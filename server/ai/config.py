"""AI configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AIConfig:
    enabled: bool
    openai_api_key: str
    gemini_api_key: str
    openai_model: str
    gemini_model: str
    brief_cache_ttl: int
    daily_request_limit: int
    max_articles: int
    request_timeout: int

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def is_configured(self) -> bool:
        return self.enabled and (self.has_openai or self.has_gemini)

    def provider_names(self) -> list[str]:
        providers: list[str] = []
        if self.has_openai:
            providers.append("openai")
        if self.has_gemini:
            providers.append("gemini")
        return providers


def get_ai_config() -> AIConfig:
    return AIConfig(
        enabled=_env_bool("AI_ENABLED", True),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        openai_model=os.getenv("AI_OPENAI_MODEL", "gpt-4o-mini").strip(),
        gemini_model=os.getenv("AI_GEMINI_MODEL", "gemini-2.0-flash").strip(),
        brief_cache_ttl=int(os.getenv("AI_BRIEF_CACHE_TTL", "900")),
        daily_request_limit=int(os.getenv("AI_DAILY_REQUEST_LIMIT", "50")),
        max_articles=int(os.getenv("AI_BRIEF_MAX_ARTICLES", "40")),
        request_timeout=int(os.getenv("AI_REQUEST_TIMEOUT", "30")),
    )
