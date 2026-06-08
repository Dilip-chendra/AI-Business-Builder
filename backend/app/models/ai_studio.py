"""Persistent AI Studio conversation and action history."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


def _uuid() -> str:
    return str(uuid.uuid4())


class AIStudioConversation(TimestampMixin, Base):
    __tablename__ = "ai_studio_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False, default="AI Studio")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", index=True)
    context_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    messages = relationship(
        "AIStudioMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AIStudioMessage.created_at",
    )
    business = relationship("Business", foreign_keys=[business_id])
    user = relationship("User", foreign_keys=[user_id])


class AIStudioMessage(TimestampMixin, Base):
    __tablename__ = "ai_studio_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_studio_conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(40), nullable=False, default="chat", index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="completed", index=True)
    action_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    conversation = relationship("AIStudioConversation", back_populates="messages")
    business = relationship("Business", foreign_keys=[business_id])
    user = relationship("User", foreign_keys=[user_id])
