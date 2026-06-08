"""Add active context columns and billing foundation tables.

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def _index_exists(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = [idx["name"] for idx in inspector.get_indexes(table)]
    return index_name in indexes


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    if not _column_exists(table, column.name):
        op.add_column(table, column)


def _create_index_if_missing(table: str, index_name: str, columns: list[str], unique: bool = False) -> None:
    if not _index_exists(table, index_name):
        op.create_index(index_name, table, columns, unique=unique)


def upgrade() -> None:
    # users
    _add_column_if_missing("users", sa.Column("active_workspace_id", sa.String(36), nullable=True))
    _add_column_if_missing("users", sa.Column("active_business_id", sa.String(36), nullable=True))
    _add_column_if_missing("users", sa.Column("active_project_id", sa.String(36), nullable=True))
    _create_index_if_missing("users", "ix_users_active_workspace_id", ["active_workspace_id"])
    _create_index_if_missing("users", "ix_users_active_business_id", ["active_business_id"])
    _create_index_if_missing("users", "ix_users_active_project_id", ["active_project_id"])

    # businesses
    _add_column_if_missing("businesses", sa.Column("workspace_id", sa.String(36), nullable=True))
    _add_column_if_missing("businesses", sa.Column("project_id", sa.String(36), nullable=True))
    _add_column_if_missing("businesses", sa.Column("page_content", sa.JSON(), nullable=False, server_default="{}"))
    _create_index_if_missing("businesses", "ix_businesses_workspace_id", ["workspace_id"])
    _create_index_if_missing("businesses", "ix_businesses_project_id", ["project_id"])

    # products
    _add_column_if_missing("products", sa.Column("project_id", sa.String(36), nullable=True))
    _add_column_if_missing("products", sa.Column("status", sa.String(32), nullable=False, server_default="draft"))
    _add_column_if_missing("products", sa.Column("product_type", sa.String(32), nullable=False, server_default="digital"))
    _add_column_if_missing("products", sa.Column("payment_provider", sa.String(32), nullable=True))
    _add_column_if_missing("products", sa.Column("paypal_product_id", sa.String(255), nullable=True))
    _add_column_if_missing("products", sa.Column("paypal_plan_id", sa.String(255), nullable=True))
    _add_column_if_missing("products", sa.Column("paypal_checkout_url", sa.String(500), nullable=True))
    _add_column_if_missing("products", sa.Column("billing_type", sa.String(32), nullable=False, server_default="one_time"))
    _create_index_if_missing("products", "ix_products_project_id", ["project_id"])

    # marketing campaigns
    _add_column_if_missing("marketing_campaigns", sa.Column("product_id", sa.String(36), nullable=True))
    _add_column_if_missing("marketing_campaigns", sa.Column("project_id", sa.String(36), nullable=True))
    _create_index_if_missing("marketing_campaigns", "ix_marketing_campaigns_product_id", ["product_id"])
    _create_index_if_missing("marketing_campaigns", "ix_marketing_campaigns_project_id", ["project_id"])

    # seo and support stay tied to business only; analytics gets campaign link
    _add_column_if_missing("analytics_events", sa.Column("campaign_id", sa.String(36), nullable=True))
    _create_index_if_missing("analytics_events", "ix_analytics_events_campaign_id", ["campaign_id"])

    # billing plans
    if not _table_exists("billing_plans"):
        op.create_table(
            "billing_plans",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("slug", sa.String(64), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("price_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("interval", sa.String(20), nullable=False, server_default="free"),
            sa.Column("paypal_product_id", sa.String(255), nullable=True),
            sa.Column("paypal_plan_id", sa.String(255), nullable=True),
            sa.Column("features_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("limits_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("slug", name="uq_billing_plans_slug"),
        )
        op.create_index("ix_billing_plans_slug", "billing_plans", ["slug"], unique=True)

    if not _table_exists("user_subscriptions"):
        op.create_table(
            "user_subscriptions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("billing_plan_id", sa.String(36), sa.ForeignKey("billing_plans.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("provider", sa.String(20), nullable=False, server_default="paypal"),
            sa.Column("provider_subscription_id", sa.String(255), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="free"),
            sa.Column("current_period_start", sa.String(64), nullable=True),
            sa.Column("current_period_end", sa.String(64), nullable=True),
            sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("raw_provider_payload", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_user_subscriptions_user_id", "user_subscriptions", ["user_id"])
        op.create_index("ix_user_subscriptions_billing_plan_id", "user_subscriptions", ["billing_plan_id"])
        op.create_index("ix_user_subscriptions_provider_subscription_id", "user_subscriptions", ["provider_subscription_id"], unique=True)
        op.create_index("ix_user_subscriptions_status", "user_subscriptions", ["status"])

    if not _table_exists("payment_transactions"):
        op.create_table(
            "payment_transactions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True),
            sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
            sa.Column("provider", sa.String(20), nullable=False, server_default="paypal"),
            sa.Column("provider_payment_id", sa.String(255), nullable=True),
            sa.Column("provider_order_id", sa.String(255), nullable=True),
            sa.Column("provider_subscription_id", sa.String(255), nullable=True),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("type", sa.String(20), nullable=False, server_default="subscription"),
            sa.Column("raw_provider_payload", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_payment_transactions_user_id", "payment_transactions", ["user_id"])
        op.create_index("ix_payment_transactions_business_id", "payment_transactions", ["business_id"])
        op.create_index("ix_payment_transactions_product_id", "payment_transactions", ["product_id"])
        op.create_index("ix_payment_transactions_provider_payment_id", "payment_transactions", ["provider_payment_id"])
        op.create_index("ix_payment_transactions_provider_order_id", "payment_transactions", ["provider_order_id"])
        op.create_index("ix_payment_transactions_provider_subscription_id", "payment_transactions", ["provider_subscription_id"])

    if not _table_exists("usage_ledger"):
        op.create_table(
            "usage_ledger",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True),
            sa.Column("feature_key", sa.String(64), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("period_start", sa.String(64), nullable=False),
            sa.Column("period_end", sa.String(64), nullable=False),
            sa.Column("source", sa.String(64), nullable=False, server_default="app"),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_usage_ledger_user_id", "usage_ledger", ["user_id"])
        op.create_index("ix_usage_ledger_business_id", "usage_ledger", ["business_id"])
        op.create_index("ix_usage_ledger_feature_key", "usage_ledger", ["feature_key"])


def downgrade() -> None:
    for table in ["usage_ledger", "payment_transactions", "user_subscriptions", "billing_plans"]:
        if _table_exists(table):
            op.drop_table(table)

    for table, index_name in [
        ("analytics_events", "ix_analytics_events_campaign_id"),
        ("marketing_campaigns", "ix_marketing_campaigns_product_id"),
        ("marketing_campaigns", "ix_marketing_campaigns_project_id"),
        ("products", "ix_products_project_id"),
        ("businesses", "ix_businesses_workspace_id"),
        ("businesses", "ix_businesses_project_id"),
        ("users", "ix_users_active_workspace_id"),
        ("users", "ix_users_active_business_id"),
        ("users", "ix_users_active_project_id"),
    ]:
        if _table_exists(table) and _index_exists(table, index_name):
            op.drop_index(index_name, table_name=table)

    for table, column in [
        ("analytics_events", "campaign_id"),
        ("marketing_campaigns", "product_id"),
        ("marketing_campaigns", "project_id"),
        ("products", "project_id"),
        ("products", "status"),
        ("products", "product_type"),
        ("products", "payment_provider"),
        ("products", "paypal_product_id"),
        ("products", "paypal_plan_id"),
        ("products", "paypal_checkout_url"),
        ("products", "billing_type"),
        ("businesses", "workspace_id"),
        ("businesses", "project_id"),
        ("businesses", "page_content"),
        ("users", "active_workspace_id"),
        ("users", "active_business_id"),
        ("users", "active_project_id"),
    ]:
        if _table_exists(table) and _column_exists(table, column):
            op.drop_column(table, column)
