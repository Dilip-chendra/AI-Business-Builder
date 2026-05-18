"""Job management API routes for tracking background task execution."""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.job import Job, JobStatus, JobType
from app.models.user import User
from app.services.job_service import JobService

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class JobCreateRequest(BaseModel):
    """Request to create a new job."""
    job_type: str = Field(description="marketing_campaign | seo_blog | code_edit | agent_pipeline | business_generation")
    job_name: str = Field(min_length=1, max_length=255)
    job_description: str | None = Field(None, max_length=500)
    business_id: str | None = None
    payload: dict = Field(default_factory=dict)
    estimated_completion_seconds: int | None = Field(None, ge=1, le=3600)


class JobStartRequest(BaseModel):
    """Request to create and dispatch a job in one call."""
    job_type: str = Field(description="marketing_campaign | seo_blog | code_edit | agent_pipeline | business_generation")
    job_name: str = Field(min_length=1, max_length=255)
    job_description: str | None = Field(None, max_length=500)
    business_id: str | None = None
    payload: dict = Field(default_factory=dict)
    estimated_completion_seconds: int | None = Field(None, ge=1, le=3600)


class JobRead(BaseModel):
    """Response model for a job."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    user_id: str | None
    business_id: str | None
    job_type: str
    status: str
    job_name: str
    job_description: str | None
    progress_percent: int
    progress_message: str | None
    result: dict
    error_message: str | None
    retry_count: int
    max_retries: int
    estimated_completion_seconds: int | None
    created_at: str | None
    updated_at: str | None
    started_at: str | None
    completed_at: str | None
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class JobListResponse(BaseModel):
    """Response for job list."""
    total: int
    jobs: list[JobRead]


class JobCancelRequest(BaseModel):
    """Request to cancel a job."""
    reason: str | None = Field(None, max_length=500)


class JobStartResponse(BaseModel):
    """Response model for create+dispatch endpoint."""
    job_id: str
    job_type: str
    status: str
    progress_percent: int
    created_at: str | None


def _dispatch_job_to_celery(job: Job) -> None:
    """Dispatch a created job to the correct Celery task."""
    try:
        from app.worker import celery_app
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Celery worker unavailable: {exc}",
        ) from exc

    task_name: str | None = None
    args: list[str] = []
    kwargs: dict = {"payload": job.payload or {}}
    task_id = f"job-{job.job_type.value}-{job.id}"

    if job.job_type == JobType.SEO_BLOG:
        if not job.business_id:
            raise HTTPException(status_code=400, detail="business_id is required for seo_blog jobs")
        task_name = "app.tasks.generate_seo_blog_job_task"
        args = [str(job.id), str(job.business_id)]
    elif job.job_type == JobType.MARKETING_CAMPAIGN:
        if not job.business_id:
            raise HTTPException(status_code=400, detail="business_id is required for marketing_campaign jobs")
        task_name = "app.tasks.generate_email_campaign_job_task"
        args = [str(job.id), str(job.business_id)]
    elif job.job_type == JobType.CODE_EDIT:
        task_name = "app.tasks.process_code_edit_job_task"
        args = [str(job.id)]
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Job type '{job.job_type.value}' is not dispatchable via /jobs/start yet",
        )

    celery_app.send_task(task_name, args=args, kwargs=kwargs, task_id=task_id)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=JobRead, status_code=201)
async def create_job(
    request: JobCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobRead:
    """Create a new background job.

    This endpoint creates a job record but does NOT dispatch the actual task.
    The caller must dispatch the task separately via their preferred method.
    """
    try:
        job_type = JobType[request.job_type.upper()]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid job_type. Must be one of: {', '.join([t.value for t in JobType])}",
        )

    job_svc = JobService(db)
    job = await job_svc.create_job(
        job_type=job_type,
        job_name=request.job_name,
        user_id=current_user.id,
        business_id=request.business_id,
        payload=request.payload,
        job_description=request.job_description,
        estimated_completion_seconds=request.estimated_completion_seconds,
    )

    return JobRead.model_validate(job.to_dict())


@router.post("/start", response_model=JobStartResponse, status_code=202)
async def start_job(
    request: JobStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobStartResponse:
    """Create and dispatch a background job in one atomic API call."""
    try:
        job_type = JobType[request.job_type.upper()]
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid job_type. Must be one of: {', '.join([t.value for t in JobType])}",
        ) from exc

    job_svc = JobService(db)
    job = await job_svc.create_job(
        job_type=job_type,
        job_name=request.job_name,
        user_id=current_user.id,
        business_id=request.business_id,
        payload=request.payload,
        job_description=request.job_description,
        estimated_completion_seconds=request.estimated_completion_seconds,
    )

    try:
        _dispatch_job_to_celery(job)
    except HTTPException:
        await job_svc.mark_failed(job.id, error_message="Failed to dispatch Celery task", should_retry=False)
        raise
    except Exception as exc:
        logger.exception("Failed to dispatch job %s", job.id)
        await job_svc.mark_failed(job.id, error_message=str(exc), should_retry=False)
        raise HTTPException(status_code=500, detail="Failed to dispatch background job") from exc

    return JobStartResponse(
        job_id=str(job.id),
        job_type=job.job_type.value,
        status=job.status.value,
        progress_percent=job.progress_percent,
        created_at=job.created_at.isoformat() if job.created_at else None,
    )


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobRead:
    """Retrieve a job by ID with current status and progress."""
    job_svc = JobService(db)
    job = await job_svc.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Verify ownership
    if job.user_id and str(job.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to access this job")

    return JobRead.model_validate(job.to_dict())


@router.get("/", response_model=JobListResponse)
async def list_user_jobs(
    job_type: str | None = Query(None, description="Filter by job type"),
    status_filter: str | None = Query(None, description="Filter by status", alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobListResponse:
    """List all jobs for the current user with optional filtering."""
    job_svc = JobService(db)

    # Validate job_type if provided
    if job_type:
        try:
            job_type_enum = JobType[job_type.upper()]
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid job_type. Must be one of: {', '.join([t.value for t in JobType])}",
            )
    else:
        job_type_enum = None

    # Validate status if provided
    if status_filter:
        try:
            status_enum = JobStatus[status_filter.upper()]
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join([s.value for s in JobStatus])}",
            )
    else:
        status_enum = None

    jobs = await job_svc.list_user_jobs(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        job_type=job_type_enum,
        status_filter=status_enum,
    )

    return JobListResponse(
        total=len(jobs),
        jobs=[JobRead.model_validate(job.to_dict()) for job in jobs],
    )


@router.get("/business/{business_id}/jobs", response_model=JobListResponse)
async def list_business_jobs(
    business_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobListResponse:
    """List all jobs for a specific business (if user owns it)."""
    from app.services.business_service import BusinessService

    # Verify ownership
    business_svc = BusinessService(db)
    business = await business_svc.get(UUID(business_id), user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    job_svc = JobService(db)
    jobs = await job_svc.list_business_jobs(business_id, limit=limit, offset=offset)

    return JobListResponse(
        total=len(jobs),
        jobs=[JobRead.model_validate(job.to_dict()) for job in jobs],
    )


@router.post("/{job_id}/cancel", response_model=JobRead)
async def cancel_job(
    job_id: str,
    request: JobCancelRequest = JobCancelRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobRead:
    """Cancel a pending or running job."""
    job_svc = JobService(db)
    job = await job_svc.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Verify ownership
    if job.user_id and str(job.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to cancel this job")

    # Check if job can be cancelled
    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {job.status.value}",
        )

    cancelled_job = await job_svc.cancel_job(job_id)
    return JobRead.model_validate(cancelled_job.to_dict())


@router.post("/{job_id}/retry", response_model=JobRead)
async def retry_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobRead:
    """Retry a failed job."""
    job_svc = JobService(db)
    job = await job_svc.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Verify ownership
    if job.user_id and str(job.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to retry this job")

    # Check if job can be retried
    if job.status not in (JobStatus.FAILED,):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only failed jobs can be retried. Current status: {job.status.value}",
        )

    # Reset job to pending
    job.status = JobStatus.PENDING
    job.error_message = None
    job.error_traceback = None
    job.progress_percent = 0
    job.progress_message = "Retrying..."
    job.retry_count = 0
    job.next_retry_at = None

    await db.commit()
    await db.refresh(job)

    logger.info("Job retry initiated  job_id=%s", job_id)
    return JobRead.model_validate(job.to_dict())
