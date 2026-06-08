"""Agent-related ORM models: logs, decisions, and task queue."""
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class AgentLog(UUIDMixin, TimestampMixin, Base):
    """Stores every decision and action taken by any agent."""

    __tablename__ = "agent_logs"

    business_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    agent_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    # "analysis" | "decision" | "action" | "error"
    log_type: Mapped[str] = mapped_column(String(40), nullable=False, default="decision")
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Whether the agent actually applied the change (vs. just suggested it)
    applied: Mapped[bool] = mapped_column(default=False, nullable=False)

    business = relationship("Business", back_populates="agent_logs")


class AgentTask(UUIDMixin, TimestampMixin, Base):
    """Lightweight task queue for background agent work."""

    __tablename__ = "agent_tasks"

    business_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    task_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    # "pending" | "running" | "done" | "failed"
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    business = relationship("Business", back_populates="agent_tasks")
