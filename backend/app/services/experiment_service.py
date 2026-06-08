"""A/B testing service — experiments, variants, assignments, and results."""
from __future__ import annotations

import hashlib
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experiment import Experiment, ExperimentAssignment, LandingVariant

logger = logging.getLogger(__name__)


class ExperimentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Experiment CRUD ───────────────────────────────────────────────────────

    async def create_experiment(
        self,
        business_id: UUID,
        name: str,
        description: str | None = None,
    ) -> Experiment:
        exp = Experiment(business_id=business_id, name=name, description=description)
        self.db.add(exp)
        await self.db.commit()
        await self.db.refresh(exp)
        return exp

    async def list_experiments(self, business_id: UUID) -> list[Experiment]:
        result = await self.db.execute(
            select(Experiment)
            .where(Experiment.business_id == business_id)
            .order_by(Experiment.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_experiment(self, experiment_id: UUID) -> Experiment | None:
        return await self.db.get(Experiment, experiment_id)

    async def update_status(self, experiment_id: UUID, status: str) -> Experiment | None:
        exp = await self.get_experiment(experiment_id)
        if not exp:
            return None
        exp.status = status
        await self.db.commit()
        await self.db.refresh(exp)
        return exp

    # ── Variant CRUD ──────────────────────────────────────────────────────────

    async def add_variant(
        self,
        experiment_id: UUID,
        name: str,
        overrides: dict,
        weight: int = 50,
    ) -> LandingVariant:
        variant = LandingVariant(
            experiment_id=experiment_id,
            name=name,
            overrides=overrides,
            weight=weight,
        )
        self.db.add(variant)
        await self.db.commit()
        await self.db.refresh(variant)
        return variant

    async def list_variants(self, experiment_id: UUID) -> list[LandingVariant]:
        result = await self.db.execute(
            select(LandingVariant).where(LandingVariant.experiment_id == experiment_id)
        )
        return list(result.scalars().all())

    # ── Assignment (traffic splitting) ────────────────────────────────────────

    async def assign_visitor(
        self, experiment_id: UUID, visitor_token: str
    ) -> LandingVariant | None:
        """Deterministically assign a visitor to a variant using consistent hashing.

        The same visitor always gets the same variant for the duration of the
        experiment, ensuring a consistent experience.
        """
        # Check for existing assignment
        existing = await self.db.execute(
            select(ExperimentAssignment).where(
                ExperimentAssignment.experiment_id == experiment_id,
                ExperimentAssignment.visitor_token == visitor_token,
            )
        )
        assignment = existing.scalar_one_or_none()
        if assignment:
            return await self.db.get(LandingVariant, assignment.variant_id)

        variants = await self.list_variants(experiment_id)
        if not variants:
            return None

        # Consistent hash → bucket 0-99
        digest = int(hashlib.md5(f"{experiment_id}:{visitor_token}".encode()).hexdigest(), 16)
        bucket = digest % 100

        # Walk variants by cumulative weight
        cumulative = 0
        chosen = variants[-1]
        for v in variants:
            cumulative += v.weight
            if bucket < cumulative:
                chosen = v
                break

        # Persist assignment
        new_assignment = ExperimentAssignment(
            experiment_id=experiment_id,
            variant_id=chosen.id,
            visitor_token=visitor_token,
        )
        self.db.add(new_assignment)
        # Increment visitor count
        chosen.visitors += 1
        await self.db.commit()
        return chosen

    async def record_conversion(self, experiment_id: UUID, visitor_token: str) -> bool:
        """Mark a visitor as converted and increment the variant's counter."""
        result = await self.db.execute(
            select(ExperimentAssignment).where(
                ExperimentAssignment.experiment_id == experiment_id,
                ExperimentAssignment.visitor_token == visitor_token,
                ExperimentAssignment.converted == False,  # noqa: E712
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            return False
        assignment.converted = True
        variant = await self.db.get(LandingVariant, assignment.variant_id)
        if variant:
            variant.conversions += 1
        await self.db.commit()
        return True

    async def get_results(self, experiment_id: UUID) -> list[dict]:
        """Return conversion stats per variant."""
        variants = await self.list_variants(experiment_id)
        results = []
        for v in variants:
            rate = v.conversions / v.visitors if v.visitors else 0.0
            results.append({
                "variant_id": str(v.id),
                "name": v.name,
                "visitors": v.visitors,
                "conversions": v.conversions,
                "conversion_rate": round(rate, 4),
                "overrides": v.overrides,
            })
        return results
