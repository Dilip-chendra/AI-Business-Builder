"""Celery application — only imported by the worker process, never by the web app.

Start the worker with:
    celery -A app.worker worker --loglevel=info
Start the beat scheduler with:
    celery -A app.worker beat --loglevel=info
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _make_celery():
    """Lazily create the Celery app to avoid blocking imports in the web process."""
    from celery import Celery
    from celery.schedules import crontab
    from kombu import Exchange, Queue
    from app.core.config import settings

    app = Celery(
        "autonomous_builder",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_default_retry_delay=30,
        task_max_retries=3,
        task_default_queue="default",
        task_queues=(
            Queue("default", Exchange("default"), routing_key="default"),
            Queue("campaigns", Exchange("campaigns"), routing_key="campaigns"),
            Queue("browser", Exchange("browser"), routing_key="browser"),
            Queue("analytics", Exchange("analytics"), routing_key="analytics"),
            Queue("ai", Exchange("ai"), routing_key="ai"),
        ),
        task_routes={
            "app.tasks.generate_business_task": {"queue": "ai", "routing_key": "ai"},
            "app.tasks.run_agent_pipeline_task": {"queue": "ai", "routing_key": "ai"},
            "app.tasks.aggregate_analytics_task": {"queue": "analytics", "routing_key": "analytics"},
            "app.tasks.send_email_task": {"queue": "campaigns", "routing_key": "campaigns"},
            "app.tasks.generate_seo_blog_job_task": {"queue": "campaigns", "routing_key": "campaigns"},
            "app.tasks.generate_email_campaign_job_task": {"queue": "campaigns", "routing_key": "campaigns"},
            "app.tasks.process_code_edit_job_task": {"queue": "ai", "routing_key": "ai"},
            "app.tasks.publish_via_browser_agent_task": {"queue": "browser", "routing_key": "browser"},
        },
    )
    app.conf.beat_schedule = {
        "run-agent-loop": {
            "task": "app.tasks.run_agent_loop_task",
            "schedule": settings.agent_loop_interval_seconds,
            "args": (),
        },
    }
    app.autodiscover_tasks(["app"])
    return app


# Only instantiate when this module is the entry-point (worker process).
# The web app never imports this module directly.
celery_app = _make_celery()
