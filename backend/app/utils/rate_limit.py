"""Rate limiting utility with a fast in-process fallback for development.

The app should not stall while probing for a local Redis instance that does not
not exist. In development we use the in-memory limiter immediately unless a
non-default Redis endpoint is explicitly configured.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from app.core.config import settings

_in_memory: dict[str, list[float]] = defaultdict(list)
_redis_client: Any | None = None
_redis_attempted = False


def _get_redis_client() -> Any | None:
    global _redis_client, _redis_attempted

    if not settings.redis_available:
        return None
    if _redis_attempted:
        return _redis_client

    _redis_attempted = True
    try:
        import redis  # type: ignore

        client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.25,
            socket_timeout=0.25,
        )
        client.ping()
        _redis_client = client
    except Exception:
        _redis_client = None
    return _redis_client


async def check_rate_limit(identifier: str) -> bool:
    """Return ``True`` if the request is allowed, ``False`` if rate-limited."""
    client = _get_redis_client()
    if client is None:
        return _memory_check(identifier)
    try:
        return _redis_check(client, identifier)
    except Exception:
        return _memory_check(identifier)


def _redis_check(client: Any, identifier: str) -> bool:
    key = f"rl:{identifier}"
    pipe = client.pipeline()
    now = time.time()
    window_start = now - settings.rate_limit_window_seconds
    pipe.zremrangebyscore(key, "-inf", window_start)
    pipe.zadd(key, {str(now): now})
    pipe.zcard(key)
    pipe.expire(key, settings.rate_limit_window_seconds)
    results = pipe.execute()
    count: int = results[2]
    return count <= settings.rate_limit_requests


def _memory_check(identifier: str) -> bool:
    now = time.time()
    window_start = now - settings.rate_limit_window_seconds
    timestamps = _in_memory[identifier]
    _in_memory[identifier] = [item for item in timestamps if item > window_start]
    _in_memory[identifier].append(now)
    return len(_in_memory[identifier]) <= settings.rate_limit_requests
