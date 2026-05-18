"""Add usage_limits table for per-user AI quotas.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("usage_limits"):
        op.create_table(
            "usage_limits",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("monthly_request_limit", sa.Integer, nullable=False, server_default="1000"),
            sa.Column("monthly_token_limit", sa.Integer, nullable=False, server_default="1000000"),
            sa.Column("requests_used_this_month", sa.Integer, nullable=False, server_default="0"),
            sa.Column("tokens_used_this_month", sa.Integer, nullable=False, server_default="0"),
            sa.Column("billing_cycle_start", sa.String(255), nullable=False),
            sa.Column("billing_cycle_end", sa.String(255), nullable=False),
            sa.Column("plan_type", sa.String(50), nullable=False, server_default="free"),
            sa.Column("is_enforced", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("hard_limit_exceeded_at", sa.String(255), nullable=True),
            sa.Column("warned_at_80_percent", sa.Boolean, nullable=False, server_default="0"),
            sa.Column("warned_at_100_percent", sa.Boolean, nullable=False, server_default="0"),
            sa.Column("metadata", sa.Text, nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_usage_limits_user_id", "usage_limits", ["user_id"])
        op.create_index("ix_usage_limits_plan_type", "usage_limits", ["plan_type"])


def downgrade() -> None:
    if _table_exists("usage_limits"):
        op.drop_table("usage_limits")
