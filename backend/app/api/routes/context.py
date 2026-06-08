from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.context_service import ContextService

router = APIRouter()


class ActiveContextUpdate(BaseModel):
    workspace_id: str | None = None
    business_id: str | None = None
    project_id: str | None = None


@router.get("/active")
async def get_active_context(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await ContextService(db).get_hierarchy(current_user)


@router.put("/active")
async def set_active_context(
    payload: ActiveContextUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    snapshot = await ContextService(db).set_active_context(
        current_user,
        payload.workspace_id,
        payload.business_id,
        payload.project_id,
    )
    return {"active": snapshot.__dict__}
