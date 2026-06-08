"""Telemetry helpers for AI provider routing health."""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.cache import cache

_KEY = "ai_orchestrator_telemetry_v1"
_TTL_SECONDS = 60 * 60 * 24 * 7  # keep one week


class AITelemetryService:
    async def _load(self) -> dict:
        existing = await cache.get(_KEY)
        if isinstance(existing, dict):
            existing.setdefault("providers", {})
            existing.setdefault("recent_failures", [])
            return existing
        return {"providers": {}, "recent_failures": []}

    async def record_success(self, provider: str, latency_ms: int) -> None:
        data = await self._load()
        p = data["providers"].setdefault(provider, {"success": 0, "failure": 0, "timeouts": 0, "latency_ms_sum": 0})
        p["success"] += 1
        p["latency_ms_sum"] += max(0, latency_ms)
        await cache.set(_KEY, data, ttl=_TTL_SECONDS)

    async def record_failure(self, provider: str, reason: str, timeout: bool = False) -> None:
        data = await self._load()
        p = data["providers"].setdefault(provider, {"success": 0, "failure": 0, "timeouts": 0, "latency_ms_sum": 0})
        p["failure"] += 1
        if timeout:
            p["timeouts"] += 1
        failures = data["recent_failures"]
        failures.append(
            {
                "provider": provider,
                "reason": reason[:300],
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )
        if len(failures) > 50:
            data["recent_failures"] = failures[-50:]
        await cache.set(_KEY, data, ttl=_TTL_SECONDS)

    async def snapshot(self) -> dict:
        data = await self._load()
        providers = {}
        for name, p in data["providers"].items():
            attempts = p["success"] + p["failure"]
            providers[name] = {
                **p,
                "attempts": attempts,
                "success_rate": (p["success"] / attempts) if attempts else 0.0,
                "avg_latency_ms": (p["latency_ms_sum"] / p["success"]) if p["success"] else 0.0,
            }
        return {"providers": providers, "recent_failures": data["recent_failures"]}
