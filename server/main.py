"""FastAPI server: static site + live news API."""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from fetch_news import fetch_all_news  # noqa: E402

CACHE_TTL_SECONDS = int(os.getenv("NEWS_CACHE_TTL", "600"))
PORT = int(os.getenv("PORT", "8000"))

app = FastAPI(title="Vietnam News Matrix Feed", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_cache_lock = threading.Lock()
_cache_payload: dict[str, Any] | None = None
_cache_fetched_at = 0.0


def get_cached_news(force_refresh: bool = False) -> dict[str, Any]:
    global _cache_payload, _cache_fetched_at

    with _cache_lock:
        now = time.time()
        is_stale = _cache_payload is None or (now - _cache_fetched_at) > CACHE_TTL_SECONDS

        if force_refresh or is_stale:
            _cache_payload = fetch_all_news()
            _cache_fetched_at = now

        return _cache_payload


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/news")
def news(refresh: bool = Query(default=False)) -> dict[str, Any]:
    return get_cached_news(force_refresh=refresh)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "index.html")


app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server.main:app", host="0.0.0.0", port=PORT, reload=False)
