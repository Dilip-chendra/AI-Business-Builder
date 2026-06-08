"""Marketing-related ORM models: campaigns, SEO content, ad payloads, support chats."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class MarketingCampaign(UUIDMixin, TimestampMixin, Base):
    """An email or ad campaign tied to a business."""

    __tablename__ = "marketing_campaigns"

    business_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    parent_campaign_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), index=True
    )
    # "email" | "seo_blog" | "social" | "google_ads" | "meta_ads"
    campaign_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text)
    budget_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str | None] = mapped_column(String(255))
    # "draft" | "pending_approval" | "approved" | "sent" | "rejected"
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)
    # AI-generated content payload (subject, body, ad copy, blog post, etc.)
    content: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Targeting / audience config
    targeting: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Metrics after execution
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    analytics_source: Mapped[str] = mapped_column(String(40), nullable=False, default="real")
    # Who approved/rejected
    approved_by: Mapped[str | None] = mapped_column(String(255))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    # Extended lifecycle and A/B test fields
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    scheduled_at: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str | None] = mapped_column(String(500))
    ab_test_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    variant_b_content: Mapped[str | None] = mapped_column(Text)

    business = relationship("Business", back_populates="campaigns")
    product = relationship("Product")
    assets = relationship("CampaignAsset", back_populates="campaign", cascade="all, delete-orphan")


class CampaignAsset(UUIDMixin, TimestampMixin, Base):
    """A platform-specific generated asset that belongs to one parent campaign."""

    __tablename__ = "campaign_assets"

    campaign_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(80), nullable=False, default="post")
    subject: Mapped[str | None] = mapped_column(String(300))
    content: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    creative_url: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_post_id: Mapped[str | None] = mapped_column(String(255))

    campaign = relationship("MarketingCampaign", back_populates="assets")


class Contact(UUIDMixin, TimestampMixin, Base):
    """A real audience/contact record for marketing and sales workflows."""

    __tablename__ = "contacts"

    business_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    phone: Mapped[str | None] = mapped_column(String(80))
    source: Mapped[str] = mapped_column(String(120), nullable=False, default="manual")
    consent_status: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown", index=True)
    segment: Mapped[str | None] = mapped_column(String(120), index=True)
    lead_status: Mapped[str] = mapped_column(String(40), nullable=False, default="new_lead", index=True)
    lead_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class CampaignRecipient(UUIDMixin, TimestampMixin, Base):
    """Per-recipient delivery state for a real email campaign send."""

    __tablename__ = "campaign_recipients"

    campaign_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_assets.id", ondelete="SET NULL"), index=True
    )
    contact_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bounced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class MarketingCalendarEvent(UUIDMixin, TimestampMixin, Base):
    """Calendar item for campaign scheduling, follow-ups, sales calls, and publishing."""

    __tablename__ = "marketing_calendar_events"

    business_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), index=True
    )
    google_event_id: Mapped[str | None] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    platform: Mapped[str | None] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="scheduled", index=True)


class SeoContent(UUIDMixin, TimestampMixin, Base):
    """AI-generated SEO blog post or page content."""

    __tablename__ = "seo_content"

    business_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    meta_description: Mapped[str] = mapped_column(String(500), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # "draft" | "published"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    business = relationship("Business", back_populates="seo_content")


class SupportConversation(UUIDMixin, TimestampMixin, Base):
    """Customer support chat conversation."""

    __tablename__ = "support_conversations"

    business_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    visitor_token: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # "open" | "resolved"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    messages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Summary generated by AI after conversation
    summary: Mapped[str | None] = mapped_column(Text)

    business = relationship("Business", back_populates="support_conversations")
