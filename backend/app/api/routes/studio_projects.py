"""Production-style AI Studio project execution routes.

These routes expose the prompt-to-project contract used by AI Studio, while
delegating mutations to AIStudioService so chat, timeline, versions, and
workspace files stay in one durable path.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.cache import cache
from app.models.business import Business
from app.models.user import User
from app.services.ai_studio_service import AIStudioService
from app.services.code_version_service import CodeVersionService
from app.services.project_sync_service import ProjectSyncService

router = APIRouter()


class StudioExecutePromptRequest(BaseModel):
    workspace_id: str | None = None
    business_id: str = Field(..., min_length=1)
    project_id: str | None = None
    prompt: str = Field(..., min_length=2, max_length=2000)
    mode: str = "apply"
    brand_context: dict[str, Any] = Field(default_factory=dict)


async def _load_business_for_project(
    db: AsyncSession,
    current_user: User,
    *,
    business_id: str | None = None,
    project_id: str | None = None,
) -> Business:
    business: Business | None = None
    if business_id:
        try:
            business = await db.get(Business, UUID(str(business_id)))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid business_id") from exc
    elif project_id:
        try:
            project_uuid = UUID(str(project_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid project_id") from exc
        result = await db.execute(
            select(Business).where(
                Business.project_id == project_uuid,
                Business.user_id == current_user.id,
            )
        )
        business = result.scalars().first()

    if not business or str(business.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Business/project not found for this user")
    if project_id and business.project_id and str(business.project_id) != str(project_id):
        raise HTTPException(status_code=400, detail="Selected business does not belong to this project")
    return business


def _file_payload(sync_service: ProjectSyncService) -> list[dict[str, Any]]:
    sync_service.ensure_scaffold()
    root = sync_service.root.resolve()
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        files.append(
            {
                "path": rel,
                "name": path.name,
                "size": path.stat().st_size,
                "updated_at": path.stat().st_mtime,
            }
        )
    return files


@router.post("/projects/{project_id}/execute-prompt")
async def execute_project_prompt(
    project_id: str,
    payload: StudioExecutePromptRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if payload.mode != "apply":
        raise HTTPException(status_code=400, detail="Only mode='apply' is supported for durable Studio execution.")
    business = await _load_business_for_project(
        db,
        current_user,
        business_id=payload.business_id,
        project_id=payload.project_id or project_id,
    )
    try:
        result = await AIStudioService(db).run_prompt(
            str(business.id),
            payload.prompt,
            current_user,
            payload.brand_context,
        )
    except ValueError as exc:
        return {
            "status": "failed",
            "reason": str(exc),
            "logs": [
                "Prompt reached backend Studio project executor.",
                "Execution failed before a durable project mutation was applied.",
                str(exc),
            ],
            "project_id": payload.project_id or project_id,
            "business_id": str(business.id),
        }

    action = result.get("action") or {}
    if result.get("status") == "failed" or action.get("error"):
        return {
            "status": "failed",
            "reason": action.get("error") or result.get("assistant_message", {}).get("content") or "AI Studio execution failed",
            "logs": [
                "Prompt reached backend Studio project executor.",
                "AI Studio returned a failed action.",
            ],
            "project_id": payload.project_id or project_id,
            "business_id": str(business.id),
        }

    trace = action.get("orchestration") or {}
    preview_version = action.get("version_id") or trace.get("completed_at")
    changed_files = action.get("changed_files") or action.get("updated_files") or []
    changed_database_records = []
    if action.get("action_type") in {"business_profile_update", "app_builder_project_update"}:
        changed_database_records.append("business_profile")

    return {
        "status": "applied",
        "provider": action.get("provider_used") or trace.get("provider_used") or "ai_service_router",
        "changed_files": changed_files,
        "changed_database_records": changed_database_records,
        "summary": action.get("summary") or result.get("assistant_message", {}).get("content") or "AI Studio applied project changes.",
        "preview_url": action.get("preview_url") or f"/landing/{business.id}?preview=1",
        "preview_version": preview_version,
        "version_id": action.get("version_id"),
        "timestamp": trace.get("completed_at") or result.get("assistant_message", {}).get("created_at"),
        "project_id": payload.project_id or project_id,
        "business_id": str(business.id),
        "action": action,
        "timeline": trace,
        "conversation_id": result.get("conversation_id"),
    }


@router.get("/projects/{project_id}/files")
async def list_project_files(
    project_id: str,
    business_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    business = await _load_business_for_project(db, current_user, business_id=business_id, project_id=project_id)
    sync_service = ProjectSyncService(business)
    return {"project_id": project_id, "business_id": str(business.id), "files": _file_payload(sync_service)}


@router.get("/projects/{project_id}/preview")
async def get_project_preview(
    project_id: str,
    business_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    business = await _load_business_for_project(db, current_user, business_id=business_id, project_id=project_id)
    sync_service = ProjectSyncService(business)
    changed_files = sync_service.sync_business_profile()
    version = business.updated_at.isoformat() if business.updated_at else ""
    return {
        "project_id": project_id,
        "business_id": str(business.id),
        "preview_url": f"/landing/{business.id}?preview=1&v={version}",
        "preview_version": version,
        "changed_files": changed_files,
        "snapshot": {
            "headline": business.headline,
            "subheading": business.subheading,
            "cta_text": business.cta_text,
            "page_content": business.page_content or {},
        },
    }


@router.get("/projects/{project_id}/versions")
async def list_project_versions(
    project_id: str,
    business_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=250),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    business = await _load_business_for_project(db, current_user, business_id=business_id, project_id=project_id)
    versions = await CodeVersionService(db).list_versions_for_business(str(current_user.id), str(business.id), limit=limit)
    return {
        "project_id": project_id,
        "business_id": str(business.id),
        "versions": [
            {
                "id": str(version.id),
                "file_path": version.file_path,
                "source": version.source,
                "instruction": version.instruction,
                "version_number": version.version_number,
                "created_at": version.created_at.isoformat() if version.created_at else None,
                "diff_summary": version.diff_summary,
            }
            for version in versions
        ],
    }


@router.post("/projects/{project_id}/rollback/{version_id}")
async def rollback_project_version(
    project_id: str,
    version_id: str,
    business_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    business = await _load_business_for_project(db, current_user, business_id=business_id, project_id=project_id)
    svc = CodeVersionService(db)
    version = await svc.get_version(version_id)
    if not version or str(version.user_id) != str(current_user.id) or str(version.business_id) != str(business.id):
        raise HTTPException(status_code=404, detail="Version not found for this project")

    sync_service = ProjectSyncService(business)
    sync_service.ensure_scaffold()
    if version.file_path in {"studio/business-profile.json", "data/business.json", "studio/app-builder-manifest.json"}:
        raise HTTPException(status_code=400, detail="Rollback for manifest/profile versions must be performed from Version History.")

    root = sync_service.root.resolve()
    target = (root / version.file_path).resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Version file path is outside the project workspace")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(version.content, encoding="utf-8")
    restored = await svc.create_version(
        user_id=str(current_user.id),
        business_id=str(business.id),
        file_path=version.file_path,
        content=version.content,
        source="studio_project_rollback",
        instruction=f"Rolled back project file to version {version.version_number}",
    )
    await cache.delete(f"business:{business.id}:{current_user.id}")
    await cache.delete(f"landing:{business.id}")
    return {
        "status": "rolled_back",
        "project_id": project_id,
        "business_id": str(business.id),
        "file_path": version.file_path,
        "version_id": str(restored.id),
        "preview_url": f"/landing/{business.id}?preview=1&v={restored.id}",
    }
