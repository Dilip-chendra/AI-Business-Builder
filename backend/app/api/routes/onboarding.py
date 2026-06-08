"""Onboarding routes.

GET  /onboarding/status          — get onboarding checklist state
POST /onboarding/complete/{step} — mark onboarding step complete
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.onboarding_service import OnboardingService

router = APIRouter()


@router.get("/status")
async def get_onboarding_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the onboarding checklist state for the current user."""
    svc = OnboardingService(db)
    return await svc.get_status(current_user)


@router.post("/complete/{step}")
async def complete_onboarding_step(
    step: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark an onboarding step as complete."""
    svc = OnboardingService(db)
    return await svc.complete_step(current_user, step)
