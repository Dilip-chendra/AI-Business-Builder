"""Safe system diagnostics for AI execution infrastructure."""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Depends
from redis import asyncio as redis_async
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.user import User
from app.services.ai_service import AIService

router = APIRouter()


def _configured(value: str | None) -> bool:
    return bool(value and value.strip())


@router.get("/ai-health")
async def ai_execution_health(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return safe diagnostics for AI execution, storage, and browser runtime.

    This endpoint intentionally returns only booleans, statuses, model names,
    and sanitized error messages. It never returns API keys, tokens, passwords,
    OAuth secrets, or browser vault credentials.
    """
    started = time.monotonic()
    ai_health = await AIService().health()

    db_ok = False
    db_error = None
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        db_error = str(exc)

    redis_ok = False
    redis_error = None
    try:
        client = redis_async.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        try:
            await client.ping()
            redis_ok = True
        finally:
            await client.aclose()
    except Exception as exc:
        redis_error = str(exc)

    workspace_root = Path("workspace")
    uploads_root = Path("uploads")
    browser_sessions_root = Path("backend/.runtime/browser-sessions")

    storage = {
        "workspace_root": {
            "exists": workspace_root.exists(),
            "writable": _is_writable(workspace_root),
            "path": str(workspace_root.resolve()),
        },
        "uploads": {
            "exists": uploads_root.exists(),
            "writable": _is_writable(uploads_root),
            "path": str(uploads_root.resolve()),
        },
        "browser_sessions": {
            "exists": browser_sessions_root.exists(),
            "writable": _is_writable(browser_sessions_root),
            "path": str(browser_sessions_root.resolve()),
        },
    }

    providers = {
        "groq": {
            "configured": _configured(settings.groq_api_key),
            "reachable": bool(ai_health.groq),
            "model": settings.groq_model,
        },
        "huggingface": {
            "configured": _configured(settings.hf_api_key),
            "reachable": bool(ai_health.huggingface),
            "model": settings.hf_model,
            "image_model": settings.hf_image_model,
        },
        "ollama": {
            "configured": bool(settings.enable_ollama),
            "reachable": bool(ai_health.ollama),
            "model": settings.ollama_model,
            "base_url": settings.ollama_base_url,
        },
    }

    return {
        "status": "ok" if (ai_health.any_available and db_ok) else "degraded",
        "checked_at_ms": int((time.monotonic() - started) * 1000),
        "providers": providers,
        "browser_agent": {
            "enabled": bool(settings.enable_browser_agent),
            "reasoning_model": settings.browser_reasoning_model,
            "sessions_storage_ready": storage["browser_sessions"]["writable"],
        },
        "database": {"available": db_ok, "last_error": db_error},
        "redis": {
            "configured": _configured(settings.redis_url),
            "available": redis_ok,
            "last_error": redis_error,
        },
        "project_file_storage": storage,
        "rules": [
            "AI providers are reasoning engines, not live web evidence sources.",
            "Browser Agent is required for current website evidence and browser-only publishing.",
            "Success states must correspond to applied files, database records, provider responses, or saved reports.",
        ],
    }


def _is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False
