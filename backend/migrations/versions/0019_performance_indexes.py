"""Add performance indexes for slow queries.

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-11
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_index("ix_mc_business_created", "marketing_campaigns", ["business_id", sa.text("created_at DESC")], if_not_exists=True)
    op.create_index("ix_ae_business_created", "analytics_events", ["business_id", sa.text("created_at DESC")], if_not_exists=True)
    op.create_index("ix_sp_scheduled_status", "scheduled_posts", ["scheduled_at_utc", "status"], if_not_exists=True)
    op.create_index("ix_cm_campaign_recorded", "campaign_metrics", ["campaign_id", sa.text("recorded_at DESC")], if_not_exists=True)

def downgrade() -> None:
    op.drop_index("ix_mc_business_created", table_name="marketing_campaigns", if_exists=True)
    op.drop_index("ix_ae_business_created", table_name="analytics_events", if_exists=True)
    op.drop_index("ix_sp_scheduled_status", table_name="scheduled_posts", if_exists=True)
    op.drop_index("ix_cm_campaign_recorded", table_name="campaign_metrics", if_exists=True)
