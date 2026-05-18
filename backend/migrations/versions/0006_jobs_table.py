"""Add jobs table for background task tracking.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("jobs"):
        op.create_table(
            "jobs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=True),
            sa.Column("job_type", sa.String(40), nullable=False),
            sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
            sa.Column("celery_task_id", sa.String(255), nullable=True, unique=True),
            sa.Column("job_name", sa.String(255), nullable=False),
            sa.Column("job_description", sa.String(500), nullable=True),
            sa.Column("payload", sa.Text, nullable=False, server_default="{}"),
            sa.Column("progress_percent", sa.Integer, nullable=False, server_default="0"),
            sa.Column("progress_message", sa.String(500), nullable=True),
            sa.Column("result", sa.Text, nullable=False, server_default="{}"),
            sa.Column("error_message", sa.Text, nullable=True),
            sa.Column("error_traceback", sa.Text, nullable=True),
            sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("max_retries", sa.Integer, nullable=False, server_default="3"),
            sa.Column("next_retry_at", sa.String(255), nullable=True),
            sa.Column("started_at", sa.String(255), nullable=True),
            sa.Column("completed_at", sa.String(255), nullable=True),
            sa.Column("estimated_completion_seconds", sa.Integer, nullable=True),
            sa.Column("metadata", sa.Text, nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
        op.create_index("ix_jobs_business_id", "jobs", ["business_id"])
        op.create_index("ix_jobs_job_type", "jobs", ["job_type"])
        op.create_index("ix_jobs_status", "jobs", ["status"])
        op.create_index("ix_jobs_celery_task_id", "jobs", ["celery_task_id"])


def downgrade() -> None:
    if _table_exists("jobs"):
        op.drop_table("jobs")
