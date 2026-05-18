"""Onboarding Service — step tracking and welcome email trigger."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = logging.getLogger(__name__)

ONBOARDING_STEPS = [
    "complete_profile",
    "create_first_business",
    "generate_first_campaign",
    "explore_code_editor",
]


class OnboardingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_status(self, user: User) -> dict:
        """Return the onboarding checklist state for a user."""
        # Store completed steps in user's extra JSON field if available,
        # otherwise derive from existing data
        completed_steps: list[str] = []

        # Check profile completion
        if user.full_name:
            completed_steps.append("complete_profile")

        # Check if user has businesses (requires a separate query in real impl)
        # For now we return the stored state
        extra = getattr(user, "extra_data", {}) or {}
        stored = extra.get("onboarding_steps", [])
        for step in stored:
            if step not in completed_steps:
                completed_steps.append(step)

        all_done = all(s in completed_steps for s in ONBOARDING_STEPS)

        return {
            "steps": [
                {
                    "id": step,
                    "label": step.replace("_", " ").title(),
                    "completed": step in completed_steps,
                }
                for step in ONBOARDING_STEPS
            ],
            "completed_count": len(completed_steps),
            "total_count": len(ONBOARDING_STEPS),
            "all_complete": all_done,
            "onboarding_complete": getattr(user, "onboarding_complete", False),
        }

    async def complete_step(self, user: User, step: str) -> dict:
        """Mark an onboarding step as complete."""
        if step not in ONBOARDING_STEPS:
            return {"error": f"Unknown step: {step}"}

        extra = getattr(user, "extra_data", {}) or {}
        steps = extra.get("onboarding_steps", [])
        if step not in steps:
            steps.append(step)
        extra["onboarding_steps"] = steps

        # Check if all steps done
        if all(s in steps for s in ONBOARDING_STEPS):
            if hasattr(user, "onboarding_complete"):
                user.onboarding_complete = True  # type: ignore[assignment]
            logger.info("Onboarding complete  user_id=%s", user.id)
            await self._send_completion_email(user)

        await self.db.commit()
        logger.info("Onboarding step completed  user_id=%s  step=%s", user.id, step)
        return await self.get_status(user)

    async def _send_completion_email(self, user: User) -> None:
        """Send onboarding completion notification."""
        try:
            from app.services.email_service import EmailService
            await EmailService().send_generic(
                to=user.email,
                subject="You're all set!",
                body=f"Hi {user.full_name or 'there'},\n\nYou've completed the onboarding checklist. You're ready to build with AI!\n\nThe AI Business Builder Team",
            )
        except Exception as exc:
            logger.warning("Failed to send onboarding completion email: %s", exc)
