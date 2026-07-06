"""Map-reduce digest: summarize the full feed grouped by news domains."""

from __future__ import annotations

import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from server.ai.client import AIClientError, AIUnavailableError, generate_json
from server.ai.config import AIConfig, get_ai_config
from server.ai.grouping import GROUP_ORDER, group_articles
from server.ai.prompts import build_map_prompt, build_reduce_prompt
from server.ai.rate_limit import DailyRateLimiter, RateLimitError
from server.ai.summarize import _parse_article_time  # noqa: PLC2701

VN_TZ = timezone(timedelta(hours=7))

_digest_cache_lock = threading.Lock()
_digest_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_digest_rate_limiter: DailyRateLimiter | None = None


def _select_articles(
    articles: list[dict[str, Any]],
    *,
    hours: int,
    source: str,
    limit: int,
) -> list[dict[str, Any]]:
    cutoff = datetime.now(VN_TZ) - timedelta(hours=hours)
    selected: list[dict[str, Any]] = []

    for article in articles:
        if source != "all" and article.get("sourceKey") != source:
            continue

        published_at = _parse_article_time(article.get("publishedAt"))
        if published_at and published_at < cutoff:
            continue

        selected.append(article)

    selected.sort(
        key=lambda item: _parse_article_time(item.get("publishedAt"))
        or datetime.min.replace(tzinfo=VN_TZ),
        reverse=True,
    )
    return selected[:limit]


def _get_rate_limiter(config: AIConfig) -> DailyRateLimiter:
    global _digest_rate_limiter
    if _digest_rate_limiter is None:
        _digest_rate_limiter = DailyRateLimiter(config.digest_daily_limit)
    return _digest_rate_limiter


def _cache_key(source: str, hours: int, articles: list[dict[str, Any]]) -> str:
    signature = "|".join(
        f"{article.get('id')}:{article.get('publishedAt')}" for article in articles[:20]
    )
    raw = f"{source}|{hours}|{len(articles)}|{signature}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_cache(key: str, ttl: int) -> dict[str, Any] | None:
    now = time.time()
    with _digest_cache_lock:
        cached = _digest_cache.get(key)
        if not cached:
            return None
        cached_at, payload = cached
        if now - cached_at > ttl:
            _digest_cache.pop(key, None)
            return None
        return payload


def _write_cache(key: str, payload: dict[str, Any]) -> None:
    with _digest_cache_lock:
        _digest_cache[key] = (time.time(), payload)


def _resolve_citations(
    article_ids: Any,
    index: dict[str, dict[str, Any]],
    limit: int = 6,
) -> list[dict[str, str]]:
    if not isinstance(article_ids, list):
        return []

    citations: list[dict[str, str]] = []
    seen: set[str] = set()

    for article_id in article_ids:
        article = index.get(str(article_id))
        if not article:
            continue

        url = str(article.get("url", "")).strip()
        if not url or url in seen:
            continue

        seen.add(url)
        citations.append(
            {
                "title": str(article.get("title", "")).strip() or "Bài viết",
                "url": url,
                "source": str(article.get("source", "")).strip() or "Nguồn",
            }
        )

        if len(citations) >= limit:
            break

    return citations


def _run_map(
    config: AIConfig,
    groups: dict[str, list[dict[str, Any]]],
    hours: int,
) -> list[dict[str, Any]]:
    ordered_groups = [(name, groups[name]) for name in GROUP_ORDER if name in groups]

    def _map_one(group_name: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        prompt = build_map_prompt(group_name=group_name, hours=hours, articles=items)
        payload, _ = generate_json(config, prompt)
        points = payload.get("points")
        return {
            "group": group_name,
            "points": points if isinstance(points, list) else [],
        }

    results: list[dict[str, Any]] = []
    workers = max(1, min(config.digest_map_workers, len(ordered_groups)))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_map_one, name, items): name
            for name, items in ordered_groups
        }
        collected: dict[str, dict[str, Any]] = {}
        for future in futures:
            name = futures[future]
            try:
                collected[name] = future.result()
            except Exception:  # noqa: BLE001
                collected[name] = {"group": name, "points": []}

    for name in GROUP_ORDER:
        if name in collected and collected[name]["points"]:
            results.append(collected[name])

    return results


