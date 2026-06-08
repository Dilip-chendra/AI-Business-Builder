"""Add auth fields to users, agent_logs, agent_tasks, experiments, variants, assignments.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _column_exists(table: str, column: str) -> bool:
    cols = [c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)]
    return column in cols


def upgrade() -> None:
    # ── Extend users table ────────────────────────────────────────────────────
    if _table_exists("users"):
        if not _column_exists("users", "hashed_password"):
            op.add_column("users", sa.Column("hashed_password", sa.String(255), nullable=True))
        if not _column_exists("users", "is_active"):
            op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"))
        if not _column_exists("users", "is_verified"):
            op.add_column("users", sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="0"))
        if not _column_exists("users", "stripe_publishable_key"):
            op.add_column("users", sa.Column("stripe_publishable_key", sa.String(255), nullable=True))

    # ── agent_logs ────────────────────────────────────────────────────────────
    if not _table_exists("agent_logs"):
        op.create_table(
            "agent_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("agent_type", sa.String(80), nullable=False),
            sa.Column("log_type", sa.String(40), nullable=False, server_default="decision"),
            sa.Column("summary", sa.String(500), nullable=False),
            sa.Column("payload", sa.Text, nullable=False, server_default="{}"),
            sa.Column("applied", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_agent_logs_business_id", "agent_logs", ["business_id"])
        op.create_index("ix_agent_logs_agent_type", "agent_logs", ["agent_type"])

    # ── agent_tasks ───────────────────────────────────────────────────────────
    if not _table_exists("agent_tasks"):
        op.create_table(
            "agent_tasks",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("task_type", sa.String(80), nullable=False),
            sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
            sa.Column("payload", sa.Text, nullable=False, server_default="{}"),
            sa.Column("result", sa.Text, nullable=False, server_default="{}"),
            sa.Column("retries", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_agent_tasks_business_id", "agent_tasks", ["business_id"])
        op.create_index("ix_agent_tasks_status", "agent_tasks", ["status"])
        op.create_index("ix_agent_tasks_task_type", "agent_tasks", ["task_type"])

    # ── experiments ───────────────────────────────────────────────────────────
    if not _table_exists("experiments"):
        op.create_table(
            "experiments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(40), nullable=False, server_default="running"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_experiments_business_id", "experiments", ["business_id"])
        op.create_index("ix_experiments_status", "experiments", ["status"])

    # ── landing_variants ──────────────────────────────────────────────────────
    if not _table_exists("landing_variants"):
        op.create_table(
            "landing_variants",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("experiment_id", sa.String(36), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("overrides", sa.Text, nullable=False, server_default="{}"),
            sa.Column("weight", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("visitors", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("conversions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_landing_variants_experiment_id", "landing_variants", ["experiment_id"])

    # ── experiment_assignments ────────────────────────────────────────────────
    if not _table_exists("experiment_assignments"):
        op.create_table(
            "experiment_assignments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("experiment_id", sa.String(36), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("variant_id", sa.String(36), sa.ForeignKey("landing_variants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("visitor_token", sa.String(255), nullable=False),
            sa.Column("converted", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_experiment_assignments_experiment_id", "experiment_assignments", ["experiment_id"])
        op.create_index("ix_experiment_assignments_variant_id", "experiment_assignments", ["variant_id"])
        op.create_index("ix_experiment_assignments_visitor_token", "experiment_assignments", ["visitor_token"])


def downgrade() -> None:
    for table in ["experiment_assignments", "landing_variants", "experiments", "agent_tasks", "agent_logs"]:
        if _table_exists(table):
            op.drop_table(table)
