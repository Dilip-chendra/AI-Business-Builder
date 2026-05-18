"""Background Job model for tracking async task execution."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, Enum as SQLEnum
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.models.base import Base, TimestampMixin, UUIDMixin


class JobStatus(str, enum.Enum):
    """Job lifecycle states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, enum.Enum):
    """Types of background jobs supported."""
    MARKETING_CAMPAIGN = "marketing_campaign"
    SEO_BLOG = "seo_blog"
    CODE_EDIT = "code_edit"
    AGENT_PIPELINE = "agent_pipeline"
    BUSINESS_GENERATION = "business_generation"


class Job(UUIDMixin, TimestampMixin, Base):
    """Represents a background job (async task execution)."""

    __tablename__ = "jobs"

    # Foreign keys
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    business_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )

    # Job metadata
    job_type: Mapped[str] = mapped_column(SQLEnum(JobType), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        SQLEnum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    # Job configuration & input
    job_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_description: Mapped[str | None] = mapped_column(String(500))
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Progress tracking
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_message: Mapped[str | None] = mapped_column(String(500))

    # Results
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    error_traceback: Mapped[str | None] = mapped_column(Text)

    # Retry info
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_retry_at: Mapped[str | None] = mapped_column(String(255))

    # Performance tracking
    started_at: Mapped[str | None] = mapped_column(String(255))
    completed_at: Mapped[str | None] = mapped_column(String(255))
    estimated_completion_seconds: Mapped[int | None] = mapped_column(Integer)

    # Extra data (stored as 'metadata' in DB)
    extra_data: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    business = relationship("Business", foreign_keys=[business_id])

    def to_dict(self) -> dict:
        """Convert Job to dictionary for API responses."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "business_id": str(self.business_id) if self.business_id else None,
            "job_type": self.job_type.value if isinstance(self.job_type, JobType) else self.job_type,
            "status": self.status.value if isinstance(self.status, JobStatus) else self.status,
            "job_name": self.job_name,
            "job_description": self.job_description,
            "progress_percent": self.progress_percent,
            "progress_message": self.progress_message,
            "result": self.result,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "estimated_completion_seconds": self.estimated_completion_seconds,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "extra_data": self.extra_data,
            "metadata": self.extra_data,  # alias for API compatibility
        }
