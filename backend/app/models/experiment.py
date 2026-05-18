"""A/B testing ORM models."""
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Experiment(UUIDMixin, TimestampMixin, Base):
    """An A/B experiment tied to a business."""

    __tablename__ = "experiments"

    business_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # "running" | "paused" | "completed"
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="running", index=True)

    business = relationship("Business", back_populates="experiments")
    variants = relationship("LandingVariant", back_populates="experiment", cascade="all, delete-orphan")
    assignments = relationship("ExperimentAssignment", back_populates="experiment", cascade="all, delete-orphan")


class LandingVariant(UUIDMixin, TimestampMixin, Base):
    """A single variant (A or B) within an experiment."""

    __tablename__ = "landing_variants"

    experiment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiments.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # Overrides for landing page fields (headline, cta_text, etc.)
    overrides: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Traffic weight 0-100 (sum of all variants in experiment should equal 100)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    visitors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conversions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    experiment = relationship("Experiment", back_populates="variants")
    assignments = relationship("ExperimentAssignment", back_populates="variant")


class ExperimentAssignment(UUIDMixin, TimestampMixin, Base):
    """Maps a visitor (by session token) to a variant."""

    __tablename__ = "experiment_assignments"

    experiment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiments.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("landing_variants.id", ondelete="CASCADE"), index=True
    )
    visitor_token: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    converted: Mapped[bool] = mapped_column(default=False, nullable=False)

    experiment = relationship("Experiment", back_populates="assignments")
    variant = relationship("LandingVariant", back_populates="assignments")
