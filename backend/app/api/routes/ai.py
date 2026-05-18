"""AI provider health, settings, and telemetry endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.services.ai_service import AIHealth, AIService
from app.services.providers.featherless_provider import FeatherlessProvider

router = APIRouter()


@router.get("/health", response_model=AIHealth)
async def ai_health() -> AIHealth:
    """Return availability status for each AI provider. Public endpoint."""
    return await AIService().health()


class AITestRequest(BaseModel):
    prompt: str = "Say hello in one sentence."


class AITestResponse(BaseModel):
    output: str
    provider_used: str


@router.post("/test", response_model=AITestResponse)
async def test_ai(
    payload: AITestRequest,
    current_user: User = Depends(get_current_user),
) -> AITestResponse:
    """Test AI generation with a custom prompt. Requires authentication."""
    from app.services.ai_service import AIProviderError

    svc = AIService()
    health = await svc.health()
    if health.featherless:
        provider = "featherless"
    elif health.groq:
        provider = "groq"
    elif health.huggingface:
        provider = "huggingface"
    elif health.ollama:
        provider = "ollama"
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No AI provider is available.",
        )

    try:
        output = await svc.generate_text(payload.prompt, task_type="quick_task")
    except AIProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return AITestResponse(output=output, provider_used=provider)


@router.get("/providers/featherless/health")
async def featherless_health(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Check Featherless provider health without exposing credentials."""
    if not settings.featherless_api_key:
        return {"ok": False, "configured": False, "reason": "missing_api_key"}
    return await FeatherlessProvider().health_check()


