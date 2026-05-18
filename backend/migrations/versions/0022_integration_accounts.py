"""Add integration account vault table.

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _table_exists("integration_accounts"):
        return

    op.create_table(
        "integration_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("platform", sa.String(40), nullable=False),
        sa.Column("login_identifier_enc", sa.Text(), nullable=True),
        sa.Column("password_enc", sa.Text(), nullable=True),
        sa.Column("phone_enc", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="disconnected"),
        sa.Column("last_active_at", sa.String(64), nullable=True),
        sa.Column("last_tested_at", sa.String(64), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "business_id", "platform", name="uq_integration_account"),
    )
    op.create_index("ix_integration_accounts_user_id", "integration_accounts", ["user_id"])
    op.create_index("ix_integration_accounts_workspace_id", "integration_accounts", ["workspace_id"])
    op.create_index("ix_integration_accounts_business_id", "integration_accounts", ["business_id"])
    op.create_index("ix_integration_accounts_platform", "integration_accounts", ["platform"])


def downgrade() -> None:
    if _table_exists("integration_accounts"):
        op.drop_table("integration_accounts")
