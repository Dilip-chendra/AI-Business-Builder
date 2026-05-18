"""Add ai_memory table for per-business brand context.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("ai_memory"):
        op.create_table(
            "ai_memory",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "business_id", sa.String(36),
                sa.ForeignKey("businesses.id", ondelete="CASCADE"),
                nullable=False, unique=True,
            ),
            sa.Column(
                "user_id", sa.String(36),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("brand_name", sa.String(255), nullable=False, server_default=""),
            sa.Column("tone_of_voice", sa.String(500), nullable=False, server_default=""),
            sa.Column("target_audience", sa.String(500), nullable=False, server_default=""),
            sa.Column("key_differentiators", sa.Text, nullable=False, server_default="[]"),
            sa.Column("approved_examples", sa.Text, nullable=False, server_default="[]"),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
        )
        op.create_index("ix_ai_memory_business_id", "ai_memory", ["business_id"])
        op.create_index("ix_ai_memory_user_id", "ai_memory", ["user_id"])


def downgrade() -> None:
    if _table_exists("ai_memory"):
        op.drop_table("ai_memory")
