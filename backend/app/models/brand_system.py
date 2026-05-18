"""Brand System model — per-business brand identity for AI generation."""
from __future__ import annotations

import json

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class BrandSystem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "brand_systems"

    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"),
        index=True, unique=True, nullable=False
    )
    primary_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#6366f1")
    secondary_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#8b5cf6")
    tone_of_voice: Mapped[str] = mapped_column(String(50), nullable=False, default="professional")
    target_audience: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    industry: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    competitors: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON array
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # JSON

    business = relationship("Business", foreign_keys=[business_id])

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "business_id": str(self.business_id),
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "tone_of_voice": self.tone_of_voice,
            "target_audience": self.target_audience,
            "industry": self.industry,
            "competitors": json.loads(self.competitors or "[]"),
            "website_url": self.website_url,
            "logo_description": self.logo_description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
