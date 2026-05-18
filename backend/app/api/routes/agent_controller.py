"""AgentController and BrowserAgent API endpoints.

POST /api/v1/agent/run          — run the general autonomous agent
POST /api/v1/agent/browser/run  — run the browser research agent
GET  /api/v1/agent/status/{id}  — get run status (from DB logs)
GET  /api/v1/agent/logs/{id}    — get detailed logs for a run
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.agent import AgentLog
from app.models.user import User
from app.services.business_service import BusinessService
from app.services.usage_service import UsageService

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

class AgentRunRequest(BaseModel):
    goal: str = Field(min_length=5, max_length=1000, description="Natural language goal for the agent")
    business_id: str | None = Field(default=None, description="Optional business context UUID")
    apply_actions: bool = Field(default=False, description="If True, agent may modify business data")
    use_browser: bool = Field(default=False, description="Enable browser tools for web research")
    max_steps: int = Field(default=8, ge=1, le=10, description="Maximum agent loop steps")


class BrowserRunRequest(BaseModel):
    goal: str = Field(min_length=5, max_length=1000, description="Research goal for the browser agent")
    business_id: str | None = Field(default=None, description="Optional business context UUID")


class AgentRunResponse(BaseModel):
    run_id: str
    goal: str
    status: str
    steps: list[dict]
    result: str | None
    error: str | None
    sources: list[str] = []
    cost_summary: dict = {}
    started_at: str
    finished_at: str | None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/run", response_model=AgentRunResponse)
async def run_agent(
    payload: AgentRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentRunResponse:
    """Run the autonomous agent controller with a natural language goal.

    The agent will plan and execute steps using internal tools (and optionally
    browser tools) to achieve the goal. All actions go through the safety layer.

    Set ``apply_actions=true`` to allow the agent to modify business data.
    Set ``use_browser=true`` to enable web research capabilities.
    """
    # Verify business ownership if business_id provided
    if payload.business_id:
        business = await BusinessService(db).get(
            UUID(payload.business_id), user_id=current_user.id
        )
        if not business:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business not found or access denied",
            )

    from app.agents.controller import AgentController
    from app.agents.safety.permissions import Role

    role = Role.USER if payload.apply_actions else Role.AGENT

    controller = AgentController(
        db=db,
        role=role,
        business_id=payload.business_id,
        user_id=str(current_user.id),
        max_steps=payload.max_steps,
        use_browser=payload.use_browser,
    )

    run = await controller.run(payload.goal)

    return AgentRunResponse(
        run_id=run.run_id,
        goal=run.goal,
        status=run.status,
        steps=run.steps,
        result=run.result,
        error=run.error,
        cost_summary=run.cost_summary,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.post("/browser/run", response_model=AgentRunResponse)
async def run_browser_agent(
    payload: BrowserRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentRunResponse:
    """Run the browser research agent.

    The agent opens a headless browser, navigates to relevant sites,
    extracts data, and returns structured findings.

    Example goals:
    - "Find top 3 competitors pricing for AI SaaS tools"
    - "Research trending digital products in the productivity niche"
    - "Find SEO keywords for fitness coaching businesses"
    """
    if payload.business_id:
        business = await BusinessService(db).get(
            UUID(payload.business_id), user_id=current_user.id
        )
        if not business:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business not found or access denied",
            )

    from app.agents.browser_agent import BrowserAgent

    await UsageService(db).check_limit(current_user.id, "browser_agent_run")
    agent = BrowserAgent(
        db=db,
        business_id=payload.business_id,
        headless=True,
    )

    result = await agent.run(payload.goal)
    await UsageService(db).increment_usage(
        current_user.id,
        "browser_agent_run",
        business_id=UUID(payload.business_id) if payload.business_id else None,
        source="browser_agent",
        metadata_json={"run_id": result.run_id, "goal": payload.goal},
    )

    return AgentRunResponse(
        run_id=result.run_id,
        goal=result.goal,
        status=result.status,
        steps=result.steps,
        result=result.result,
        error=result.error,
        sources=result.sources,
        started_at=result.started_at,
        finished_at=result.finished_at,
    )


@router.get("/status/{run_id}")
async def get_run_status(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the status of an agent run by its run_id."""
    result = await db.execute(
        select(AgentLog)
        .where(AgentLog.agent_type.in_(["controller", "browser"]))
        .order_by(AgentLog.created_at.desc())
        .limit(100)
    )
    logs = result.scalars().all()

    for log in logs:
        payload = log.payload or {}
        if payload.get("run_id") == run_id:
            # Verify ownership
            if payload.get("user_id") and payload["user_id"] != str(current_user.id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
            return {
                "run_id": run_id,
                "status": payload.get("status", "unknown"),
                "goal": payload.get("goal", ""),
                "step_count": len(payload.get("steps", [])),
                "result": payload.get("result"),
                "error": payload.get("error"),
                "started_at": payload.get("started_at"),
                "finished_at": payload.get("finished_at"),
            }

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")


@router.get("/logs/{run_id}")
async def get_run_logs(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get detailed step logs for an agent run."""
    result = await db.execute(
        select(AgentLog)
        .where(AgentLog.agent_type.in_(["controller", "browser"]))
        .order_by(AgentLog.created_at.desc())
        .limit(100)
    )
    logs = result.scalars().all()

    for log in logs:
        payload = log.payload or {}
        if payload.get("run_id") == run_id:
            if payload.get("user_id") and payload["user_id"] != str(current_user.id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
            return payload

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
