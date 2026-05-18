"""Deployment routes.

POST /deployments/preview              — create preview deployment
POST /deployments/{id}/promote         — promote to production
POST /deployments/{id}/rollback        — rollback to this deployment
GET  /deployments/{id}/log             — SSE build log stream
GET  /deployments/{id}/checks          — AI pre-deploy check results
GET  /deployments/project/{project_id} — list deployments for project
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.deployment_service import DeploymentService

router = APIRouter()
logger = logging.getLogger(__name__)


class PreviewRequest(BaseModel):
    project_id: str


class RollbackRequest(BaseModel):
    project_id: str


@router.post("/preview", status_code=201)
async def create_preview(
    payload: PreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a preview deployment for a project."""
    svc = DeploymentService(db)
    dep = await svc.create_preview(payload.project_id, str(current_user.id))
    return dep.to_dict()


@router.post("/{deployment_id}/promote")
async def promote_to_production(
    deployment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Promote a preview deployment to production."""
    svc = DeploymentService(db)
    try:
        dep = await svc.promote_to_production(deployment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return dep.to_dict()


@router.post("/{deployment_id}/rollback")
async def rollback_deployment(
    deployment_id: str,
    payload: RollbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Rollback to a specific previous deployment."""
    svc = DeploymentService(db)
    try:
        dep = await svc.rollback(payload.project_id, deployment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return dep.to_dict()


@router.get("/{deployment_id}/log")
async def stream_build_log(
    deployment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream build log as SSE."""
    svc = DeploymentService(db)
    return StreamingResponse(
        svc.stream_build_log(deployment_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{deployment_id}/checks")
async def get_deployment_checks(
    deployment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Run and return AI pre-deployment checks."""
    svc = DeploymentService(db)
    checks = await svc.run_ai_checks(deployment_id)
    return [c.to_dict() for c in checks]


@router.get("/project/{project_id}")
async def list_project_deployments(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all deployments for a project."""
    svc = DeploymentService(db)
    deployments = await svc.list_deployments(project_id)
    return [d.to_dict() for d in deployments]
