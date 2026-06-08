"""AI Memory model — per-business brand context for AI generation."""
from __future__ import annotations

import json

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class AIMemory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ai_memory"

    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"),
        index=True, unique=True, nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    tone_of_voice: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    target_audience: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    key_differentiators: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    approved_examples: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    business = relationship("Business", foreign_keys=[business_id])
    user = relationship("User", foreign_keys=[user_id])

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "business_id": str(self.business_id),
            "user_id": str(self.user_id),
            "brand_name": self.brand_name,
            "tone_of_voice": self.tone_of_voice,
            "target_audience": self.target_audience,
            "key_differentiators": json.loads(self.key_differentiators or "[]"),
            "approved_examples": json.loads(self.approved_examples or "[]"),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
