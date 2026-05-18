"""Agent pipeline endpoints."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.agents.coordinator import AgentCoordinator
from app.models.agent import AgentLog, AgentTask
from app.models.user import User
from app.services.business_service import BusinessService

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class AgentRunRequest(BaseModel):
    apply_decisions: bool = False


class AgentLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    agent_type: str
    log_type: str
    summary: str
    payload: dict
    applied: bool
    created_at: datetime


class AgentTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    task_type: str
    status: str
    payload: dict
    result: dict
    retries: int
    error_message: str | None
    created_at: datetime


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{business_id}/run")
async def run_agent_pipeline(
    business_id: UUID,
    payload: AgentRunRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run the full multi-agent pipeline for a business.

    Set ``apply_decisions=true`` to let the Optimization and Execution agents
    automatically apply changes to the landing page.
    """
    # Verify business belongs to user
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    coordinator = AgentCoordinator(db)
    result = await coordinator.run_full_pipeline(
        business_id=business_id,
        apply_decisions=payload.apply_decisions,
    )
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["error"])
    return result


@router.get("/{business_id}/logs", response_model=list[AgentLogRead])
async def list_agent_logs(
    business_id: UUID,
    agent_type: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AgentLogRead]:
    """Return agent decision/action logs for a business."""
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    query = (
        select(AgentLog)
        .where(AgentLog.business_id == business_id)
        .order_by(AgentLog.created_at.desc())
        .limit(limit)
    )
    if agent_type:
        query = query.where(AgentLog.agent_type == agent_type)
    result = await db.execute(query)
    return [AgentLogRead.model_validate(row) for row in result.scalars().all()]


@router.get("/{business_id}/tasks", response_model=list[AgentTaskRead])
async def list_agent_tasks(
    business_id: UUID,
    task_status: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AgentTaskRead]:
    """Return queued/completed agent tasks for a business."""
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    query = (
        select(AgentTask)
        .where(AgentTask.business_id == business_id)
        .order_by(AgentTask.created_at.desc())
    )
    if task_status:
        query = query.where(AgentTask.status == task_status)
    result = await db.execute(query)
    return [AgentTaskRead.model_validate(row) for row in result.scalars().all()]
