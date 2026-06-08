"""Add persistent AI Studio conversation history.

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("ai_studio_conversations"):
        op.create_table(
            "ai_studio_conversations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(180), nullable=False, server_default="AI Studio"),
            sa.Column("status", sa.String(40), nullable=False, server_default="active"),
            sa.Column("context_snapshot", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_ai_studio_conversations_user_id", "ai_studio_conversations", ["user_id"])
        op.create_index("ix_ai_studio_conversations_business_id", "ai_studio_conversations", ["business_id"])
        op.create_index("ix_ai_studio_conversations_status", "ai_studio_conversations", ["status"])

    if not _table_exists("ai_studio_messages"):
        op.create_table(
            "ai_studio_messages",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "conversation_id",
                sa.String(36),
                sa.ForeignKey("ai_studio_conversations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("message_type", sa.String(40), nullable=False, server_default="chat"),
            sa.Column("status", sa.String(40), nullable=False, server_default="completed"),
            sa.Column("action_type", sa.String(80), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_ai_studio_messages_conversation_id", "ai_studio_messages", ["conversation_id"])
        op.create_index("ix_ai_studio_messages_user_id", "ai_studio_messages", ["user_id"])
        op.create_index("ix_ai_studio_messages_business_id", "ai_studio_messages", ["business_id"])
        op.create_index("ix_ai_studio_messages_role", "ai_studio_messages", ["role"])
        op.create_index("ix_ai_studio_messages_message_type", "ai_studio_messages", ["message_type"])
        op.create_index("ix_ai_studio_messages_status", "ai_studio_messages", ["status"])
        op.create_index("ix_ai_studio_messages_action_type", "ai_studio_messages", ["action_type"])


def downgrade() -> None:
    if _table_exists("ai_studio_messages"):
        op.drop_table("ai_studio_messages")
    if _table_exists("ai_studio_conversations"):
        op.drop_table("ai_studio_conversations")
