"""Add campaign_metrics table.

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-07
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("campaign_metrics"):
        op.create_table(
            "campaign_metrics",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("campaign_id", sa.String(36), sa.ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), nullable=False),
            sa.Column("recorded_at", sa.String(255), nullable=False),
            sa.Column("impressions", sa.Integer, nullable=False, server_default="0"),
            sa.Column("clicks", sa.Integer, nullable=False, server_default="0"),
            sa.Column("conversions", sa.Integer, nullable=False, server_default="0"),
            sa.Column("spend_cents", sa.Integer, nullable=False, server_default="0"),
            sa.Column("engagement", sa.Integer, nullable=False, server_default="0"),
            sa.Column("platform", sa.String(40), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_campaign_metrics_campaign_id", "campaign_metrics", ["campaign_id"])
        op.create_index("ix_campaign_metrics_recorded_at", "campaign_metrics", ["recorded_at"])


def downgrade() -> None:
    if _table_exists("campaign_metrics"):
        op.drop_table("campaign_metrics")
