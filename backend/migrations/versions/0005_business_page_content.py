"""Add page_content JSON column to businesses table.

Stores AI-generated rich landing page content:
pain_points, benefits, features, social_proof, faq,
pricing_tiers, urgency_text, trust_badges, color_scheme.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    if not _column_exists("businesses", "page_content"):
        op.add_column(
            "businesses",
            sa.Column(
                "page_content",
                sa.JSON,
                nullable=False,
                server_default="{}",
            ),
        )


def downgrade() -> None:
    if _column_exists("businesses", "page_content"):
        op.drop_column("businesses", "page_content")
