from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.user import User
from app.models.workspace import Project, Workspace, WorkspaceMember
from app.services.workspace_service import WorkspaceService


@dataclass
class ActiveContextSnapshot:
    workspace_id: str | None
    business_id: str | None
    project_id: str | None


class ContextService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.workspace_service = WorkspaceService(db)

    async def _hydrate_legacy_businesses(self, user: User, workspace_id: str) -> list[Business]:
        """Attach pre-context businesses to the active workspace/project model.

        Older records were created before workspace/project linkage existed.
        We repair them lazily so the rest of the product can treat them as
        first-class entities without forcing the user to recreate data.
        """
        result = await self.db.execute(
            select(Business)
            .where(Business.user_id == user.id)
            .order_by(Business.created_at.desc())
        )
        businesses = list(result.scalars().all())
        if not businesses:
            return []

        workspace_uuid = UUID(workspace_id)
        changed = False
        workspace_projects = list(
            (
                await self.db.execute(
                    select(Project)
                    .where(Project.workspace_id == workspace_uuid)
                    .order_by(Project.created_at.asc())
                )
            ).scalars()
        )
        default_project = workspace_projects[0] if workspace_projects else None

        for business in businesses:
            if business.workspace_id is None:
                business.workspace_id = workspace_uuid
                changed = True

            if business.workspace_id and str(business.workspace_id) == workspace_id and business.project_id is None:
                project_name = f"{business.name} Project"
                project = await self.workspace_service.create_project(workspace_id, project_name, "business")
                business.project_id = project.id
                default_project = default_project or project
                changed = True
            elif business.workspace_id and str(business.workspace_id) == workspace_id and not default_project and business.project_id:
                project = await self.db.get(Project, business.project_id)
                default_project = project or default_project

            self.db.add(business)

        if changed:
            await self.db.commit()
            for business in businesses:
                await self.db.refresh(business)
        return businesses

    async def ensure_initial_context(self, user: User) -> ActiveContextSnapshot:
        workspaces = await self.workspace_service.list_workspaces(str(user.id))
        active_workspace_id = str(user.active_workspace_id) if user.active_workspace_id else None
        if not workspaces:
            workspace_name = f"{(user.full_name or 'Personal').split()[0]}'s Workspace"
            workspace = await self.workspace_service.create_workspace(workspace_name, str(user.id))
            workspaces = [workspace]
            active_workspace_id = str(workspace.id)
        elif not active_workspace_id or active_workspace_id not in {str(w.id) for w in workspaces}:
            active_workspace_id = str(workspaces[0].id)

        user_businesses = await self._hydrate_legacy_businesses(user, active_workspace_id)

        active_business_id = str(user.active_business_id) if user.active_business_id else None
        business = None
        if active_business_id:
            business = await self.db.get(Business, UUID(active_business_id))
            if not business or str(business.user_id) != str(user.id):
                business = None
                active_business_id = None

        if not business:
            stmt = (
                select(Business)
                .where(Business.user_id == user.id, Business.workspace_id == UUID(active_workspace_id))
                .order_by(Business.created_at.desc())
            )
            result = await self.db.execute(stmt)
            business = result.scalars().first()
            active_business_id = str(business.id) if business else None

        if not business and user_businesses:
            for candidate in user_businesses:
                if candidate.workspace_id and str(candidate.workspace_id) == active_workspace_id:
                    business = candidate
                    active_business_id = str(candidate.id)
                    break

        active_project_id = str(user.active_project_id) if user.active_project_id else None
        project = None
        if active_project_id:
            project = await self.db.get(Project, UUID(active_project_id))
            if not project or str(project.workspace_id) != active_workspace_id:
                project = None
                active_project_id = None

        if business and business.project_id:
            business_project = await self.db.get(Project, business.project_id)
            if business_project and str(business_project.workspace_id) == active_workspace_id:
                if active_project_id != str(business_project.id):
                    project = business_project
                    active_project_id = str(business_project.id)

        if not project and business and business.project_id:
            project = await self.db.get(Project, business.project_id)
            if project:
                active_project_id = str(project.id)

        if not project and active_workspace_id:
            result = await self.db.execute(
                select(Project)
                .where(Project.workspace_id == UUID(active_workspace_id))
                .order_by(Project.created_at.asc())
            )
            project = result.scalars().first()
            if project:
                active_project_id = str(project.id)

        if not project and active_workspace_id:
            project_name = f"{(user.full_name or 'My').split()[0]}'s Project"
            project = await self.workspace_service.create_project(active_workspace_id, project_name, "business")
            active_project_id = str(project.id)

        user.active_workspace_id = UUID(active_workspace_id) if active_workspace_id else None
        user.active_business_id = UUID(active_business_id) if active_business_id else None
        user.active_project_id = UUID(active_project_id) if active_project_id else None
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return ActiveContextSnapshot(
            workspace_id=active_workspace_id,
            business_id=active_business_id,
            project_id=active_project_id,
        )

    async def get_hierarchy(self, user: User) -> dict:
        snapshot = await self.ensure_initial_context(user)
        workspace_ids = {
            str(row.workspace_id)
            for row in (
                await self.db.execute(
                    select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
                )
            ).scalars()
        }
        workspaces = [
            ws.to_dict()
            for ws in (
                await self.db.execute(
                    select(Workspace).where(Workspace.id.in_([UUID(wid) for wid in workspace_ids]))
                )
            ).scalars()
        ] if workspace_ids else []

        businesses_stmt = select(Business).where(Business.user_id == user.id).order_by(Business.created_at.desc())
        if snapshot.workspace_id:
            businesses_stmt = businesses_stmt.where(Business.workspace_id == UUID(snapshot.workspace_id))
        businesses = [
            {
                "id": str(b.id),
                "name": b.name,
                "workspace_id": str(b.workspace_id) if b.workspace_id else None,
                "project_id": str(b.project_id) if b.project_id else None,
                "niche": b.niche,
                "headline": b.headline,
            }
            for b in (await self.db.execute(businesses_stmt)).scalars()
        ]

        projects_stmt = select(Project).order_by(Project.created_at.desc())
        if snapshot.workspace_id:
            projects_stmt = projects_stmt.where(Project.workspace_id == UUID(snapshot.workspace_id))
        else:
            projects_stmt = projects_stmt.where(False)
        projects = [p.to_dict() for p in (await self.db.execute(projects_stmt)).scalars()]

        return {
            "active": snapshot.__dict__,
            "workspaces": workspaces,
            "businesses": businesses,
            "projects": projects,
        }

    async def set_active_context(
        self,
        user: User,
        workspace_id: str | None,
        business_id: str | None,
        project_id: str | None,
    ) -> ActiveContextSnapshot:
        if workspace_id:
            workspace = await self.workspace_service.get_workspace(workspace_id, str(user.id))
            if not workspace:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        else:
            workspace = None

        business = None
        if business_id:
            business = await self.db.get(Business, UUID(business_id))
            if not business or str(business.user_id) != str(user.id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
            if workspace and business.workspace_id and str(business.workspace_id) != str(workspace.id):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Business does not belong to workspace")
            workspace_id = workspace_id or (str(business.workspace_id) if business.workspace_id else None)
            if not project_id and business.project_id:
                project_id = str(business.project_id)

        project = None
        if project_id:
            project = await self.db.get(Project, UUID(project_id))
            if not project:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
            if workspace_id and str(project.workspace_id) != workspace_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project does not belong to workspace")
            workspace_id = workspace_id or str(project.workspace_id)
            if business and business.project_id and str(business.project_id) != str(project.id):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project does not match business")

        user.active_workspace_id = UUID(workspace_id) if workspace_id else None
        user.active_business_id = UUID(business_id) if business_id else None
        user.active_project_id = UUID(project_id) if project_id else None
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return ActiveContextSnapshot(
            workspace_id=workspace_id,
            business_id=business_id,
            project_id=project_id,
        )
