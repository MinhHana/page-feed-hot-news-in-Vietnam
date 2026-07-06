"""AI configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

XAI_API_BASE_URL = "https://api.x.ai/v1"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AIConfig:
    enabled: bool
    xai_api_key: str
    grok_model: str
    brief_cache_ttl: int
    daily_request_limit: int
    max_articles: int
    request_timeout: int
    digest_max_articles: int
    digest_cache_ttl: int
    digest_daily_limit: int
    digest_map_workers: int

    @property
    def has_grok(self) -> bool:
        return bool(self.xai_api_key)

    @property
    def is_configured(self) -> bool:
        return self.enabled and self.has_grok

    def provider_names(self) -> list[str]:
        return ["grok"] if self.has_grok else []


def get_ai_config() -> AIConfig:
    return AIConfig(
        enabled=_env_bool("AI_ENABLED", True),
        xai_api_key=os.getenv("XAI_API_KEY", "").strip(),
        grok_model=os.getenv("AI_GROK_MODEL", "grok-4.3").strip(),
        brief_cache_ttl=int(os.getenv("AI_BRIEF_CACHE_TTL", "900")),
        daily_request_limit=int(os.getenv("AI_DAILY_REQUEST_LIMIT", "50")),
        max_articles=int(os.getenv("AI_BRIEF_MAX_ARTICLES", "40")),
        request_timeout=int(os.getenv("AI_REQUEST_TIMEOUT", "30")),
        digest_max_articles=int(os.getenv("AI_DIGEST_MAX_ARTICLES", "200")),
        digest_cache_ttl=int(os.getenv("AI_DIGEST_CACHE_TTL", "1800")),
        digest_daily_limit=int(os.getenv("AI_DIGEST_DAILY_LIMIT", "20")),
        digest_map_workers=int(os.getenv("AI_DIGEST_MAP_WORKERS", "5")),
    )
