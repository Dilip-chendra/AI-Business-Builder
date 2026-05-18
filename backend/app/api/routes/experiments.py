"""A/B testing endpoints."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.business_service import BusinessService
from app.services.experiment_service import ExperimentService

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ExperimentCreate(BaseModel):
    business_id: UUID
    name: str = Field(min_length=2, max_length=160)
    description: str | None = None


class VariantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    overrides: dict = Field(
        default_factory=dict,
        description="Landing page field overrides, e.g. {headline: '...', cta_text: '...'}",
    )
    weight: int = Field(default=50, ge=1, le=100)


class AssignRequest(BaseModel):
    visitor_token: str = Field(min_length=4, max_length=255)


class ConversionRequest(BaseModel):
    visitor_token: str


class ExperimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime


class VariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    experiment_id: UUID
    name: str
    overrides: dict
    weight: int
    visitors: int
    conversions: int


# ── Authenticated endpoints ───────────────────────────────────────────────────

@router.post("", response_model=ExperimentRead, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    payload: ExperimentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExperimentRead:
    business = await BusinessService(db).get(payload.business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    exp = await ExperimentService(db).create_experiment(
        business_id=payload.business_id,
        name=payload.name,
        description=payload.description,
    )
    return ExperimentRead.model_validate(exp)


@router.get("/business/{business_id}", response_model=list[ExperimentRead])
async def list_experiments(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ExperimentRead]:
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    exps = await ExperimentService(db).list_experiments(business_id)
    return [ExperimentRead.model_validate(e) for e in exps]


@router.get("/{experiment_id}", response_model=ExperimentRead)
async def get_experiment(
    experiment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExperimentRead:
    exp = await ExperimentService(db).get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    # Verify ownership
    business = await BusinessService(db).get(exp.business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    return ExperimentRead.model_validate(exp)


@router.patch("/{experiment_id}/status", response_model=ExperimentRead)
async def update_experiment_status(
    experiment_id: UUID,
    status_value: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExperimentRead:
    exp = await ExperimentService(db).get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    business = await BusinessService(db).get(exp.business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    exp = await ExperimentService(db).update_status(experiment_id, status_value)
    return ExperimentRead.model_validate(exp)


@router.post("/{experiment_id}/variants", response_model=VariantRead, status_code=status.HTTP_201_CREATED)
async def add_variant(
    experiment_id: UUID,
    payload: VariantCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VariantRead:
    exp = await ExperimentService(db).get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    business = await BusinessService(db).get(exp.business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    variant = await ExperimentService(db).add_variant(
        experiment_id=experiment_id,
        name=payload.name,
        overrides=payload.overrides,
        weight=payload.weight,
    )
    return VariantRead.model_validate(variant)


@router.get("/{experiment_id}/variants", response_model=list[VariantRead])
async def list_variants(
    experiment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[VariantRead]:
    exp = await ExperimentService(db).get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    business = await BusinessService(db).get(exp.business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    variants = await ExperimentService(db).list_variants(experiment_id)
    return [VariantRead.model_validate(v) for v in variants]


@router.get("/{experiment_id}/results")
async def get_results(
    experiment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return conversion stats per variant."""
    exp = await ExperimentService(db).get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    business = await BusinessService(db).get(exp.business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    return await ExperimentService(db).get_results(experiment_id)


# ── Public endpoints (visitor-facing) ─────────────────────────────────────────

@router.post("/{experiment_id}/assign")
async def assign_visitor(
    experiment_id: UUID,
    payload: AssignRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Assign a visitor to a variant (deterministic, consistent hashing). Public."""
    variant = await ExperimentService(db).assign_visitor(experiment_id, payload.visitor_token)
    if not variant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No variants found")
    return {
        "variant_id": str(variant.id),
        "variant_name": variant.name,
        "overrides": variant.overrides,
    }


@router.post("/{experiment_id}/convert")
async def record_conversion(
    experiment_id: UUID,
    payload: ConversionRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Record a conversion for a visitor's assigned variant. Public."""
    recorded = await ExperimentService(db).record_conversion(experiment_id, payload.visitor_token)
    return {"recorded": recorded}
