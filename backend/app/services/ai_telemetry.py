"""AI Telemetry Service — per-provider observability, adaptive scoring, circuit breaker.

Tracks in-memory (no DB required):
  - success/failure/timeout counts per provider
  - rolling average latency
  - last 50 failures with full context
  - circuit breaker state (open/closed/half-open)

Adaptive routing:
  - Each provider gets a dynamic score (0-100)
  - Score = success_rate * 60 + latency_score * 30 + availability * 10
  - Circuit breaker opens after 3 consecutive failures, resets after 60s cooldown

Thread-safe: uses asyncio.Lock for all mutations.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
_CIRCUIT_BREAKER_THRESHOLD = 3      # consecutive failures before opening
_CIRCUIT_BREAKER_COOLDOWN  = 60.0   # seconds before half-open retry
_FAILURE_LOG_SIZE          = 50     # rolling failure log entries
_LATENCY_WINDOW            = 20     # rolling window for avg latency


@dataclass
class ProviderStats:
    """Per-provider telemetry counters."""
    name: str
    total_requests: int = 0
    total_successes: int = 0
    total_failures: int = 0
    total_timeouts: int = 0
    total_rate_limits: int = 0
    consecutive_failures: int = 0
    # Rolling latency window (seconds)
    latency_window: deque = field(default_factory=lambda: deque(maxlen=_LATENCY_WINDOW))
    # Circuit breaker
    circuit_open: bool = False
    circuit_opened_at: float = 0.0
    # Last success/failure timestamps
    last_success_at: float = 0.0
    last_failure_at: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0  # assume healthy if never used
        return self.total_successes / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        if not self.latency_window:
            return 0.0
        return sum(self.latency_window) / len(self.latency_window) * 1000

    @property
    def is_available(self) -> bool:
        """True if circuit is closed or cooldown has elapsed (half-open)."""
        if not self.circuit_open:
            return True
        elapsed = time.monotonic() - self.circuit_opened_at
        return elapsed >= _CIRCUIT_BREAKER_COOLDOWN

    @property
    def circuit_state(self) -> str:
        if not self.circuit_open:
            return "closed"
        elapsed = time.monotonic() - self.circuit_opened_at
        if elapsed >= _CIRCUIT_BREAKER_COOLDOWN:
            return "half-open"
        return "open"

    def score(self) -> float:
        """Dynamic provider score 0-100. Higher = better."""
        if not self.is_available:
            return 0.0

        # Success rate component (0-60)
        sr_score = self.success_rate * 60

        # Latency component (0-30) — lower latency = higher score
        # Baseline: 500ms = 30pts, 2000ms = 0pts
        avg_ms = self.avg_latency_ms
        if avg_ms == 0:
            lat_score = 30.0  # no data = assume fast
        else:
            lat_score = max(0.0, 30.0 * (1 - (avg_ms - 200) / 1800))

        # Availability component (0-10)
        avail_score = 10.0 if self.is_available else 0.0

        return round(sr_score + lat_score + avail_score, 2)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "total_requests": self.total_requests,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "total_timeouts": self.total_timeouts,
            "total_rate_limits": self.total_rate_limits,
            "success_rate_pct": round(self.success_rate * 100, 1),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "circuit_state": self.circuit_state,
            "score": self.score(),
            "is_available": self.is_available,
            "last_success_at": self.last_success_at,
            "last_failure_at": self.last_failure_at,
        }


@dataclass
class FailureRecord:
    """Single failure log entry."""
    trace_id: str
    provider: str
    error_type: str
    error_message: str
    latency_ms: float
    timestamp: float
    prompt_preview: str = ""  # first 100 chars of prompt (no secrets)

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "provider": self.provider,
            "error_type": self.error_type,
            "error_message": self.error_message[:200],
            "latency_ms": round(self.latency_ms, 1),
            "timestamp": self.timestamp,
            "prompt_preview": self.prompt_preview,
        }


class AITelemetryService:
    """Singleton telemetry service. Import and use `telemetry` module-level instance."""

    _instance: "AITelemetryService | None" = None

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._providers: dict[str, ProviderStats] = {
            "groq":        ProviderStats(name="groq"),
            "huggingface": ProviderStats(name="huggingface"),
            "ollama":      ProviderStats(name="ollama"),
        }
        self._failure_log: deque[FailureRecord] = deque(maxlen=_FAILURE_LOG_SIZE)
        self._total_requests: int = 0
        self._total_fallbacks: int = 0
        self._started_at: float = time.monotonic()

    @classmethod
    def get(cls) -> "AITelemetryService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Recording ─────────────────────────────────────────────────────────────

    async def record_success(
        self,
        provider: str,
        latency_s: float,
        trace_id: str = "",
        tokens: int = 0,
    ) -> None:
        async with self._lock:
            stats = self._get_or_create(provider)
            stats.total_requests += 1
            stats.total_successes += 1
            stats.consecutive_failures = 0
            stats.latency_window.append(latency_s)
            stats.last_success_at = time.time()
            # Reset circuit breaker on success
            if stats.circuit_open:
                stats.circuit_open = False
                logger.info("Circuit breaker CLOSED for provider=%s", provider)
            self._total_requests += 1
            logger.debug(
                "Telemetry: success  provider=%s  latency=%.2fs  tokens=%d  trace=%s",
                provider, latency_s, tokens, trace_id,
            )

    async def record_failure(
        self,
        provider: str,
        error_type: str,
        error_message: str,
        latency_s: float,
        trace_id: str = "",
        prompt_preview: str = "",
        is_timeout: bool = False,
        is_rate_limit: bool = False,
    ) -> None:
        async with self._lock:
            stats = self._get_or_create(provider)
            stats.total_requests += 1
            stats.total_failures += 1
            stats.consecutive_failures += 1
            stats.last_failure_at = time.time()
            if is_timeout:
                stats.total_timeouts += 1
            if is_rate_limit:
                stats.total_rate_limits += 1

            # Circuit breaker: open after threshold consecutive failures
            if (
                stats.consecutive_failures >= _CIRCUIT_BREAKER_THRESHOLD
                and not stats.circuit_open
            ):
                stats.circuit_open = True
                stats.circuit_opened_at = time.monotonic()
                logger.warning(
                    "Circuit breaker OPENED for provider=%s  consecutive_failures=%d",
                    provider, stats.consecutive_failures,
                )

            # Log failure
            self._failure_log.append(FailureRecord(
                trace_id=trace_id,
                provider=provider,
                error_type=error_type,
                error_message=error_message,
                latency_ms=latency_s * 1000,
                timestamp=time.time(),
                prompt_preview=prompt_preview[:100],
            ))
            self._total_requests += 1

    async def record_fallback(self, from_provider: str, to_provider: str) -> None:
        async with self._lock:
            self._total_fallbacks += 1
            logger.info("Telemetry: fallback  from=%s  to=%s", from_provider, to_provider)

    # ── Adaptive routing ──────────────────────────────────────────────────────

    def best_provider(self, candidates: list[str]) -> str | None:
        """Return the highest-scoring available provider from candidates."""
        available = [
            (name, self._providers.get(name, ProviderStats(name=name)))
            for name in candidates
            if self._providers.get(name, ProviderStats(name=name)).is_available
        ]
        if not available:
            return None
        return max(available, key=lambda x: x[1].score())[0]

    def is_provider_available(self, provider: str) -> bool:
        stats = self._providers.get(provider)
        return stats.is_available if stats else True

    # ── Reporting ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return full telemetry snapshot."""
        uptime_s = time.monotonic() - self._started_at
        return {
            "uptime_seconds": round(uptime_s, 0),
            "total_requests": self._total_requests,
            "total_fallbacks": self._total_fallbacks,
            "fallback_rate_pct": round(
                self._total_fallbacks / max(self._total_requests, 1) * 100, 1
            ),
            "providers": {
                name: stats.to_dict()
                for name, stats in self._providers.items()
            },
            "recent_failures": [f.to_dict() for f in reversed(self._failure_log)],
        }

    def get_provider_health(self) -> dict[str, str]:
        """Return color-coded health per provider: green/yellow/red."""
        health = {}
        for name, stats in self._providers.items():
            if not stats.is_available:
                health[name] = "red"
            elif stats.success_rate < 0.7 or stats.consecutive_failures >= 2:
                health[name] = "yellow"
            else:
                health[name] = "green"
        return health

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_or_create(self, provider: str) -> ProviderStats:
        if provider not in self._providers:
            self._providers[provider] = ProviderStats(name=provider)
        return self._providers[provider]


# Module-level singleton
telemetry = AITelemetryService.get()
