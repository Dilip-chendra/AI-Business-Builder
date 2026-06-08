"""Add SaaS OAuth integration and state tables.

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("user_integrations"):
        op.create_table(
            "user_integrations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True),
            sa.Column("provider", sa.String(40), nullable=False),
            sa.Column("provider_account_id", sa.String(255), nullable=True),
            sa.Column("provider_account_name", sa.String(255), nullable=True),
            sa.Column("access_token_encrypted", sa.Text(), nullable=False),
            sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("scopes", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("status", sa.String(32), nullable=False, server_default="connected"),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("user_id", "business_id", "provider", name="uq_user_integration_provider"),
        )
        op.create_index("ix_user_integrations_user_id", "user_integrations", ["user_id"])
        op.create_index("ix_user_integrations_business_id", "user_integrations", ["business_id"])
        op.create_index("ix_user_integrations_provider", "user_integrations", ["provider"])

    if not _table_exists("oauth_states"):
        op.create_table(
            "oauth_states",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True),
            sa.Column("provider", sa.String(40), nullable=False),
            sa.Column("state_hash", sa.String(128), nullable=False, unique=True),
            sa.Column("redirect_after", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_oauth_states_user_id", "oauth_states", ["user_id"])
        op.create_index("ix_oauth_states_business_id", "oauth_states", ["business_id"])
        op.create_index("ix_oauth_states_provider", "oauth_states", ["provider"])
        op.create_index("ix_oauth_states_state_hash", "oauth_states", ["state_hash"])


def downgrade() -> None:
    if _table_exists("oauth_states"):
        op.drop_table("oauth_states")
    if _table_exists("user_integrations"):
        op.drop_table("user_integrations")
