"""Agent scheduling — Celery Beat dispatches agent pipelines for all businesses.

This module is imported by the worker via autodiscover.  The actual Beat
schedule is defined in ``app.worker``.

The scheduled task queries all businesses and dispatches one
``run_agent_pipeline_task`` per business, creating the continuous
improvement loop:

    Collect Data → Analyze → Decide → Execute → Log → Repeat
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# The scheduling logic lives in app.tasks.run_agent_loop_task
# and is triggered by Celery Beat from app.worker.celery_app.conf.beat_schedule.
#
# This module exists as a reference point and can be extended with:
# - Business-level scheduling configuration
# - Agent health checks
# - Loop telemetry


async def get_active_business_ids() -> list[str]:
    """Return all business IDs that should participate in the agent loop.

    This can be extended to filter by:
    - Businesses with active subscriptions
    - Businesses with enough analytics data
    - Businesses not paused by the user
    """
    from sqlalchemy import select
    from app.db.session import async_session_factory
    from app.models.business import Business

    async with async_session_factory() as db:
        result = await db.execute(select(Business.id))
        return [str(row[0]) for row in result.all()]
