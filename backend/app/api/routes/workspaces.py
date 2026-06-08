"""Workspace and Project routes.

GET    /workspaces                          — list user's workspaces
POST   /workspaces                          — create workspace
GET    /workspaces/{id}/members             — list members
POST   /workspaces/{id}/invite              — invite member
GET    /workspaces/{id}/projects            — list projects
POST   /workspaces/{id}/projects            — create project
GET    /projects/{id}                       — get project detail
GET    /projects/{id}/envvars               — list env vars (masked)
POST   /projects/{id}/envvars               — set env var
DELETE /projects/{id}/envvars/{key}         — delete env var
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.usage_service import UsageService
from app.services.workspace_service import WorkspaceService

router = APIRouter()
logger = logging.getLogger(__name__)

# Simple file-based env var store for dev (per project)
_ENVVAR_DIR = Path(".envvars")
_ENVVAR_DIR.mkdir(exist_ok=True)


def _envvar_path(project_id: str) -> Path:
    return _ENVVAR_DIR / f"{project_id}.json"


def _load_envvars(project_id: str) -> dict[str, str]:
    p = _envvar_path(project_id)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def _save_envvars(project_id: str, data: dict[str, str]) -> None:
    _envvar_path(project_id).write_text(json.dumps(data))


# ── Schemas ───────────────────────────────────────────────────────────────────

class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class InviteRequest(BaseModel):
    user_id: str
    role: str = Field(default="editor", pattern="^(owner|editor|viewer)$")


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: str = Field(default="business", pattern="^(business|codebase)$")


class EnvVarSet(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    value: str = Field(max_length=2000)


# ── Workspace endpoints ───────────────────────────────────────────────────────

@router.get("/workspaces")
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    svc = WorkspaceService(db)
    workspaces = await svc.list_workspaces(str(current_user.id))
    return [w.to_dict() for w in workspaces]


@router.post("/workspaces", status_code=201)
async def create_workspace(
    payload: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = WorkspaceService(db)
    ws = await svc.create_workspace(payload.name, str(current_user.id))
    return ws.to_dict()


@router.get("/workspaces/{workspace_id}/members")
async def list_members(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    svc = WorkspaceService(db)
    ws = await svc.get_workspace(workspace_id, str(current_user.id))
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    members = await svc.list_members(workspace_id)
    return [m.to_dict() for m in members]


@router.post("/workspaces/{workspace_id}/invite", status_code=201)
async def invite_member(
    workspace_id: str,
    payload: InviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = WorkspaceService(db)
    await svc.require_write_access(workspace_id, str(current_user.id))
    member = await svc.invite_member(workspace_id, payload.user_id, payload.role)
    return member.to_dict()


# ── Project endpoints ─────────────────────────────────────────────────────────

@router.get("/workspaces/{workspace_id}/projects")
async def list_projects(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    svc = WorkspaceService(db)
    ws = await svc.get_workspace(workspace_id, str(current_user.id))
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    projects = await svc.list_projects(workspace_id)
    return [p.to_dict() for p in projects]


@router.post("/workspaces/{workspace_id}/projects", status_code=201)
async def create_project(
    workspace_id: str,
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = WorkspaceService(db)
    await svc.require_write_access(workspace_id, str(current_user.id))
    await UsageService(db).check_limit(current_user.id, "project")
    project = await svc.create_project(workspace_id, payload.name, payload.type)
    await UsageService(db).increment_usage(
        current_user.id,
        "project",
        source="project_create",
        metadata_json={"workspace_id": workspace_id, "project_id": str(project.id)},
    )
    return project.to_dict()


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = WorkspaceService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.to_dict()


# ── Env var endpoints ─────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/envvars")
async def list_envvars(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List env vars with values masked after first 4 chars."""
    data = _load_envvars(project_id)
    return [
        {"key": k, "value": v[:4] + "****" if len(v) > 4 else "****"}
        for k, v in data.items()
    ]


@router.post("/projects/{project_id}/envvars", status_code=201)
async def set_envvar(
    project_id: str,
    payload: EnvVarSet,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = _load_envvars(project_id)
    data[payload.key] = payload.value
    _save_envvars(project_id, data)
    return {"key": payload.key, "status": "set"}


@router.delete("/projects/{project_id}/envvars/{key}")
async def delete_envvar(
    project_id: str,
    key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = _load_envvars(project_id)
    if key not in data:
        raise HTTPException(status_code=404, detail="Env var not found")
    del data[key]
    _save_envvars(project_id, data)
    return {"key": key, "status": "deleted"}