def _fallback_digest(
    groups: dict[str, list[dict[str, Any]]],
    base_response: dict[str, Any],
    message: str | None,
) -> dict[str, Any]:
    sections = []
    for name in GROUP_ORDER:
        items = groups.get(name)
        if not items:
            continue
        points = [
            {
                "text": article.get("title", "").strip(),
                "citations": [
                    {
                        "title": article.get("title", ""),
                        "url": article.get("url", ""),
                        "source": article.get("source", ""),
                    }
                ]
                if article.get("url")
                else [],
            }
            for article in items[:6]
            if article.get("title")
        ]
        if points:
            sections.append({"title": name, "points": points})

    return {
        **base_response,
        "headline": "Danh sách tin mới theo chuyên mục (chưa bật AI tổng hợp).",
        "hotspots": [],
        "sections": sections,
        "fallback": True,
        "message": message,
    }


def generate_digest(
    articles: list[dict[str, Any]],
    *,
    source: str = "all",
    hours: int = 48,
    client_key: str = "global",
    config: AIConfig | None = None,
) -> dict[str, Any]:
    config = config or get_ai_config()
    selected = _select_articles(
        articles,
        hours=hours,
        source=source,
        limit=config.digest_max_articles,
    )

    groups = group_articles(selected)

    base_response = {
        "source": source,
        "hours": hours,
        "articleCount": len(selected),
        "groupCounts": {name: len(items) for name, items in groups.items()},
        "generatedAt": datetime.now(VN_TZ).isoformat(),
        "cached": False,
        "provider": None,
    }

    if not selected:
        return {
            **base_response,
            "headline": "Chưa có đủ tin trong khoảng thời gian này để tổng hợp.",
            "hotspots": [],
            "sections": [],
            "fallback": True,
        }

    if not config.is_configured:
        return _fallback_digest(
            groups,
            base_response,
            "AI chưa bật. Thêm XAI_API_KEY (Grok API key) trong Environment của Render "
            "để bật bản tin tổng hợp.",
        )

    cache_key = _cache_key(source, hours, selected)
    cached = _read_cache(cache_key, config.digest_cache_ttl)
    if cached:
        return {**cached, "cached": True}

    _get_rate_limiter(config).check(client_key)

    index = {str(article.get("id")): article for article in selected}

    try:
        map_results = _run_map(config, groups, hours)
        if not map_results:
            raise AIClientError("Map stage returned no points.")

        reduce_prompt = build_reduce_prompt(hours=hours, map_results=map_results)
        reduced, provider = generate_json(config, reduce_prompt)
    except RateLimitError:
        raise
    except (AIUnavailableError, AIClientError) as exc:
        return _fallback_digest(groups, base_response, str(exc))

    hotspots = []
    for item in reduced.get("hotspots", []) or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        hotspots.append(
            {
                "text": text,
                "citations": _resolve_citations(item.get("articleIds"), index),
            }
        )

    sections = []
    for section in reduced.get("sections", []) or []:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title", "")).strip() or "Khác"
        points = []
        for point in section.get("points", []) or []:
            if not isinstance(point, dict):
                continue
            text = str(point.get("text", "")).strip()
            if not text:
                continue
            points.append(
                {
                    "text": text,
                    "citations": _resolve_citations(point.get("articleIds"), index),
                }
            )
        if points:
            sections.append({"title": title, "points": points})

    result = {
        **base_response,
        "headline": str(reduced.get("headline", "")).strip()
        or "Bản tin tổng hợp trong ngày.",
        "hotspots": hotspots,
        "sections": sections,
        "fallback": False,
        "provider": provider,
    }
    _write_cache(cache_key, result)
    return result
