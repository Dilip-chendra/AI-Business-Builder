"""OAuth token model for production integrations."""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class OAuthToken(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "oauth_tokens"
    __table_args__ = (
        UniqueConstraint("user_id", "business_id", "platform", name="uq_oauth_token"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    workspace_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="SET NULL"), index=True, nullable=True
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Platform identifier: linkedin | twitter | facebook | instagram |
    #                       google_ads | meta_ads | sendgrid | mailchimp | wordpress
    platform: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # AES-256 / Fernet encrypted token values
    access_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[str | None] = mapped_column(String(255), nullable=True)  # ISO datetime
    account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # connected | disconnected | expired
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="connected")
    scopes: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON array
    provider_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    workspace = relationship("Workspace", foreign_keys=[workspace_id])
    business = relationship("Business", foreign_keys=[business_id])

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "platform": self.platform,
            "workspace_id": str(self.workspace_id) if self.workspace_id else None,
            "business_id": str(self.business_id),
            "account_id": self.account_id,
            "account_name": self.account_name,
            "status": self.status,
            "expires_at": self.expires_at,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
