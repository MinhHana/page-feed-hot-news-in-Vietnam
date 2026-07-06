"""Simple in-memory rate limiting for AI endpoints."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimitError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit exceeded. Retry after {retry_after_seconds}s.")


class DailyRateLimiter:
    def __init__(self, limit: int, window_seconds: int = 86_400) -> None:
        self.limit = max(limit, 1)
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= self.limit:
                retry_after = max(int(bucket[0] + self.window_seconds - now), 1)
                raise RateLimitError(retry_after)

            bucket.append(now)
