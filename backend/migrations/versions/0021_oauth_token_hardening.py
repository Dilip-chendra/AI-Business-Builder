"""Add workspace and payload columns to oauth_tokens.

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def _index_exists(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = [idx["name"] for idx in inspector.get_indexes(table)]
    return index_name in indexes


def upgrade() -> None:
    if not _table_exists("oauth_tokens"):
        return

    if not _column_exists("oauth_tokens", "workspace_id"):
        op.add_column("oauth_tokens", sa.Column("workspace_id", sa.String(36), nullable=True))
    if not _column_exists("oauth_tokens", "provider_payload"):
        op.add_column("oauth_tokens", sa.Column("provider_payload", sa.JSON(), nullable=False, server_default="{}"))
    if not _column_exists("oauth_tokens", "last_error"):
        op.add_column("oauth_tokens", sa.Column("last_error", sa.Text(), nullable=True))

    if not _index_exists("oauth_tokens", "ix_oauth_tokens_workspace_id"):
        op.create_index("ix_oauth_tokens_workspace_id", "oauth_tokens", ["workspace_id"])


def downgrade() -> None:
    if not _table_exists("oauth_tokens"):
        return

    if _index_exists("oauth_tokens", "ix_oauth_tokens_workspace_id"):
        op.drop_index("ix_oauth_tokens_workspace_id", table_name="oauth_tokens")

    for column in ["last_error", "provider_payload", "workspace_id"]:
        if _column_exists("oauth_tokens", column):
            op.drop_column("oauth_tokens", column)
