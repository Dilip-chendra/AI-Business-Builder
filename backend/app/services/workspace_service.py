"""Workspace Service — CRUD, member invite, role enforcement."""
from __future__ import annotations

import logging
import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Project, Workspace, WorkspaceMember

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:60] or "workspace"


class WorkspaceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Workspace CRUD ────────────────────────────────────────────────────────

    async def create_workspace(self, name: str, owner_id: str) -> Workspace:
        slug = _slugify(name)
        # Ensure slug uniqueness
        existing = await self.db.execute(select(Workspace).where(Workspace.slug == slug))
        if existing.scalar_one_or_none():
            slug = f"{slug}-{str(owner_id)[:6]}"

        owner_uuid = UUID(str(owner_id))
        ws = Workspace(name=name, slug=slug, owner_id=owner_uuid)
        self.db.add(ws)
        # Add owner as member with owner role
        await self.db.flush()
        member = WorkspaceMember(workspace_id=ws.id, user_id=owner_uuid, role="owner")
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(ws)
        logger.info("Workspace created  id=%s  owner=%s", ws.id, owner_id)
        return ws

    async def list_workspaces(self, user_id: str) -> list[Workspace]:
        result = await self.db.execute(
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == UUID(str(user_id)))
        )
        return list(result.scalars().all())

    async def get_workspace(self, workspace_id: str, user_id: str) -> Workspace | None:
        result = await self.db.execute(
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(Workspace.id == UUID(str(workspace_id)), WorkspaceMember.user_id == UUID(str(user_id)))
        )
        return result.scalar_one_or_none()

    # ── Member management ─────────────────────────────────────────────────────

    async def list_members(self, workspace_id: str) -> list[WorkspaceMember]:
        result = await self.db.execute(
            select(WorkspaceMember).where(WorkspaceMember.workspace_id == UUID(str(workspace_id)))
        )
        return list(result.scalars().all())

    async def invite_member(self, workspace_id: str, user_id: str, role: str = "editor") -> WorkspaceMember:
        existing = await self.db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == UUID(str(workspace_id)),
                WorkspaceMember.user_id == UUID(str(user_id)),
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="User is already a member of this workspace")
        member = WorkspaceMember(workspace_id=UUID(str(workspace_id)), user_id=UUID(str(user_id)), role=role)
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def get_member_role(self, workspace_id: str, user_id: str) -> str | None:
        result = await self.db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == UUID(str(workspace_id)),
                WorkspaceMember.user_id == UUID(str(user_id)),
            )
        )
        member = result.scalar_one_or_none()
        return member.role if member else None

    async def require_write_access(self, workspace_id: str, user_id: str) -> None:
        """Raise 403 if user has Viewer role or is not a member."""
        role = await self.get_member_role(workspace_id, str(user_id))
        if role is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this workspace")
        if role == "viewer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions: Viewer role cannot perform write actions",
            )

    # ── Project CRUD ──────────────────────────────────────────────────────────

    async def create_project(self, workspace_id: str, name: str, project_type: str = "business") -> Project:
        project = Project(workspace_id=UUID(str(workspace_id)), name=name, type=project_type)
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def list_projects(self, workspace_id: str) -> list[Project]:
        result = await self.db.execute(
            select(Project).where(Project.workspace_id == UUID(str(workspace_id)))
        )
        return list(result.scalars().all())

    async def get_project(self, project_id: str) -> Project | None:
        return await self.db.get(Project, project_id)
