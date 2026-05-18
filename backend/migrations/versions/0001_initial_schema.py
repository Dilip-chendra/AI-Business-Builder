"""Initial schema – users, businesses, products, analytics_events, orders.

Revision ID: 0001
Revises:
Create Date: 2026-05-03

NOTE: This migration uses IF NOT EXISTS guards so it is safe to run against
a database that was already created by SQLAlchemy's create_all().
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _uuid_col(name: str, **kwargs):
    """UUID column — native on PostgreSQL, TEXT on SQLite."""
    if _is_pg():
        from sqlalchemy.dialects.postgresql import UUID
        return sa.Column(name, UUID(as_uuid=True), **kwargs)
    return sa.Column(name, sa.String(36), **kwargs)


def _json_col(name: str, **kwargs):
    """JSONB on PostgreSQL, TEXT on SQLite."""
    if _is_pg():
        from sqlalchemy.dialects.postgresql import JSONB
        return sa.Column(name, JSONB, **kwargs)
    return sa.Column(name, sa.Text, **kwargs)


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    if _is_pg():
        op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # ── users ─────────────────────────────────────────────────────────────────
    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False, unique=True),
            sa.Column("full_name", sa.String(160), nullable=True),
            sa.Column("hashed_password", sa.String(255), nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("is_verified", sa.Boolean, nullable=False, server_default="0"),
            sa.Column("stripe_publishable_key", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── businesses ────────────────────────────────────────────────────────────
    if not _table_exists("businesses"):
        op.create_table(
            "businesses",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("niche", sa.String(140), nullable=False),
            sa.Column("description", sa.Text, nullable=False),
            sa.Column("target_audience", sa.String(220), nullable=False),
            sa.Column("monetization_model", sa.String(160), nullable=False),
            sa.Column("brand_tone", sa.String(120), nullable=False, server_default="clear and trustworthy"),
            sa.Column("headline", sa.String(180), nullable=False),
            sa.Column("subheading", sa.Text, nullable=False),
            sa.Column("product_pitch", sa.Text, nullable=False),
            sa.Column("cta_text", sa.String(80), nullable=False, server_default="Start now"),
            sa.Column("seo_title", sa.String(180), nullable=False),
            sa.Column("seo_description", sa.String(260), nullable=False),
            sa.Column("raw_ai_payload", sa.Text, nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_businesses_user_id", "businesses", ["user_id"])

    # ── products ──────────────────────────────────────────────────────────────
    if not _table_exists("products"):
        op.create_table(
            "products",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(140), nullable=False),
            sa.Column("description", sa.Text, nullable=False),
            sa.Column("price", sa.Numeric(10, 2), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="usd"),
            sa.Column("category", sa.String(100), nullable=False, server_default="digital"),
            sa.Column("image_url", sa.String(500), nullable=True),
            sa.Column("purchase_link", sa.String(500), nullable=True),
            sa.Column("stripe_price_id", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_products_business_id", "products", ["business_id"])

    # ── analytics_events ──────────────────────────────────────────────────────
    if not _table_exists("analytics_events"):
        op.create_table(
            "analytics_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
            sa.Column("event_type", sa.String(80), nullable=False),
            sa.Column("source", sa.String(120), nullable=True),
            sa.Column("value_cents", sa.Integer, nullable=False, server_default="0"),
            sa.Column("metadata_json", sa.Text, nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_analytics_events_business_id", "analytics_events", ["business_id"])
        op.create_index("ix_analytics_events_product_id", "analytics_events", ["product_id"])
        op.create_index("ix_analytics_events_event_type", "analytics_events", ["event_type"])

    # ── orders ────────────────────────────────────────────────────────────────
    if not _table_exists("orders"):
        op.create_table(
            "orders",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
            sa.Column("stripe_session_id", sa.String(255), nullable=False, unique=True),
            sa.Column("customer_email", sa.String(255), nullable=True),
            sa.Column("amount_cents", sa.Integer, nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="usd"),
            sa.Column("status", sa.String(60), nullable=False, server_default="pending"),
            sa.Column("raw_payload", sa.Text, nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_orders_business_id", "orders", ["business_id"])
        op.create_index("ix_orders_product_id", "orders", ["product_id"])
        op.create_index("ix_orders_stripe_session_id", "orders", ["stripe_session_id"], unique=True)


def downgrade() -> None:
    for table in ["orders", "analytics_events", "products", "businesses", "users"]:
        if _table_exists(table):
            op.drop_table(table)