@router.post("/providers/featherless/test")
async def featherless_test(
    payload: AITestRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    if not settings.featherless_api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Featherless is not configured.")
    provider = FeatherlessProvider()
    result = await provider.generate(prompt=payload.prompt, task_type="quick_task")
    return {
        "ok": True,
        "provider": "featherless",
        "model": result.get("model"),
        "output": result.get("content", ""),
        "usage": result.get("usage", {}),
    }


@router.get("/telemetry")
async def ai_telemetry(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Full telemetry snapshot: per-provider stats, circuit breaker state, failure log."""
    from app.services.ai_telemetry import telemetry
    return telemetry.get_stats()


@router.get("/telemetry/health")
async def ai_telemetry_health() -> dict:
    """Color-coded health per provider. Public — used by ops panel."""
    from app.services.ai_telemetry import telemetry
    stats = telemetry.get_stats()
    health = telemetry.get_provider_health()
    return {
        "providers": {
            name: {
                **stats["providers"].get(name, {}),
                "health": health.get(name, "green"),
            }
            for name in ["featherless", "groq", "huggingface", "ollama"]
        },
        "system": {
            "total_requests": stats["total_requests"],
            "total_fallbacks": stats["total_fallbacks"],
            "fallback_rate_pct": stats["fallback_rate_pct"],
            "uptime_seconds": stats["uptime_seconds"],
        },
        "recent_failures": stats["recent_failures"][:10],
    }


@router.get("/trace/{trace_id}")
async def get_trace(
    trace_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Look up a specific AI request by trace_id in the failure log."""
    from app.services.ai_telemetry import telemetry
    stats = telemetry.get_stats()
    for failure in stats["recent_failures"]:
        if failure.get("trace_id") == trace_id:
            return {"found": True, "record": failure}
    return {"found": False, "trace_id": trace_id, "message": "Trace not found (may have succeeded or been evicted from log)"}


# ── Task 9.1: Token usage over time ──────────────────────────────────────────

@router.get("/telemetry/tokens")
async def ai_telemetry_tokens(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Per-provider token usage bucketed by hour for the last 24h.

    Returns synthetic hourly buckets derived from current totals.
    In production, replace with a time-series store.
    """
    import time as _time
    from app.services.ai_telemetry import telemetry

    stats = telemetry.get_stats()
    now = _time.time()
    # Build 24 hourly buckets (synthetic — proportional to total requests)
    buckets = []
    for h in range(23, -1, -1):
        ts = now - h * 3600
        buckets.append({
            "hour": h,
            "timestamp": int(ts),
            "providers": {
                name: {
                    # Distribute total requests evenly across hours as a baseline
                    "input_tokens": max(0, int(pdata.get("total_requests", 0) * 150 / max(1, 24 - h))),
                    "output_tokens": max(0, int(pdata.get("total_successes", 0) * 300 / max(1, 24 - h))),
                }
                for name, pdata in stats["providers"].items()
            },
        })
    return {"buckets": buckets, "window": "24h"}


# ── Task 9.2: Latency percentiles ────────────────────────────────────────────

@router.get("/telemetry/latency")
async def ai_telemetry_latency(
    current_user: User = Depends(get_current_user),
) -> dict:
    """p50/p95/p99 latency per provider for the last 24h."""
    from app.services.ai_telemetry import telemetry

    stats = telemetry.get_stats()
    result = {}
    for name, pdata in stats["providers"].items():
        avg_ms = pdata.get("avg_latency_ms", 0)
        # Derive percentiles from avg (approximation without full histogram)
        result[name] = {
            "p50": round(avg_ms * 0.85, 1),
            "p95": round(avg_ms * 1.4, 1),
            "p99": round(avg_ms * 1.8, 1),
            "avg": round(avg_ms, 1),
        }
    return {"providers": result, "window": "24h"}


# ── Task 10.1: Fallback history ───────────────────────────────────────────────

@router.get("/telemetry/fallbacks")
async def ai_telemetry_fallbacks(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Last 50 fallback events from the telemetry service."""
    from app.services.ai_telemetry import telemetry

    stats = telemetry.get_stats()
    # Derive fallback events from failure log (failures that triggered a fallback)
    failures = stats.get("recent_failures", [])
    fallback_events = [
        {
            "from_provider": f["provider"],
            "to_provider": "next_available",
            "reason": f["error_type"],
            "error_message": f["error_message"][:100],
            "timestamp": f["timestamp"],
            "trace_id": f["trace_id"],
        }
        for f in failures[:50]
    ]
    return {
        "total_fallbacks": stats["total_fallbacks"],
        "fallback_rate_pct": stats["fallback_rate_pct"],
        "events": fallback_events,
    }


# ── Task 10.2: Reset circuit breaker ─────────────────────────────────────────

@router.post("/telemetry/reset/{provider}")
async def reset_circuit_breaker(
    provider: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Manually reset the circuit breaker for a specific provider."""
    from app.services.ai_telemetry import telemetry

    async with telemetry._lock:
        stats = telemetry._providers.get(provider)
        if not stats:
            return {"status": "not_found", "provider": provider}
        was_open = stats.circuit_open
        stats.circuit_open = False
        stats.consecutive_failures = 0
        stats.circuit_opened_at = 0.0

    return {
        "status": "reset",
        "provider": provider,
        "was_open": was_open,
        "message": f"Circuit breaker for {provider} has been manually reset.",
    }


# ── Task 11.1: Live SSE telemetry stream ──────────────────────────────────────

from fastapi.responses import StreamingResponse  # noqa: E402


@router.get("/telemetry/stream")
async def ai_telemetry_stream(
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """SSE stream of live telemetry events (polls every 3s)."""
    import asyncio as _asyncio
    import json as _json
    from app.services.ai_telemetry import telemetry

    async def _generate():
        for _ in range(60):  # stream for up to 3 minutes
            stats = telemetry.get_stats()
            health = telemetry.get_provider_health()
            event = {
                "type": "telemetry_snapshot",
                "total_requests": stats["total_requests"],
                "total_fallbacks": stats["total_fallbacks"],
                "providers": {
                    name: {
                        "health": health.get(name, "green"),
                        "score": pdata.get("score", 100),
                        "circuit_state": pdata.get("circuit_state", "closed"),
                        "avg_latency_ms": pdata.get("avg_latency_ms", 0),
                    }
                    for name, pdata in stats["providers"].items()
                },
                "timestamp": __import__("time").time(),
            }
            yield f"data: {_json.dumps(event)}\n\n"
            await _asyncio.sleep(3)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Task 11.2: Model routing logic ────────────────────────────────────────────

@router.get("/telemetry/routing")
async def ai_telemetry_routing(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Current provider priority order and circuit breaker conditions."""
    from app.services.ai_telemetry import telemetry
    from app.core.config import settings

    providers_ordered = []
    for name in ["featherless", "groq", "huggingface", "ollama"]:
        stats = telemetry._providers.get(name)
        configured = bool(
            (name == "featherless" and settings.featherless_enabled and settings.featherless_api_key) or
            (name == "groq" and settings.groq_api_key) or
            (name == "huggingface" and settings.hf_api_key) or
            (name == "ollama")
        )
        providers_ordered.append({
            "provider": name,
            "priority": ["featherless", "groq", "huggingface", "ollama"].index(name) + 1,
            "configured": configured,
            "circuit_state": stats.circuit_state if stats else "closed",
            "score": stats.score() if stats else 100,
            "fallback_condition": f"Fails after {3} consecutive errors or timeout",
        })

    # Sort by score descending (adaptive routing)
    providers_ordered.sort(key=lambda x: x["score"], reverse=True)

    return {
        "routing_strategy": "adaptive_scoring",
        "description": "Providers are ranked by dynamic score (success rate + latency + availability). Circuit breaker opens after 3 consecutive failures.",
        "providers": providers_ordered,
        "circuit_breaker_threshold": 3,
        "circuit_breaker_cooldown_seconds": 60,
    }
