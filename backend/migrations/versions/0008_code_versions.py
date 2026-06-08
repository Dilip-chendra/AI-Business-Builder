"""Add code_versions table for editor history.

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("code_versions"):
        op.create_table(
            "code_versions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True),
            sa.Column("file_path", sa.String(500), nullable=False),
            sa.Column("content", sa.Text, nullable=False),
            sa.Column("diff_summary", sa.Text, nullable=False, server_default="{}"),
            sa.Column("source", sa.String(40), nullable=False, server_default="manual"),
            sa.Column("instruction", sa.Text, nullable=True),
            sa.Column("version_number", sa.Integer, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_code_versions_user_id", "code_versions", ["user_id"])
        op.create_index("ix_code_versions_business_id", "code_versions", ["business_id"])
        op.create_index("ix_code_versions_file_path", "code_versions", ["file_path"])


def downgrade() -> None:
    if _table_exists("code_versions"):
        op.drop_table("code_versions")
