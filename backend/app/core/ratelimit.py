"""Small per-client sliding-window limiter for expensive endpoints (uploads, reports, detection, automation).

shortcut: in-process memory, so limits are per server process and reset on restart; use Redis or the database
when running more than one instance. AI calls have their own database-backed limit (services/ai/insights.py).
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.errors import AppError

_hits: dict[tuple[str, str], deque] = defaultdict(deque)
_lock = threading.Lock()


def rate_limit(bucket: str, limit: int, window_seconds: int = 60):
    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with _lock:
            hits = _hits[(bucket, client)]
            while hits and now - hits[0] > window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                raise AppError(429, f"Too many {bucket} requests. Try again in a minute.", code="rate_limited")
            hits.append(now)
    return dependency


def reset() -> None:
    with _lock:
        _hits.clear()
