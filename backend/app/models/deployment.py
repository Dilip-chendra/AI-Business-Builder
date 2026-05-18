"""Deployment and DeploymentCheck models."""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Deployment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deployments"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    environment: Mapped[str] = mapped_column(String(40), nullable=False, default="preview")
    # environment: "preview" | "staging" | "production"
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    # status: "pending" | "building" | "live" | "failed" | "rolled_back"
    preview_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    triggered_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    build_log: Mapped[str] = mapped_column(Text, nullable=False, default="")

    project = relationship("Project", foreign_keys=[project_id])
    triggered_by_user = relationship("User", foreign_keys=[triggered_by])
    checks = relationship("DeploymentCheck", back_populates="deployment", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "environment": self.environment,
            "status": self.status,
            "preview_url": self.preview_url,
            "triggered_by": str(self.triggered_by) if self.triggered_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DeploymentCheck(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deployment_checks"

    deployment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deployments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    check_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # check_type: "breaking_api" | "missing_env" | "security"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pass")
    # status: "pass" | "warn" | "fail"
    message: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    deployment = relationship("Deployment", back_populates="checks")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "deployment_id": str(self.deployment_id),
            "check_type": self.check_type,
            "status": self.status,
            "message": self.message,
        }
