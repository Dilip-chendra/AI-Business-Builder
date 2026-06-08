"""Add provider account email to user integrations."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    if not _column_exists("user_integrations", "provider_account_email"):
        op.add_column("user_integrations", sa.Column("provider_account_email", sa.String(length=255), nullable=True))


def downgrade() -> None:
    if _column_exists("user_integrations", "provider_account_email"):
        op.drop_column("user_integrations", "provider_account_email")
