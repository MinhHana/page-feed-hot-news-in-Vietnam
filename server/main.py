"""FastAPI server: static site + live news API."""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from fetch_news import fetch_all_news  # noqa: E402

from server.ai.config import get_ai_config  # noqa: E402
from server.ai.rate_limit import RateLimitError  # noqa: E402
from server.ai.summarize import generate_brief  # noqa: E402

CACHE_TTL_SECONDS = int(os.getenv("NEWS_CACHE_TTL", "600"))
PORT = int(os.getenv("PORT", "8000"))

app = FastAPI(title="Vietnam News Matrix Feed", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_cache_lock = threading.Lock()
_cache_payload: dict[str, Any] | None = None
_cache_fetched_at = 0.0


class BriefRequest(BaseModel):
    query: str = ""
    source: str = "all"
    hours: int = Field(default=24, ge=1, le=168)


def get_cached_news(force_refresh: bool = False) -> dict[str, Any]:
    global _cache_payload, _cache_fetched_at

    with _cache_lock:
        now = time.time()
        is_stale = _cache_payload is None or (now - _cache_fetched_at) > CACHE_TTL_SECONDS

        if force_refresh or is_stale:
            _cache_payload = fetch_all_news()
            _cache_fetched_at = now

        return _cache_payload


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or "anonymous"
    if request.client and request.client.host:
        return request.client.host
    return "anonymous"


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/news")
def news(refresh: bool = Query(default=False)) -> dict[str, Any]:
    return get_cached_news(force_refresh=refresh)


@app.get("/api/ai/status")
def ai_status() -> dict[str, Any]:
    config = get_ai_config()
    return {
        "enabled": config.enabled,
        "configured": config.is_configured,
        "providers": config.provider_names(),
        "openaiModel": config.openai_model if config.has_openai else None,
        "geminiModel": config.gemini_model if config.has_gemini else None,
        "dailyRequestLimit": config.daily_request_limit,
        "briefCacheTtl": config.brief_cache_ttl,
        "message": (
            "AI sẵn sàng."
            if config.is_configured
            else "Thêm OPENAI_API_KEY hoặc GEMINI_API_KEY trên Render để bật tóm tắt AI."
        ),
    }


@app.post("/api/ai/brief")
def ai_brief(request: Request, body: BriefRequest) -> dict[str, Any]:
    payload = get_cached_news(force_refresh=False)
    articles = payload.get("articles") or []

    try:
        return generate_brief(
            articles,
            query=body.query,
            source=body.source,
            hours=body.hours,
            client_key=_client_key(request),
        )
    except RateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Đã vượt giới hạn tóm tắt AI trong ngày. Vui lòng thử lại sau.",
                "retryAfter": exc.retry_after_seconds,
            },
        ) from exc


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "index.html")


app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server.main:app", host="0.0.0.0", port=PORT, reload=False)
