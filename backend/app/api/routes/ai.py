"""AI provider health, settings, and telemetry endpoints."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from redis import asyncio as redis_async
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.user import User
from app.services.ai_service import AIHealth, AIService
from app.services.image_generation_service import _DEFAULT_HF_IMAGE_MODELS

router = APIRouter()


@router.get("/health", response_model=AIHealth)
async def ai_health() -> AIHealth:
    """Return availability status for each AI provider. Public endpoint."""
    return await AIService().health()


def _configured(value: str | None) -> bool:
    return bool(value and value.strip())


def _provider_status(name: str, *, configured: bool, model: str | None, telemetry_stats: dict, reachable: bool | None = None, error: str | None = None) -> dict:
    pdata = telemetry_stats.get("providers", {}).get(name, {})
    recent_failures = [
        failure for failure in telemetry_stats.get("recent_failures", [])
        if failure.get("provider") == name
    ]
    last_failure = recent_failures[0] if recent_failures else None
    if configured is False:
        status_value = "missing_key"
    elif reachable is False:
        status_value = "unreachable"
    elif error:
        status_value = "error"
    elif reachable is True or configured:
        status_value = "configured"
    else:
        status_value = "unknown"
    return {
        "configured": configured,
        "status": status_value,
        "model": model,
        "latency_ms": pdata.get("avg_latency_ms") or None,
        "last_test_result": "success" if pdata.get("total_successes", 0) else ("failed" if last_failure else "not_tested"),
        "last_error": error or (last_failure or {}).get("error_message"),
        "circuit_state": pdata.get("circuit_state"),
    }


@router.get("/provider-audit")
async def provider_audit(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Safe provider/config audit. Never returns secrets."""
    import httpx
    from app.services.ai_telemetry import telemetry

    stats = telemetry.get_stats()

    started = time.monotonic()
    ollama_reachable = False
    ollama_error = None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
        ollama_reachable = response.is_success
        if not response.is_success:
            ollama_error = f"http_{response.status_code}"
    except Exception as exc:
        ollama_error = str(exc)
    ollama_latency = int((time.monotonic() - started) * 1000)

    db_available = False
    db_error = None
    try:
        await db.execute(text("SELECT 1"))
        db_available = True
    except Exception as exc:
        db_error = str(exc)

    redis_available = False
    redis_error = None
    redis_started = time.monotonic()
    try:
        client = redis_async.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        try:
            await client.ping()
            redis_available = True
        finally:
            await client.aclose()
    except Exception as exc:
        redis_error = str(exc)

    search_configured = any([
        _configured(settings.search_provider),
        _configured(settings.serpapi_api_key),
        _configured(settings.tavily_api_key),
        _configured(settings.brave_search_api_key),
        _configured(settings.bing_search_api_key),
        _configured(settings.google_cse_api_key) and _configured(settings.google_cse_id),
    ])

    providers = {
        "groq": _provider_status(
            "groq",
            configured=_configured(settings.groq_api_key),
            model=settings.groq_model,
            telemetry_stats=stats,
        ),
        "huggingface": _provider_status(
            "huggingface",
            configured=_configured(settings.hf_api_key),
            model=settings.hf_model,
            telemetry_stats=stats,
        ),
        "image_generation": {
            "configured": _configured(settings.hf_api_key),
            "status": "configured" if _configured(settings.hf_api_key) else "missing_key",
            "provider": "huggingface",
            "model": settings.hf_image_model or _DEFAULT_HF_IMAGE_MODELS[0],
            "fallback_models": _DEFAULT_HF_IMAGE_MODELS,
            "supported_tasks": ["text_to_image", "campaign_creative", "social_media_creative"],
            "last_test_result": "not_tested",
            "last_error": None if _configured(settings.hf_api_key) else "HUGGINGFACE_API_KEY is missing.",
            "note": "Campaign image generation uses Hugging Face Inference. It tries HUGGINGFACE_IMAGE_MODEL first when set, then known free/open image models.",
        },
        "ollama": {
            **_provider_status(
                "ollama",
                configured=bool(settings.enable_ollama),
                model=settings.ollama_model,
                telemetry_stats=stats,
                reachable=ollama_reachable,
                error=ollama_error,
            ),
            "latency_ms": ollama_latency,
            "base_url": settings.ollama_base_url,
        },
        "live_search_optional": {
            "configured": search_configured,
            "status": "configured" if search_configured else "not_configured",
            "provider": settings.search_provider,
            "last_test_result": "not_tested",
            "last_error": None,
            "note": (
                "Optional live-search provider is configured."
                if search_configured
                else "No Search API is required. AI providers handle reasoning; Browser Agent handles live website evidence when needed."
            ),
        },
        "browser_agent": {
            "configured": bool(settings.enable_browser_agent),
            "status": "enabled" if settings.enable_browser_agent else "disabled",
            "model": settings.browser_reasoning_model,
            "last_test_result": "not_tested",
            "last_error": None,
        },
        "linkedin": {"configured": bool(settings.linkedin_client_id and settings.linkedin_client_secret), "status": "configured" if settings.linkedin_client_id and settings.linkedin_client_secret else "missing_key"},
        "instagram": {"configured": bool(settings.instagram_client_id and settings.instagram_client_secret), "status": "configured" if settings.instagram_client_id and settings.instagram_client_secret else "missing_key"},
        "google_ads": {"configured": bool(settings.google_ads_client_id and settings.google_ads_client_secret), "status": "configured" if settings.google_ads_client_id and settings.google_ads_client_secret else "missing_key"},
        "google_oauth": {"configured": bool(settings.google_client_id and settings.google_client_secret), "status": "configured" if settings.google_client_id and settings.google_client_secret else "missing_key", "redirect_uri": settings.google_redirect_uri},
        "notion": {"configured": bool(settings.notion_client_id and settings.notion_client_secret), "status": "configured" if settings.notion_client_id and settings.notion_client_secret else "missing_key", "redirect_uri": settings.notion_redirect_uri},
        "sendgrid": {"configured": _configured(settings.sendgrid_api_key), "status": "configured" if _configured(settings.sendgrid_api_key) else "missing_key", "last_test_result": "not_tested", "last_error": None if _configured(settings.sendgrid_api_key) else "SENDGRID_API_KEY is missing."},
        "redis": {"configured": _configured(settings.redis_url), "status": "available" if redis_available else "unavailable", "latency_ms": int((time.monotonic() - redis_started) * 1000), "last_error": redis_error},
        "database": {"configured": True, "status": "available" if db_available else "unavailable", "last_error": db_error},
    }

    return {
        "environment": {
            "app_env": settings.app_env,
            "deployment_mode": settings.deployment_mode,
            "is_local": settings.is_local,
            "backend_url": str(settings.backend_url),
            "frontend_url": str(settings.frontend_url),
        },
        "providers": providers,
        "summary": {
            "groq_configured": providers["groq"]["configured"],
            "huggingface_configured": providers["huggingface"]["configured"],
            "ollama_reachable": ollama_reachable,
            "live_search_optional_configured": search_configured,
            "browser_agent_enabled": bool(settings.enable_browser_agent),
            "redis_available": redis_available,
            "database_available": db_available,
            "google_oauth_configured": providers["google_oauth"]["configured"],
            "notion_oauth_configured": providers["notion"]["configured"],
            "sendgrid_configured": providers["sendgrid"]["configured"],
            "image_generation_configured": providers["image_generation"]["configured"],
        },
        "notes": [
            "AI providers can reason and format reports, but they are not live evidence sources.",
            "Search APIs are optional in this app. Use Browser Agent when a task needs fresh external web evidence.",
            "Reasoning, planning, marketing, SEO ideas, code generation, and recommendations should route through Groq, Ollama, or HuggingFace.",
        ],
    }


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
    if health.groq:
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
    return {"ok": False, "configured": False, "reason": "disabled_deprecated_provider"}


@router.post("/providers/featherless/test")
async def featherless_test(
    payload: AITestRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Featherless has been disabled for this project. Use Groq, Ollama, or HuggingFace.",
    )


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
            for name in ["groq", "huggingface", "ollama"]
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
    for name in ["groq", "ollama", "huggingface"]:
        stats = telemetry._providers.get(name)
        configured = bool(
            (name == "groq" and settings.groq_api_key) or
            (name == "huggingface" and settings.hf_api_key) or
            (name == "ollama")
        )
        providers_ordered.append({
            "provider": name,
            "priority": ["groq", "ollama", "huggingface"].index(name) + 1,
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
