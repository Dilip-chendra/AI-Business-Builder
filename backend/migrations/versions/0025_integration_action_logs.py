"""Add integration action audit log.

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _table_exists("integration_action_logs"):
        return
    op.create_table(
        "integration_action_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_integration_action_logs_user_id", "integration_action_logs", ["user_id"])
    op.create_index("ix_integration_action_logs_business_id", "integration_action_logs", ["business_id"])
    op.create_index("ix_integration_action_logs_provider", "integration_action_logs", ["provider"])
    op.create_index("ix_integration_action_logs_action", "integration_action_logs", ["action"])
    op.create_index("ix_integration_action_logs_status", "integration_action_logs", ["status"])


def downgrade() -> None:
    if _table_exists("integration_action_logs"):
        op.drop_table("integration_action_logs")
