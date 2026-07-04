#!/usr/bin/env python3
"""Fetch and merge Vietnamese news from RSS feeds and 24HMoney."""

from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "feed" / "news.json"
MAX_ARTICLES = 200
REQUEST_TIMEOUT = 25
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

VN_TZ = timezone(timedelta(hours=7))

RSS_SOURCES = [
    {"key": "vnexpress", "name": "VnExpress", "url": "https://vnexpress.net/rss/tin-moi-nhat.rss"},
    {"key": "tuoitre", "name": "Tuổi Trẻ", "url": "https://tuoitre.vn/rss/tin-moi-nhat.rss"},
    {"key": "thanhnien", "name": "Thanh Niên", "url": "https://thanhnien.vn/rss/home.rss"},
    {"key": "dantri", "name": "Dân Trí", "url": "https://dantri.com.vn/rss/home.rss"},
    {"key": "kenh14", "name": "Kenh14", "url": "https://kenh14.vn/rss/home.rss"},
    {
        "key": "cafef",
        "name": "CafeF",
        "url": "https://cafef.vn/home.rss",
        "category": "Tài chính",
    },
]

SCRAPE_SOURCES = [
    {"key": "vneconomy", "name": "VnEconomy", "url": "https://vneconomy.vn/", "category": "Kinh tế"},
    {"key": "vietstock", "name": "Vietstock", "url": "https://vietstock.vn/", "category": "Chứng khoán"},
]

RELATIVE_TIME_PATTERN = re.compile(
    r"(\d+)\s*(giây|phút|giờ|ngày|tuần|tháng|năm)", re.IGNORECASE
)
RELATIVE_UNITS = {
    "giây": "seconds",
    "phút": "minutes",
    "giờ": "hours",
    "ngày": "days",
    "tuần": "weeks",
    "tháng": "days",  # approximate as 30 days
    "năm": "days",  # approximate as 365 days
}
RELATIVE_MULTIPLIERS = {"tháng": 30, "năm": 365}
IMAGE_SRC_PATTERN = re.compile(r"""src=["']([^"']+)["']""", re.IGNORECASE)
MEDIA_CONTENT_TAG = "{http://search.yahoo.com/mrss/}content"
VN_DATETIME_LABEL_PATTERN = re.compile(
    r"(\d{1,2}):(\d{2}),\s*(\d{2})/(\d{2})/(\d{4})"
)
ARTICLE_PUBLISHED_META_PATTERN = re.compile(
    r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
ARTICLE_PUBLISHED_META_ALT_PATTERN = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']article:published_time["\']',
    re.IGNORECASE,
)
ARTICLE_META_TIME_PATTERN = re.compile(
    r'class=["\']article-meta__time["\'][^>]*>([^<]+)<',
    re.IGNORECASE,
)
IMAGE_UPLOAD_DATE_PATTERN = re.compile(r"/uploads/(\d{4})/(\d{2})/(\d{2})/")
ARTICLE_DATE_FETCH_WORKERS = 8


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def article_id(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:12]


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=VN_TZ)
    return dt.astimezone(VN_TZ).isoformat()


def parse_relative_time(label: str, now: datetime) -> datetime | None:
    match = RELATIVE_TIME_PATTERN.search(label.strip())
    if not match:
        return None

    amount = int(match.group(1))
    unit_vi = match.group(2).lower()
    unit = RELATIVE_UNITS.get(unit_vi)
    if not unit:
        return None

    kwargs = {unit: amount * RELATIVE_MULTIPLIERS.get(unit_vi, 1)}
    return now - timedelta(**kwargs)


def parse_nuxt_timestamps(html: str) -> list[int]:
    return [int(value) for value in re.findall(r"published_at=(\d{10})", html)]


def looks_like_image(url: str) -> bool:
    lowered = url.lower().split("?", 1)[0]
    if lowered.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return True
    return any(
        marker in lowered
        for marker in ("cdn", "vcdn", "kenh14cdn", "cafefcdn", "premedia", "/zoom/", "/avatar")
    )


