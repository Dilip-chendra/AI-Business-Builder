"""Add user_ai_settings table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("user_ai_settings"):
        op.create_table(
            "user_ai_settings",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("provider", sa.String(40), nullable=False, server_default="local"),
            sa.Column("api_key_encrypted", sa.Text(), nullable=True),
            sa.Column("model_name", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_user_ai_settings_user_id", "user_ai_settings", ["user_id"], unique=True)


def downgrade() -> None:
    if _table_exists("user_ai_settings"):
        op.drop_table("user_ai_settings")
