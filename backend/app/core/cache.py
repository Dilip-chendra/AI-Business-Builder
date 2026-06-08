"""Unified cache — Redis-first with in-process TTL fallback.

The cache degrades gracefully:
- Redis available → use Redis
- Redis unavailable in development → use in-memory TTL dict (single-process only)
- Redis unavailable in production → raise RuntimeError at startup

Usage::

    from app.core.cache import cache

    value = await cache.get("my-key")
    if value is None:
        value = await compute_value()
        await cache.set("my-key", value, ttl=300)
    await cache.delete("my-key")
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── In-memory fallback ────────────────────────────────────────────────────────

class _InMemoryTTLCache:
    """Thread-safe in-process cache with TTL expiry."""

    def __init__(self) -> None:
        # {key: (value, expires_at_monotonic)}
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: Any, ttl: float = 300) -> None:
        async with self._lock:
            self._store[key] = (value, time.monotonic() + ttl)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()


# ── Redis-backed cache ────────────────────────────────────────────────────────

class _RedisCache:
    """Synchronous Redis client wrapped for async use."""

    def __init__(self) -> None:
        self._client: Any = None
        self._attempted = False

    def _connect(self) -> Any | None:
        if self._attempted:
            return self._client
        self._attempted = True
        try:
            import redis  # type: ignore
            client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=0.25,
                socket_timeout=0.25,
            )
            client.ping()
            self._client = client
            logger.info("Redis cache connected at %s", settings.redis_url)
        except Exception as exc:
            if settings.is_production:
                raise RuntimeError(
                    f"Redis is required in production but unavailable: {exc}"
                ) from exc
            logger.warning("Redis unavailable (%s) — using in-memory cache", exc)
            self._client = None
        return self._client

    async def get(self, key: str) -> Any | None:
        client = self._connect()
        if client is None:
            return None
        try:
            raw = client.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception as exc:
            logger.debug("Redis GET error: %s", exc)
            return None

    async def set(self, key: str, value: Any, ttl: float = 300) -> None:
        client = self._connect()
        if client is None:
            return
        try:
            client.setex(key, int(ttl), json.dumps(value, default=str))
        except Exception as exc:
            logger.debug("Redis SET error: %s", exc)

    async def delete(self, key: str) -> None:
        client = self._connect()
        if client is None:
            return
        try:
            client.delete(key)
        except Exception as exc:
            logger.debug("Redis DELETE error: %s", exc)

    async def clear(self) -> None:
        client = self._connect()
        if client is None:
            return
        try:
            client.flushdb()
        except Exception as exc:
            logger.debug("Redis CLEAR error: %s", exc)


# ── Unified cache singleton ───────────────────────────────────────────────────

class _UnifiedCache:
    """Tries Redis first; falls back to in-memory in development.

    The ``_use_redis`` attribute can be set to ``False`` in tests to force
    the in-memory backend without attempting a Redis connection.
    """

    def __init__(self) -> None:
        self._redis = _RedisCache()
        self._memory = _InMemoryTTLCache()
        # None = not yet determined; True = use Redis; False = use memory
        self._use_redis: bool | None = None
        self._probe_lock = asyncio.Lock()

    async def _backend(self) -> _RedisCache | _InMemoryTTLCache:
        if not settings.redis_available:
            self._use_redis = False
            return self._memory
        if self._use_redis is False:
            return self._memory
        if self._use_redis is True:
            return self._redis
        # First call — probe Redis
        async with self._probe_lock:
            if self._use_redis is None:
                try:
                    client = await asyncio.to_thread(self._redis._connect)
                    self._use_redis = client is not None
                except RuntimeError:
                    raise
                except Exception:
                    self._use_redis = False
        return self._redis if self._use_redis else self._memory

    async def get(self, key: str) -> Any | None:
        backend = await self._backend()
        return await backend.get(key)

    async def set(self, key: str, value: Any, ttl: float = 300) -> None:
        backend = await self._backend()
        await backend.set(key, value, ttl)

    async def delete(self, key: str) -> None:
        backend = await self._backend()
        await backend.delete(key)

    async def clear(self) -> None:
        backend = await self._backend()
        await backend.clear()


# Module-level singleton — import and use directly.
cache = _UnifiedCache()
