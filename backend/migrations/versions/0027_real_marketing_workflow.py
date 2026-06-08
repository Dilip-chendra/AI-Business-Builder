"""Real marketing workflow tables and metrics reset.

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    with op.batch_alter_table("marketing_campaigns") as batch:
        if not _has_column("marketing_campaigns", "parent_campaign_id"):
            batch.add_column(sa.Column("parent_campaign_id", sa.UUID(), nullable=True))
            batch.create_index("ix_marketing_campaigns_parent_campaign_id", ["parent_campaign_id"])
        if not _has_column("marketing_campaigns", "goal"):
            batch.add_column(sa.Column("goal", sa.Text(), nullable=True))
        if not _has_column("marketing_campaigns", "budget_cents"):
            batch.add_column(sa.Column("budget_cents", sa.Integer(), nullable=False, server_default="0"))
        if not _has_column("marketing_campaigns", "created_by"):
            batch.add_column(sa.Column("created_by", sa.String(length=255), nullable=True))
        if not _has_column("marketing_campaigns", "analytics_source"):
            batch.add_column(sa.Column("analytics_source", sa.String(length=40), nullable=False, server_default="real"))

    if "campaign_assets" not in tables:
        op.create_table(
            "campaign_assets",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("campaign_id", sa.UUID(), nullable=False),
            sa.Column("platform", sa.String(length=80), nullable=False),
            sa.Column("asset_type", sa.String(length=80), nullable=False, server_default="post"),
            sa.Column("subject", sa.String(length=300), nullable=True),
            sa.Column("content", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("creative_url", sa.String(length=1000), nullable=True),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
            sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("external_post_id", sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(["campaign_id"], ["marketing_campaigns.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_campaign_assets_campaign_id", "campaign_assets", ["campaign_id"])
        op.create_index("ix_campaign_assets_platform", "campaign_assets", ["platform"])
        op.create_index("ix_campaign_assets_status", "campaign_assets", ["status"])

    if "contacts" not in tables:
        op.create_table(
            "contacts",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("business_id", sa.UUID(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=True),
            sa.Column("email", sa.String(length=320), nullable=True),
            sa.Column("phone", sa.String(length=80), nullable=True),
            sa.Column("source", sa.String(length=120), nullable=False, server_default="manual"),
            sa.Column("consent_status", sa.String(length=40), nullable=False, server_default="unknown"),
            sa.Column("segment", sa.String(length=120), nullable=True),
            sa.Column("lead_status", sa.String(length=40), nullable=False, server_default="new_lead"),
            sa.Column("lead_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_contacts_business_id", "contacts", ["business_id"])
        op.create_index("ix_contacts_email", "contacts", ["email"])
        op.create_index("ix_contacts_consent_status", "contacts", ["consent_status"])
        op.create_index("ix_contacts_lead_status", "contacts", ["lead_status"])
        op.create_index("ix_contacts_segment", "contacts", ["segment"])

    if "campaign_recipients" not in tables:
        op.create_table(
            "campaign_recipients",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("campaign_id", sa.UUID(), nullable=False),
            sa.Column("asset_id", sa.UUID(), nullable=True),
            sa.Column("contact_id", sa.UUID(), nullable=True),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("bounced_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.ForeignKeyConstraint(["asset_id"], ["campaign_assets.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["campaign_id"], ["marketing_campaigns.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_campaign_recipients_campaign_id", "campaign_recipients", ["campaign_id"])
        op.create_index("ix_campaign_recipients_asset_id", "campaign_recipients", ["asset_id"])
        op.create_index("ix_campaign_recipients_contact_id", "campaign_recipients", ["contact_id"])
        op.create_index("ix_campaign_recipients_email", "campaign_recipients", ["email"])
        op.create_index("ix_campaign_recipients_status", "campaign_recipients", ["status"])

    if "marketing_calendar_events" not in tables:
        op.create_table(
            "marketing_calendar_events",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("business_id", sa.UUID(), nullable=False),
            sa.Column("campaign_id", sa.UUID(), nullable=True),
            sa.Column("google_event_id", sa.String(length=255), nullable=True),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("platform", sa.String(length=80), nullable=True),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="scheduled"),
            sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["campaign_id"], ["marketing_campaigns.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_marketing_calendar_events_business_id", "marketing_calendar_events", ["business_id"])
        op.create_index("ix_marketing_calendar_events_campaign_id", "marketing_calendar_events", ["campaign_id"])
        op.create_index("ix_marketing_calendar_events_google_event_id", "marketing_calendar_events", ["google_event_id"])
        op.create_index("ix_marketing_calendar_events_platform", "marketing_calendar_events", ["platform"])
        op.create_index("ix_marketing_calendar_events_start_time", "marketing_calendar_events", ["start_time"])
        op.create_index("ix_marketing_calendar_events_status", "marketing_calendar_events", ["status"])

    with op.batch_alter_table("analytics_events") as batch:
        if not _has_column("analytics_events", "asset_id"):
            batch.add_column(sa.Column("asset_id", sa.UUID(), nullable=True))
            batch.create_index("ix_analytics_events_asset_id", ["asset_id"])
        if not _has_column("analytics_events", "contact_id"):
            batch.add_column(sa.Column("contact_id", sa.UUID(), nullable=True))
            batch.create_index("ix_analytics_events_contact_id", ["contact_id"])
        if not _has_column("analytics_events", "revenue_amount"):
            batch.add_column(sa.Column("revenue_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
        if not _has_column("analytics_events", "currency"):
            batch.add_column(sa.Column("currency", sa.String(length=12), nullable=False, server_default="USD"))

    bind.execute(sa.text("UPDATE marketing_campaigns SET metrics = '{}', analytics_source = 'real'"))
    bind.execute(sa.text("DELETE FROM analytics_events WHERE source IN ('email', 'social', 'google_ads', 'meta_ads') AND metadata_json LIKE '%campaign_id%'"))


def downgrade() -> None:
    op.drop_table("marketing_calendar_events")
    op.drop_table("campaign_recipients")
    op.drop_table("contacts")
    op.drop_table("campaign_assets")
