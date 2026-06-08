"""Import all ORM models so SQLAlchemy's metadata is fully populated.

IMPORT ORDER MATTERS:
- User must be imported before any model that references it via relationship
- UserAISettings must be imported right after User so the mapper can resolve it
- All other models follow

This module must be imported before any ``Base.metadata.create_all()`` call
or Alembic migration run.
"""
# ── Core user models (order is critical) ─────────────────────────────────────
from app.models.user import User  # noqa: F401
from app.models.user_ai_settings import UserAISettings  # noqa: F401

# ── Business domain models ────────────────────────────────────────────────────
from app.models.business import Business  # noqa: F401
from app.models.product import Product  # noqa: F401
from app.models.order import Order  # noqa: F401
from app.models.analytics import AnalyticsEvent  # noqa: F401

# ── Agent models ──────────────────────────────────────────────────────────────
from app.models.agent import AgentLog, AgentTask  # noqa: F401

# ── Experiment / A/B testing models ──────────────────────────────────────────
from app.models.experiment import Experiment, ExperimentAssignment, LandingVariant  # noqa: F401

# ── Marketing + support models ────────────────────────────────────────────────
from app.models.marketing import (  # noqa: F401
    CampaignAsset,
    CampaignRecipient,
    Contact,
    MarketingCalendarEvent,
    MarketingCampaign,
    SeoContent,
    SupportConversation,
)

# ── Background jobs model ─────────────────────────────────────────────────────
from app.models.job import Job, JobStatus, JobType  # noqa: F401
# ── Usage limits model ────────────────────────────────────────────────────────
from app.models.usage_limit import UsageLimit  # noqa: F401
from app.models.code_version import CodeVersion  # noqa: F401
from app.models.ai_memory import AIMemory  # noqa: F401
from app.models.code_embedding import CodeEmbedding  # noqa: F401
from app.models.workspace import Workspace, WorkspaceMember, Project  # noqa: F401
from app.models.deployment import Deployment, DeploymentCheck  # noqa: F401
from app.models.oauth_token import OAuthToken  # noqa: F401
from app.models.brand_system import BrandSystem  # noqa: F401
from app.models.scheduled_post import ScheduledPost  # noqa: F401
from app.models.campaign_metric import CampaignMetric  # noqa: F401
from app.models.billing import BillingPlan, UserSubscription, PaymentTransaction, UsageLedger  # noqa: F401
from app.models.integration_account import IntegrationAccount  # noqa: F401
from app.models.user_integration import IntegrationActionLog, OAuthStateRecord, UserIntegration  # noqa: F401
from app.models.ai_studio import AIStudioConversation, AIStudioMessage  # noqa: F401
__all__ = [
    "User",
    "UserAISettings",
    "Business",
    "Product",
    "Order",
    "AnalyticsEvent",
    "AgentLog",
    "AgentTask",
    "Experiment",
    "ExperimentAssignment",
    "LandingVariant",
    "MarketingCampaign",
    "SeoContent",
    "SupportConversation",
    "Job",
    "JobStatus",
    "JobType",
    "UsageLimit",
    "CodeVersion",
    "BillingPlan",
    "UserSubscription",
    "PaymentTransaction",
    "UsageLedger",
    "AIStudioConversation",
    "AIStudioMessage",
]
