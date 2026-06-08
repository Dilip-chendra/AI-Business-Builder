"""Job service for managing background job execution, tracking, and results."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus, JobType

logger = logging.getLogger(__name__)


class JobService:
    """Service for managing background job lifecycle."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job(
        self,
        job_type: JobType | str,
        job_name: str,
        user_id: UUID | str | None = None,
        business_id: UUID | str | None = None,
        payload: dict | None = None,
        job_description: str | None = None,
        estimated_completion_seconds: int | None = None,
        metadata: dict | None = None,
    ) -> Job:
        """Create a new job in PENDING status."""
        if isinstance(job_type, str):
            job_type = JobType[job_type.upper()]

        job = Job(
            job_type=job_type,
            job_name=job_name,
            status=JobStatus.PENDING,
            user_id=str(user_id) if user_id else None,
            business_id=str(business_id) if business_id else None,
            payload=payload or {},
            job_description=job_description,
            estimated_completion_seconds=estimated_completion_seconds,
            metadata=metadata or {},
            progress_percent=0,
            retry_count=0,
            max_retries=3,
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        logger.info("Job created  job_id=%s  type=%s  name=%r", job.id, job_type, job_name)
        return job

    async def get_job(self, job_id: UUID | str) -> Job | None:
        """Retrieve a job by ID."""
        return await self.db.get(Job, str(job_id))

    async def get_job_by_celery_task_id(self, celery_task_id: str) -> Job | None:
        """Retrieve a job by its Celery task ID."""
        result = await self.db.execute(
            select(Job).where(Job.celery_task_id == celery_task_id)
        )
        return result.scalar_one_or_none()

    async def set_running(
        self,
        job_id: UUID | str,
        celery_task_id: str | None = None,
    ) -> Job | None:
        """Mark job as RUNNING."""
        job = await self.get_job(job_id)
        if not job:
            return None

        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow().isoformat()
        if celery_task_id:
            job.celery_task_id = celery_task_id
        job.progress_percent = 0
        job.progress_message = "Task started"

        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def update_progress(
        self,
        job_id: UUID | str,
        progress_percent: int,
        message: str | None = None,
    ) -> Job | None:
        """Update job progress."""
        job = await self.get_job(job_id)
        if not job:
            return None

        job.progress_percent = max(0, min(100, progress_percent))
        if message:
            job.progress_message = message
        job.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def mark_completed(
        self,
        job_id: UUID | str,
        result: dict | None = None,
    ) -> Job | None:
        """Mark job as COMPLETED with result."""
        job = await self.get_job(job_id)
        if not job:
            return None

        job.status = JobStatus.COMPLETED
        job.progress_percent = 100
        job.progress_message = "Task completed successfully"
        job.result = result or {}
        job.completed_at = datetime.utcnow().isoformat()
        job.error_message = None
        job.error_traceback = None

        await self.db.commit()
        await self.db.refresh(job)
        logger.info("Job completed  job_id=%s", job.id)
        return job

    async def mark_failed(
        self,
        job_id: UUID | str,
        error_message: str | None = None,
        error_traceback: str | None = None,
        should_retry: bool = False,
    ) -> Job | None:
        """Mark job as FAILED with error details."""
        job = await self.get_job(job_id)
        if not job:
            return None

        job.error_message = error_message
        job.error_traceback = error_traceback

        if should_retry and job.retry_count < job.max_retries:
            job.retry_count += 1
            job.status = JobStatus.PENDING
            # Exponential backoff: 60s, 180s, 300s
            delay_seconds = min(60 * (2 ** (job.retry_count - 1)), 300)
            job.next_retry_at = (datetime.utcnow() + timedelta(seconds=delay_seconds)).isoformat()
            job.progress_message = f"Retrying ({job.retry_count}/{job.max_retries})..."
            logger.info("Job failed, will retry  job_id=%s  retry=%d", job.id, job.retry_count)
        else:
            job.status = JobStatus.FAILED
            job.progress_message = "Task failed"
            logger.error("Job failed (no retry)  job_id=%s  error=%s", job.id, error_message)

        job.completed_at = datetime.utcnow().isoformat()
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def cancel_job(self, job_id: UUID | str) -> Job | None:
        """Cancel a pending or running job."""
        job = await self.get_job(job_id)
        if not job:
            return None

        if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
            return job  # Already completed or failed

        job.status = JobStatus.CANCELLED
        job.progress_message = "Task cancelled by user"
        job.completed_at = datetime.utcnow().isoformat()

        await self.db.commit()
        await self.db.refresh(job)
        logger.info("Job cancelled  job_id=%s", job.id)
        return job

    async def list_user_jobs(
        self,
        user_id: UUID | str,
        limit: int = 50,
        offset: int = 0,
        job_type: JobType | str | None = None,
        status_filter: JobStatus | str | None = None,
    ) -> list[Job]:
        """List jobs for a specific user."""
        query = select(Job).where(Job.user_id == str(user_id))

        if job_type:
            if isinstance(job_type, str):
                job_type = JobType[job_type.upper()]
            query = query.where(Job.job_type == job_type)

        if status_filter:
            if isinstance(status_filter, str):
                status_filter = JobStatus[status_filter.upper()]
            query = query.where(Job.status == status_filter)

        query = query.order_by(Job.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_business_jobs(
        self,
        business_id: UUID | str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        """List all jobs for a specific business."""
        result = await self.db.execute(
            select(Job)
            .where(Job.business_id == str(business_id))
            .order_by(Job.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_pending_retries(self) -> list[Job]:
        """Get jobs that are pending retry."""
        result = await self.db.execute(
            select(Job)
            .where(
                (Job.status == JobStatus.PENDING)
                & (Job.next_retry_at.isnot(None))
                & (Job.next_retry_at <= datetime.utcnow().isoformat())
            )
            .order_by(Job.created_at.asc())
            .limit(100)
        )
        return list(result.scalars().all())
