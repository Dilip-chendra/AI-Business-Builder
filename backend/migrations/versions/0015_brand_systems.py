"""Add brand_systems table.

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-07
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("brand_systems"):
        op.create_table(
            "brand_systems",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("primary_color", sa.String(20), nullable=False, server_default="#6366f1"),
            sa.Column("secondary_color", sa.String(20), nullable=False, server_default="#8b5cf6"),
            sa.Column("tone_of_voice", sa.String(50), nullable=False, server_default="professional"),
            sa.Column("target_audience", sa.String(500), nullable=False, server_default=""),
            sa.Column("industry", sa.String(100), nullable=False, server_default=""),
            sa.Column("competitors", sa.Text, nullable=False, server_default="[]"),
            sa.Column("website_url", sa.String(500), nullable=True),
            sa.Column("logo_description", sa.Text, nullable=True),
            sa.Column("extra", sa.Text, nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_brand_systems_business_id", "brand_systems", ["business_id"])


def downgrade() -> None:
    if _table_exists("brand_systems"):
        op.drop_table("brand_systems")
