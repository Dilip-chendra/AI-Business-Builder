from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class UserAISettings(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_ai_settings"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="local")
    api_key_encrypted: Mapped[str | None] = mapped_column(String)
    model_name: Mapped[str | None] = mapped_column(String(100))

    # Relationship back to User — defined here to avoid circular import in user.py
    user = relationship("User", back_populates=None)
