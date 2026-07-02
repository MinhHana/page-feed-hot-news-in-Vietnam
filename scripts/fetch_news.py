#!/usr/bin/env python3
"""Fetch and merge Vietnamese news from RSS feeds and 24HMoney."""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "feed" / "news.json"
MAX_ARTICLES = 200
REQUEST_TIMEOUT = 25
USER_AGENT = (
    "Mozilla/5.0 (compatible; VietnamNewsMatrix/1.0; +https://github.com/)"
)

VN_TZ = timezone(timedelta(hours=7))

RSS_SOURCES = [
    {"key": "vnexpress", "name": "VnExpress", "url": "https://vnexpress.net/rss/tin-moi-nhat.rss"},
    {"key": "tuoitre", "name": "Tuổi Trẻ", "url": "https://tuoitre.vn/rss/tin-moi-nhat.rss"},
    {"key": "thanhnien", "name": "Thanh Niên", "url": "https://thanhnien.vn/rss/home.rss"},
    {"key": "dantri", "name": "Dân Trí", "url": "https://dantri.com.vn/rss/home.rss"},
    {"key": "kenh14", "name": "Kenh14", "url": "https://kenh14.vn/rss/home.rss"},
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
        summary = clean_text(item.findtext("description"))
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
            {
                "id": article_id(link),
                "title": title,
                "summary": summary[:280],
                "url": link,
                "source": source["name"],
                "sourceKey": source["key"],
                "publishedAt": published_at,
                "category": "Tin tức",
            }
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
                "source": "24HMoney",
                "sourceKey": "24hmoney",
                "publishedAt": published_at,
                "category": category or "Tài chính",
            }
        )

    print(f"[24hmoney] {len(articles)} articles")
    return articles


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


def main() -> None:
    session = make_session()
    all_articles: list[dict[str, Any]] = []

    for source in RSS_SOURCES:
        all_articles.extend(fetch_rss_source(session, source))
        time.sleep(0.4)

    all_articles.extend(fetch_24hmoney(session))

    all_articles = dedupe_articles(all_articles)
    all_articles.sort(key=sort_key, reverse=True)
    all_articles = all_articles[:MAX_ARTICLES]

    payload = {
        "updatedAt": to_iso(datetime.now(VN_TZ)),
        "total": len(all_articles),
        "sources": [source["name"] for source in RSS_SOURCES] + ["24HMoney"],
        "articles": all_articles,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(all_articles)} articles to {OUTPUT}")


if __name__ == "__main__":
    main()