def extract_image_url(item: ElementTree.Element, raw_description: str) -> str:
    enclosure = item.find("enclosure")
    if enclosure is not None:
        url = (enclosure.get("url") or "").strip()
        if url and looks_like_image(url):
            return unescape(url)

    media = item.find(MEDIA_CONTENT_TAG)
    if media is not None:
        url = (media.get("url") or "").strip()
        if url:
            return unescape(url)

    if raw_description:
        match = IMAGE_SRC_PATTERN.search(raw_description)
        if match:
            return unescape(match.group(1).strip())

    return ""


def extract_image_from_element(element) -> str:
    if element is None:
        return ""

    for img in element.select("img"):
        for attr in ("data-src", "data-original", "src"):
            value = (img.get(attr) or "").strip()
            if value and not value.startswith("data:") and looks_like_image(value):
                return unescape(value)

    return ""


def parse_vn_datetime_label(label: str) -> datetime | None:
    match = VN_DATETIME_LABEL_PATTERN.search(label.strip())
    if not match:
        return None

    hour, minute, day, month, year = map(int, match.groups())
    try:
        return datetime(year, month, day, hour, minute, tzinfo=VN_TZ)
    except ValueError:
        return None


def parse_image_upload_date(url: str) -> str | None:
    match = IMAGE_UPLOAD_DATE_PATTERN.search(url)
    if not match:
        return None

    year, month, day = map(int, match.groups())
    return to_iso(datetime(year, month, day, 12, 0, tzinfo=VN_TZ))


def extract_published_at_from_html(html: str) -> str | None:
    for pattern in (ARTICLE_PUBLISHED_META_PATTERN, ARTICLE_PUBLISHED_META_ALT_PATTERN):
        match = pattern.search(html)
        if match:
            try:
                return to_iso(date_parser.parse(match.group(1)))
            except (ValueError, TypeError):
                pass

    match = ARTICLE_META_TIME_PATTERN.search(html)
    if match:
        parsed = parse_vn_datetime_label(match.group(1))
        if parsed:
            return to_iso(parsed)

    return None


def fetch_article_published_at(url: str) -> str | None:
    session = make_session()
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return extract_published_at_from_html(response.text)
    except Exception:  # noqa: BLE001
        return None


def fetch_published_at_map(urls: list[str]) -> dict[str, str | None]:
    published_at_map: dict[str, str | None] = {}
    if not urls:
        return published_at_map

    with ThreadPoolExecutor(max_workers=ARTICLE_DATE_FETCH_WORKERS) as executor:
        futures = {executor.submit(fetch_article_published_at, url): url for url in urls}
        for future in as_completed(futures):
            url = futures[future]
            try:
                published_at_map[url] = future.result()
            except Exception:  # noqa: BLE001
                published_at_map[url] = None

    return published_at_map


def build_article(
    *,
    title: str,
    url: str,
    source: str,
    source_key: str,
    category: str,
    summary: str = "",
    image: str = "",
    published_at: str | None = None,
) -> dict[str, Any]:
    return {
        "id": article_id(url),
        "title": title,
        "summary": summary[:280],
        "url": url,
        "image": image,
        "source": source,
        "sourceKey": source_key,
        "publishedAt": published_at,
        "category": category,
    }


