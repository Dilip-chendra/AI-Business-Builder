"""Add deployments and deployment_checks tables.

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("deployments"):
        op.create_table(
            "deployments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("environment", sa.String(40), nullable=False, server_default="preview"),
            sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
            sa.Column("preview_url", sa.String(500), nullable=True),
            sa.Column("triggered_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("build_log", sa.Text, nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_deployments_project_id", "deployments", ["project_id"])

    if not _table_exists("deployment_checks"):
        op.create_table(
            "deployment_checks",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("deployment_id", sa.String(36), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("check_type", sa.String(50), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pass"),
            sa.Column("message", sa.String(500), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_deployment_checks_deployment_id", "deployment_checks", ["deployment_id"])


def downgrade() -> None:
    for t in ["deployment_checks", "deployments"]:
        if _table_exists(t):
            op.drop_table(t)
