"""AI Studio orchestration routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.ai_studio_service import AIStudioService

router = APIRouter()


class AIStudioPromptRequest(BaseModel):
    business_id: str
    instruction: str = Field(..., min_length=2, max_length=2000)
    brand_context: dict[str, Any] = Field(default_factory=dict)


class AIStudioExecuteRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=2000)
    business_id: str
    project_id: str | None = None
    brand_context: dict[str, Any] = Field(default_factory=dict)


@router.get("/{business_id}/timeline")
async def get_ai_studio_timeline(
    business_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        return await AIStudioService(db).get_timeline(business_id, current_user, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/chat")
async def run_ai_studio_prompt(
    payload: AIStudioPromptRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        return await AIStudioService(db).run_prompt(
            payload.business_id,
            payload.instruction,
            current_user,
            payload.brand_context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/execute")
async def execute_ai_studio_project_prompt(
    project_id: str,
    payload: AIStudioExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Prompt-to-app execution endpoint used by AI Studio and external project runners."""
    try:
        result = await AIStudioService(db).run_prompt(
            payload.business_id,
            payload.prompt,
            current_user,
            payload.brand_context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    action = result.get("action") or {}
    trace = action.get("orchestration") or {}
    return {
        "status": result.get("status", "completed"),
        "changed_files": action.get("changed_files") or action.get("updated_files") or [],
        "summary": action.get("summary") or result.get("assistant_message", {}).get("content") or "",
        "preview_url": action.get("preview_url") or f"/landing/{payload.business_id}?preview=1",
        "version_id": action.get("version_id"),
        "timestamp": trace.get("completed_at") or result.get("assistant_message", {}).get("created_at"),
        "project_id": payload.project_id or project_id,
        "business_id": payload.business_id,
        "provider_used": action.get("provider_used") or "ai_service_router",
        "timeline": trace,
        "conversation_id": result.get("conversation_id"),
    }
