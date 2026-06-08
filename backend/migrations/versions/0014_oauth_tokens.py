"""Add oauth_tokens table for platform integrations.

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-07
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("oauth_tokens"):
        op.create_table(
            "oauth_tokens",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("platform", sa.String(40), nullable=False),
            sa.Column("access_token_enc", sa.Text, nullable=False),
            sa.Column("refresh_token_enc", sa.Text, nullable=True),
            sa.Column("expires_at", sa.String(255), nullable=True),
            sa.Column("account_id", sa.String(255), nullable=True),
            sa.Column("account_name", sa.String(255), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="connected"),
            sa.Column("scopes", sa.Text, nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("user_id", "business_id", "platform", name="uq_oauth_token"),
        )
        op.create_index("ix_oauth_tokens_user_id", "oauth_tokens", ["user_id"])
        op.create_index("ix_oauth_tokens_business_id", "oauth_tokens", ["business_id"])
        op.create_index("ix_oauth_tokens_platform", "oauth_tokens", ["platform"])


def downgrade() -> None:
    if _table_exists("oauth_tokens"):
        op.drop_table("oauth_tokens")
