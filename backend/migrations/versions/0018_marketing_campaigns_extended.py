"""Extend marketing_campaigns with lifecycle fields.

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-07
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def upgrade() -> None:
    if not _column_exists("marketing_campaigns", "lifecycle_status"):
        op.add_column("marketing_campaigns", sa.Column("lifecycle_status", sa.String(40), nullable=False, server_default="draft"))
    if not _column_exists("marketing_campaigns", "scheduled_at"):
        op.add_column("marketing_campaigns", sa.Column("scheduled_at", sa.String(255), nullable=True))
    if not _column_exists("marketing_campaigns", "image_url"):
        op.add_column("marketing_campaigns", sa.Column("image_url", sa.String(500), nullable=True))
    if not _column_exists("marketing_campaigns", "ab_test_active"):
        op.add_column("marketing_campaigns", sa.Column("ab_test_active", sa.Boolean, nullable=False, server_default="0"))
    if not _column_exists("marketing_campaigns", "variant_b_content"):
        op.add_column("marketing_campaigns", sa.Column("variant_b_content", sa.Text, nullable=True))


def downgrade() -> None:
    for col in ["lifecycle_status", "scheduled_at", "image_url", "ab_test_active", "variant_b_content"]:
        if _column_exists("marketing_campaigns", col):
            op.drop_column("marketing_campaigns", col)
