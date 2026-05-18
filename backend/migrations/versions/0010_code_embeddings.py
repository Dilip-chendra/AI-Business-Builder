"""Add code_embeddings table for RAG codebase search.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("code_embeddings"):
        op.create_table(
            "code_embeddings",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("workspace_id", sa.String(36), nullable=False),
            sa.Column("file_path", sa.String(500), nullable=False),
            sa.Column("chunk_index", sa.Integer, nullable=False, server_default="0"),
            sa.Column("content", sa.Text, nullable=False),
            sa.Column("embedding_csv", sa.Text, nullable=False, server_default=""),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
        )
        op.create_index("ix_code_embeddings_workspace_id", "code_embeddings", ["workspace_id"])
        op.create_index("ix_code_embeddings_file_path", "code_embeddings", ["file_path"])


def downgrade() -> None:
    if _table_exists("code_embeddings"):
        op.drop_table("code_embeddings")
