"""Generate AI news briefs grounded in fetched articles."""

from __future__ import annotations

import hashlib
import re
import threading
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

from dateutil import parser as date_parser

from server.ai.client import AIClientError, AIUnavailableError, generate_json
from server.ai.config import AIConfig, get_ai_config
from server.ai.prompts import build_brief_prompt
from server.ai.rate_limit import DailyRateLimiter, RateLimitError

VN_TZ = timezone(timedelta(hours=7))

_brief_cache_lock = threading.Lock()
_brief_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_rate_limiter: DailyRateLimiter | None = None


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFD", value or "")
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text.replace("đ", "d").replace("Đ", "D").lower().strip()


def _parse_article_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = date_parser.parse(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=VN_TZ)
        return parsed.astimezone(VN_TZ)
    except (ValueError, TypeError):
        return None


def _matches_query(article: dict[str, Any], query: str) -> bool:
    tokens = [token for token in _normalize_text(query).split() if token]
    if not tokens:
        return True

    haystack = _normalize_text(
        f"{article.get('title', '')} {article.get('summary', '')} "
        f"{article.get('source', '')} {article.get('category', '')}"
    )
    return all(token in haystack for token in tokens)


def select_articles_for_brief(
    articles: list[dict[str, Any]],
    *,
    hours: int,
    source: str,
    query: str,
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

        if not _matches_query(article, query):
            continue

        selected.append(article)

    selected.sort(
        key=lambda item: _parse_article_time(item.get("publishedAt"))
        or datetime.min.replace(tzinfo=VN_TZ),
        reverse=True,
    )
    return selected[:limit]


def _sanitize_citations(
    citations: Any,
    articles: list[dict[str, Any]],
) -> list[dict[str, str]]:
    if not isinstance(citations, list):
        return []

    allowed_urls = {str(article.get("url", "")).strip() for article in articles}
    allowed_urls.discard("")

    cleaned: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for item in citations:
        if not isinstance(item, dict):
            continue

        url = str(item.get("url", "")).strip()
        if not url or url not in allowed_urls or url in seen_urls:
            continue

        seen_urls.add(url)
        cleaned.append(
            {
                "title": str(item.get("title", "")).strip() or "Bài viết",
                "url": url,
                "source": str(item.get("source", "")).strip() or "Nguồn",
            }
        )

        if len(cleaned) >= 8:
            break

    return cleaned


def _fallback_brief(articles: list[dict[str, Any]], query: str) -> str:
    prefix = f"Các tin liên quan \"{query.strip()}\"" if query.strip() else "Các tin mới nổi bật"
    lines = [f"{prefix}:"]
    for article in articles[:5]:
        source = article.get("source", "Nguồn")
        title = article.get("title", "").strip()
        if title:
            lines.append(f"• {title} [{source}]")
    return "\n".join(lines)


def _cache_key(payload: dict[str, Any], articles: list[dict[str, Any]]) -> str:
    article_signature = "|".join(
        f"{article.get('id')}:{article.get('publishedAt')}" for article in articles[:10]
    )
    raw = (
        f"{payload.get('query','')}|{payload.get('source','all')}|"
        f"{payload.get('hours',24)}|{len(articles)}|{article_signature}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _get_rate_limiter(config: AIConfig) -> DailyRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = DailyRateLimiter(config.daily_request_limit)
    return _rate_limiter


def _read_cache(key: str, ttl: int) -> dict[str, Any] | None:
    now = time.time()
    with _brief_cache_lock:
        cached = _brief_cache.get(key)
        if not cached:
            return None
        cached_at, payload = cached
        if now - cached_at > ttl:
            _brief_cache.pop(key, None)
            return None
        return payload


def _write_cache(key: str, payload: dict[str, Any]) -> None:
    with _brief_cache_lock:
        _brief_cache[key] = (time.time(), payload)


def generate_brief(
    articles: list[dict[str, Any]],
    *,
    query: str = "",
    source: str = "all",
    hours: int = 24,
    client_key: str = "global",
    config: AIConfig | None = None,
) -> dict[str, Any]:
    config = config or get_ai_config()
    selected = select_articles_for_brief(
        articles,
        hours=hours,
        source=source,
        query=query,
        limit=config.max_articles,
    )

    base_response = {
        "query": query.strip(),
        "source": source,
        "hours": hours,
        "articleCount": len(selected),
        "generatedAt": datetime.now(VN_TZ).isoformat(),
        "cached": False,
        "provider": None,
    }

    if not selected:
        return {
            **base_response,
            "brief": "Chưa có đủ tin trong khoảng thời gian này để tóm tắt.",
            "citations": [],
            "fallback": True,
        }

    if not config.is_configured:
        return {
            **base_response,
            "brief": _fallback_brief(selected, query),
            "citations": [
                {
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                    "source": article.get("source", ""),
                }
                for article in selected[:5]
                if article.get("url")
            ],
            "fallback": True,
            "message": (
                "AI chưa bật. Thêm OPENAI_API_KEY hoặc GEMINI_API_KEY trong Environment "
                "của Render để bật tóm tắt thông minh."
            ),
        }

    cache_key = _cache_key({"query": query, "source": source, "hours": hours}, selected)
    cached = _read_cache(cache_key, config.brief_cache_ttl)
    if cached:
        return {**cached, "cached": True}

    _get_rate_limiter(config).check(client_key)

    prompt = build_brief_prompt(query=query, hours=hours, articles=selected)

    try:
        model_payload, provider = generate_json(config, prompt)
    except RateLimitError:
        raise
    except (AIUnavailableError, AIClientError) as exc:
        return {
            **base_response,
            "brief": _fallback_brief(selected, query),
            "citations": [
                {
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                    "source": article.get("source", ""),
                }
                for article in selected[:5]
                if article.get("url")
            ],
            "fallback": True,
            "message": str(exc),
        }

    brief = str(model_payload.get("brief", "")).strip()
    if not brief:
        brief = _fallback_brief(selected, query)

    brief = re.sub(r"\n{3,}", "\n\n", brief)
    citations = _sanitize_citations(model_payload.get("citations"), selected)

    result = {
        **base_response,
        "brief": brief,
        "citations": citations,
        "fallback": False,
        "provider": provider,
    }
    _write_cache(cache_key, result)
    return result
