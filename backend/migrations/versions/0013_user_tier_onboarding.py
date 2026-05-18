"""Add subscription_tier and onboarding_complete to users table.

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def upgrade() -> None:
    if not _column_exists("users", "subscription_tier"):
        op.add_column("users", sa.Column("subscription_tier", sa.String(20), nullable=False, server_default="free"))
    if not _column_exists("users", "onboarding_complete"):
        op.add_column("users", sa.Column("onboarding_complete", sa.Boolean, nullable=False, server_default="0"))


def downgrade() -> None:
    for col in ["subscription_tier", "onboarding_complete"]:
        if _column_exists("users", col):
            op.drop_column("users", col)
