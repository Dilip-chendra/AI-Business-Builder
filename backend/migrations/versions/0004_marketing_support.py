"""Add marketing_campaigns, seo_content, support_conversations tables.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("marketing_campaigns"):
        op.create_table(
            "marketing_campaigns",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("campaign_type", sa.String(40), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
            sa.Column("content", sa.Text, nullable=False, server_default="{}"),
            sa.Column("targeting", sa.Text, nullable=False, server_default="{}"),
            sa.Column("metrics", sa.Text, nullable=False, server_default="{}"),
            sa.Column("approved_by", sa.String(255), nullable=True),
            sa.Column("rejection_reason", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_marketing_campaigns_business_id", "marketing_campaigns", ["business_id"])
        op.create_index("ix_marketing_campaigns_campaign_type", "marketing_campaigns", ["campaign_type"])
        op.create_index("ix_marketing_campaigns_status", "marketing_campaigns", ["status"])

    if not _table_exists("seo_content"):
        op.create_table(
            "seo_content",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("slug", sa.String(300), nullable=False),
            sa.Column("meta_description", sa.String(500), nullable=False),
            sa.Column("content_markdown", sa.Text, nullable=False),
            sa.Column("keywords", sa.Text, nullable=False, server_default="[]"),
            sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
            sa.Column("word_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_seo_content_business_id", "seo_content", ["business_id"])
        op.create_index("ix_seo_content_slug", "seo_content", ["slug"])

    if not _table_exists("support_conversations"):
        op.create_table(
            "support_conversations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("visitor_token", sa.String(255), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="open"),
            sa.Column("messages", sa.Text, nullable=False, server_default="[]"),
            sa.Column("summary", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_support_conversations_business_id", "support_conversations", ["business_id"])
        op.create_index("ix_support_conversations_visitor_token", "support_conversations", ["visitor_token"])


def downgrade() -> None:
    for table in ["support_conversations", "seo_content", "marketing_campaigns"]:
        if _table_exists(table):
            op.drop_table(table)
