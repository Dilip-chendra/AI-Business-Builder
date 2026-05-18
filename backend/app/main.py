import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from redis import asyncio as redis_async
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

import app.db.base  # noqa: F401

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import async_session_factory
from app.tasks import campaign_scheduling_task
from app.utils.exceptions import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.utils.request_id import RequestIDMiddleware


configure_logging()
logger = logging.getLogger(__name__)


async def _check_database() -> tuple[bool, str]:
    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


async def _check_redis() -> tuple[bool, str]:
    if not settings.redis_healthcheck_enabled:
        return True, "disabled"

    client = redis_async.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    try:
        await client.ping()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)
    finally:
        await client.aclose()


async def _check_ollama() -> tuple[bool, str]:
    if not settings.should_enable_ollama:
        return False, "disabled (deployment mode)"
    try:
        import httpx

        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
        return response.is_success, "ok" if response.is_success else f"http_{response.status_code}"
    except Exception as exc:
        return False, str(exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("%s API v%s starting", settings.app_name, settings.app_version)
    logger.info("Environment: %s", settings.app_env)
    logger.info("Deployment mode: %s", settings.deployment_mode)
    logger.info("Docs: %s/api/docs", settings.backend_url)

    if settings.is_render_eval:
        logger.info("Render Free mode: heavy services disabled (Ollama, browser agent, workers)")

    scheduler_task = None
    if settings.should_run_campaign_scheduler:
        scheduler_task = asyncio.create_task(campaign_scheduling_task(), name="campaign-scheduler")

    from app.services.ai_service import AIService

    health = await AIService().health()
    if health.any_available:
        active = [provider for provider in ("featherless", "groq", "huggingface", "ollama") if getattr(health, provider)]
        logger.info("AI providers available: %s", ", ".join(active))
    else:
        logger.warning(
            "No AI providers configured. Set FEATHERLESS_API_KEY, GROQ_API_KEY or HF_API_KEY in .env, "
            "or start Ollama locally. Business generation will return 503 until a provider is available."
        )

    yield

    if scheduler_task:
        scheduler_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
                await scheduler_task


app = FastAPI(
    title=f"{settings.app_name} API",
    version=settings.app_version,
    description=(
        "AI-powered SaaS backend for business generation, products, campaigns, "
        "browser automation, billing, analytics, and orchestration."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

if settings.metrics_enabled:
    Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        excluded_handlers={"/health", "/ready"},
    ).instrument(app).expose(app, endpoint=settings.metrics_path, include_in_schema=False)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1024)
if settings.enable_trusted_host_middleware:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts or ["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_RATE_LIMIT_EXEMPT = {
    "/health",
    "/ready",
    settings.metrics_path,
    "/api/v1/payments/webhook",
    "/api/v1/billing/paypal/webhook",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
}


@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/_next/static/") or path.startswith("/uploads/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif request.method == "GET" and path.startswith("/api/v1/"):
        if any(segment in path for segment in ("/landing-page", "/products-public", "/health")):
            response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=60"
        else:
            response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path in _RATE_LIMIT_EXEMPT:
        return await call_next(request)

    if request.url.path.startswith("/api/"):
        from app.utils.rate_limit import check_rate_limit

        client_ip = request.client.host if request.client else "unknown"
        allowed = await check_rate_limit(client_ip)
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please slow down."},
                headers={"Retry-After": str(settings.rate_limit_window_seconds)},
            )

    return await call_next(request)


app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(api_router, prefix="/api/v1")

uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")
app.mount("/api/uploads", StaticFiles(directory=str(uploads_dir)), name="api-uploads")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": app.version,
        "env": settings.app_env,
    }


@app.get("/api/health", tags=["health"], include_in_schema=False)
async def api_health_check() -> dict[str, str]:
    return await health_check()


@app.get("/ready", tags=["health"])
async def readiness_check():
    database_ok, database_detail = await _check_database()
    redis_ok, redis_detail = await _check_redis()
    ollama_ok, ollama_detail = await _check_ollama()

    ready = database_ok and (redis_ok or not settings.is_production)
    payload = {
        "status": "ready" if ready else "degraded",
        "service": settings.app_name,
        "version": app.version,
        "env": settings.app_env,
        "checks": {
            "database": {"ok": database_ok, "detail": database_detail},
            "redis": {"ok": redis_ok, "detail": redis_detail},
            "ollama": {"ok": ollama_ok, "detail": ollama_detail},
        },
    }
    return JSONResponse(
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload,
    )


@app.get("/api/ready", tags=["health"], include_in_schema=False)
async def api_readiness_check():
    return await readiness_check()
