"""Add scheduled_posts table.

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-07
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("scheduled_posts"):
        op.create_table(
            "scheduled_posts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("campaign_id", sa.String(36), sa.ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), nullable=False),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("platform", sa.String(40), nullable=False),
            sa.Column("content_json", sa.Text, nullable=False, server_default="{}"),
            sa.Column("scheduled_at_utc", sa.String(255), nullable=False),
            sa.Column("timezone", sa.String(60), nullable=False, server_default="UTC"),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("published_at", sa.String(255), nullable=True),
            sa.Column("error_message", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_scheduled_posts_campaign_id", "scheduled_posts", ["campaign_id"])
        op.create_index("ix_scheduled_posts_business_id", "scheduled_posts", ["business_id"])
        op.create_index("ix_scheduled_posts_scheduled_at_utc", "scheduled_posts", ["scheduled_at_utc"])
        op.create_index("ix_scheduled_posts_status", "scheduled_posts", ["status"])


def downgrade() -> None:
    if _table_exists("scheduled_posts"):
        op.drop_table("scheduled_posts")