def fetch_rss_source(session: requests.Session, source: dict[str, str]) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    try:
        response = session.get(source["url"], timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        content = response.content.lstrip(b"\xef\xbb\xbf").strip()
        root = ElementTree.fromstring(content)
    except Exception as exc:  # noqa: BLE001
        print(f"[rss] {source['name']}: {exc}")
        return articles

    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title"))
        link = clean_text(item.findtext("link"))
        raw_description = item.findtext("description") or ""
        summary = clean_text(raw_description)
        image = extract_image_url(item, raw_description)
        pub_raw = clean_text(item.findtext("pubDate"))

        if not title or not link:
            continue

        published_at = None
        if pub_raw:
            try:
                published_at = to_iso(date_parser.parse(pub_raw))
            except (ValueError, TypeError):
                published_at = None

        articles.append(
            build_article(
                title=title,
                url=link,
                source=source["name"],
                source_key=source["key"],
                category=source.get("category", "Tin tức"),
                summary=summary,
                image=image,
                published_at=published_at,
            )
        )

    print(f"[rss] {source['name']}: {len(articles)} articles")
    return articles


def fetch_24hmoney(session: requests.Session) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    url = "https://24hmoney.vn/news/live"

    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        html = response.text
    except Exception as exc:  # noqa: BLE001
        print(f"[24hmoney] fetch failed: {exc}")
        return articles

    now = datetime.now(VN_TZ)
    timestamps = parse_nuxt_timestamps(html)
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("article.article-item-live")

    for index, card in enumerate(cards):
        title_el = card.select_one("h3.article-title a")
        if not title_el:
            continue

        title = clean_text(title_el.get_text())
        link = title_el.get("href", "").strip()
        if not title or not link:
            continue

        link = link.split("?")[0]
        summary_el = card.select_one(".article-description")
        summary = clean_text(summary_el.get_text() if summary_el else "")

        category_el = card.select_one(".category-tag")
        category = clean_text(category_el.get_text() if category_el else "Tài chính").lstrip("#")

        published_at = None
        if index < len(timestamps):
            published_at = to_iso(datetime.fromtimestamp(timestamps[index], tz=VN_TZ))
        else:
            time_el = card.select_one(".article-time")
            if time_el:
                relative = parse_relative_time(clean_text(time_el.get_text()), now)
                if relative:
                    published_at = to_iso(relative)

        articles.append(
            {
                "id": article_id(link),
                "title": title,
                "summary": summary[:280],
                "url": link,
                "image": "",
                "source": "24HMoney",
                "sourceKey": "24hmoney",
                "publishedAt": published_at,
                "category": category or "Tài chính",
            }
        )

    print(f"[24hmoney] {len(articles)} articles")
    return articles


def fetch_vneconomy(session: requests.Session, source: dict[str, str]) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    skip_parts = ("tap-chi", "doanh-nghiep-niem-yet", "san-pham", "rss", "video")

    try:
        response = session.get(source["url"], timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as exc:  # noqa: BLE001
        print(f"[scrape] {source['name']}: {exc}")
        return articles

    seen: set[str] = set()
    pending: list[dict[str, Any]] = []

    for article_el in soup.select("article"):
        link_el = article_el.select_one("h2 a[href], h3 a[href], .title a[href]")
        if not link_el:
            candidates = [
                anchor
                for anchor in article_el.select("a[href]")
                if len(clean_text(anchor.get_text())) >= 20
            ]
            link_el = candidates[0] if candidates else None
        if not link_el:
            continue

        title = clean_text(link_el.get_text())
        href = (link_el.get("href") or "").strip()
        if not title or len(title) < 20 or not href.endswith(".htm"):
            continue
        if any(part in href for part in skip_parts):
            continue

        url = urljoin(source["url"], href)
        if url in seen:
            continue
        seen.add(url)

        summary_el = article_el.select_one("p, .sapo, .description")
        summary = clean_text(summary_el.get_text() if summary_el else "")
        image = extract_image_from_element(article_el)

        pending.append(
            {
                "title": title,
                "url": url,
                "summary": summary,
                "image": image,
            }
        )

    published_at_map = fetch_published_at_map([item["url"] for item in pending])

    for item in pending:
        published_at = published_at_map.get(item["url"])
        if not published_at:
            published_at = parse_image_upload_date(item["image"] or item["url"])

        articles.append(
            build_article(
                title=item["title"],
                url=item["url"],
                source=source["name"],
                source_key=source["key"],
                category=source.get("category", "Kinh tế"),
                summary=item["summary"],
                image=item["image"],
                published_at=published_at,
            )
        )

    print(f"[scrape] {source['name']}: {len(articles)} articles")
    return articles


def fetch_vietstock(session: requests.Session, source: dict[str, str]) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []

    try:
        response = session.get(source["url"], timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as exc:  # noqa: BLE001
        print(f"[scrape] {source['name']}: {exc}")
        return articles

    seen: set[str] = set()
    pending: list[dict[str, Any]] = []

    for link_el in soup.select('a[href*="/20"]'):
        href = (link_el.get("href") or "").strip()
        title = clean_text(link_el.get_text())
        if not title or len(title) < 20 or not href.endswith(".htm"):
            continue
        if "/chu-de/" in href or "/tag/" in href:
            continue

        url = urljoin(source["url"], href)
        if url in seen:
            continue
        seen.add(url)

        container = link_el.find_parent(["article", "div", "li"])
        image = extract_image_from_element(container)
        published_at = None
        date_match = re.search(r"/(20\d{2})/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])/", url)
        if date_match:
            year, month, day = map(int, date_match.groups())
            published_at = to_iso(datetime(year, month, day, 12, 0, tzinfo=VN_TZ))

        pending.append(
            {
                "title": title,
                "url": url,
                "image": image,
                "published_at": published_at,
            }
        )

    urls_to_fetch = [item["url"] for item in pending if not item["published_at"]]
    published_at_map = fetch_published_at_map(urls_to_fetch)

    for item in pending:
        published_at = item["published_at"] or published_at_map.get(item["url"])
        if not published_at:
            published_at = parse_image_upload_date(item["image"] or item["url"])

        articles.append(
            build_article(
                title=item["title"],
                url=item["url"],
                source=source["name"],
                source_key=source["key"],
                category=source.get("category", "Chứng khoán"),
                image=item["image"],
                published_at=published_at,
            )
        )

    print(f"[scrape] {source['name']}: {len(articles)} articles")
    return articles


def fetch_scrape_source(session: requests.Session, source: dict[str, str]) -> list[dict[str, Any]]:
    if source["key"] == "vneconomy":
        return fetch_vneconomy(session, source)
    if source["key"] == "vietstock":
        return fetch_vietstock(session, source)
    return []


def sort_key(article: dict[str, Any]) -> datetime:
    value = article.get("publishedAt")
    if not value:
        return datetime.min.replace(tzinfo=VN_TZ)
    try:
        return date_parser.parse(value)
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=VN_TZ)


def dedupe_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_urls: set[str] = set()
    unique: list[dict[str, Any]] = []

    for article in articles:
        normalized = urlparse(article["url"])._replace(query="", fragment="").geturl()
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        unique.append(article)

    return unique


def fetch_all_news() -> dict[str, Any]:
    session = make_session()
    all_articles: list[dict[str, Any]] = []

    for source in RSS_SOURCES:
        all_articles.extend(fetch_rss_source(session, source))
        time.sleep(0.4)

    for source in SCRAPE_SOURCES:
        all_articles.extend(fetch_scrape_source(session, source))
        time.sleep(0.4)

    all_articles.extend(fetch_24hmoney(session))

    all_articles = dedupe_articles(all_articles)
    all_articles.sort(key=sort_key, reverse=True)
    all_articles = all_articles[:MAX_ARTICLES]

    source_names = [source["name"] for source in RSS_SOURCES]
    source_names.extend(source["name"] for source in SCRAPE_SOURCES)
    source_names.append("24HMoney")

    return {
        "updatedAt": to_iso(datetime.now(VN_TZ)),
        "total": len(all_articles),
        "sources": source_names,
        "articles": all_articles,
    }


def main() -> None:
    payload = fetch_all_news()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {payload['total']} articles to {OUTPUT}")


if __name__ == "__main__":
    main()
