"""Marketing Engine API — SEO content, email campaigns, social posts, ad payloads."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.user import User
from app.schemas.analytics import AnalyticsEventCreate
from app.services.ai_service import AIProviderError
from app.services.analytics_service import AnalyticsService
from app.services.business_service import BusinessService
from app.services.marketing_service import MarketingService
from app.services.product_service import ProductService
from app.services.job_service import JobService
from app.models.job import JobType
from app.services.integration_account_service import IntegrationAccountService
from app.services.platform_login_service import PlatformLoginService
from app.services.platform_publish_service import PlatformPublishService
from app.services.usage_service import UsageService

logger = logging.getLogger(__name__)
router = APIRouter()


def _public_browser_error_message(exc: Exception) -> str:
    raw = str(exc or "").strip()
    lowered = raw.lower()
    if "no saved" in lowered or "credentials are incomplete" in lowered:
        return raw
    if "attributeerror" in lowered or "sql:" in lowered or "integration_accounts" in lowered:
        return "The saved browser account could not be loaded correctly. Re-save the integration account and try again."
    if "timed out" in lowered:
        return "The browser session took too long to respond. Please try again."
    if "verification" in lowered:
        return "The platform requested extra verification before the session could be restored."
    return raw or "The browser publishing session failed before it could complete."


def _build_browser_publish_goal(platform: str, business_name: str, campaign: "MarketingCampaign") -> str:
    """Build a concrete browser-operator goal for publishing a campaign."""
    content = campaign.content or {}
    image_hint = content.get("image_url") or content.get("image_b64") or campaign.image_url or ""

    if platform == "wordpress":
        title = content.get("title") or content.get("headline") or campaign.name
        body = (
            content.get("content_markdown")
            or content.get("body")
            or content.get("post_text")
            or json.dumps(content, indent=2)
        )
        return (
            f"Open WordPress and publish a new post for {business_name}. "
            f"Log in if needed. Create a post titled '{title}'. "
            f"Use this content as the article body:\n\n{body}\n\n"
            f"If an image is available, upload it using this hint or path: {image_hint or 'no image provided'}.\n"
            "Stop when everything is ready for the final Publish click. "
            "Do not click Publish yet. Instead, summarize what is ready and wait for human confirmation."
        )

    post_text = (
        content.get("post_text")
        or content.get("headline")
        or content.get("body")
        or content.get("plain_text")
        or content.get("description")
    )
    if not post_text and isinstance(content.get("posts"), list) and content["posts"]:
        first_post = content["posts"][0] or {}
        post_text = (
            first_post.get("text")
            or first_post.get("caption")
            or first_post.get("body")
            or first_post.get("headline")
        )
        post_hashtags = first_post.get("hashtags") or []
        if post_text and post_hashtags:
            hashtag_text = " ".join(post_hashtags) if isinstance(post_hashtags, list) else str(post_hashtags)
            post_text = f"{post_text}\n\n{hashtag_text}"
    if not post_text:
        post_text = json.dumps(content, indent=2)

    hashtags = content.get("hashtags") or []
    hashtag_text = " ".join(hashtags) if isinstance(hashtags, list) else str(hashtags)
    if hashtag_text:
        post_text = f"{post_text}\n\n{hashtag_text}"

    return (
        f"Open {platform} and publish a post for {business_name}. "
        "Log in if needed using the saved session. "
        f"Create a new post with this content:\n\n{post_text}\n\n"
        f"If an image is available, upload it using this hint or path: {image_hint or 'no image provided'}.\n"
        "Complete the posting flow until the final confirmation screen. "
        "Do not click the final Publish/Post button. Stop there, summarize what is prepared, and wait for human confirmation."
    )


def _campaign_publish_text(campaign: "MarketingCampaign") -> str:
    content = campaign.content or {}
    text = (
        content.get("post_text")
        or content.get("headline")
        or content.get("body")
        or content.get("plain_text")
        or content.get("description")
        or content.get("content_markdown")
        or ""
    )
    if not text and isinstance(content.get("posts"), list):
        first_post = content["posts"][0] if content["posts"] else {}
        text = first_post.get("text") or first_post.get("caption") or first_post.get("body") or ""
        hashtags = first_post.get("hashtags") or []
        if hashtags:
            text = f"{text}\n\n{' '.join(str(tag) for tag in hashtags)}"
    hashtags = content.get("hashtags") or []
    if hashtags:
        text = f"{text}\n\n{' '.join(str(tag) for tag in hashtags)}"
    return str(text).strip()

async def check_publish_rate_limit(current_user: User = Depends(get_current_user)) -> User:
    from app.core.cache import cache
    key = f"rl:publish:{current_user.id}"
    count = await cache.get(key) or 0
    if count >= 10:
        raise HTTPException(status_code=429, detail="Publish rate limit exceeded. Max 10 publishes per hour.")
    await cache.set(key, count + 1, ttl=3600)
    return current_user


# ── Schemas ───────────────────────────────────────────────────────────────────

class SeoBlogRequest(BaseModel):
    topic: str = Field(min_length=5, max_length=200)
    target_keyword: str = Field(min_length=2, max_length=100)


class EmailCampaignRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    goal: str = Field(min_length=5, max_length=500)
    recipient_count: int = Field(default=0, ge=0)
    product_id: UUID | None = None


class SocialContentRequest(BaseModel):
    platform: str = Field(description="twitter | linkedin | instagram")
    post_count: int = Field(default=5, ge=1, le=20)
    product_id: UUID | None = None


class AdCampaignRequest(BaseModel):
    platform: str = Field(description="google_ads | meta_ads")
    budget_usd: float = Field(gt=0, le=100_000)
    product_id: UUID | None = None


class SendEmailRequest(BaseModel):
    recipient_emails: list[str] = Field(min_length=1)


class RejectRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    product_id: UUID | None
    project_id: UUID | None
    campaign_type: str
    name: str
    status: str
    content: dict
    targeting: dict
    metrics: dict
    approved_by: str | None
    rejection_reason: str | None
    created_at: datetime


class SeoContentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    title: str
    slug: str
    meta_description: str
    content_markdown: str
    keywords: list
    status: str
    word_count: int
    created_at: datetime


# ── SEO endpoints ─────────────────────────────────────────────────────────────

@router.post("/{business_id}/seo/generate", response_model=SeoContentRead, status_code=201)
async def generate_seo_blog(
    business_id: UUID,
    payload: SeoBlogRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SeoContentRead:
    """Generate a full SEO blog post using real AI."""
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    usage_svc = UsageService(db)
    await usage_svc.check_limit(current_user.id, "seo_generation")
    await usage_svc.check_limit(current_user.id, "ai_request")
    try:
        content = await MarketingService(db).generate_seo_blog(
            business_id=business_id,
            topic=payload.topic,
            target_keyword=payload.target_keyword,
            business_context={
                "name": business.name, "niche": business.niche,
                "target_audience": business.target_audience,
            },
        )
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    await usage_svc.increment_usage(
        current_user.id,
        "seo_generation",
        business_id=business_id,
        source="marketing_seo_generate",
        metadata_json={"topic": payload.topic, "target_keyword": payload.target_keyword},
    )
    await usage_svc.increment_usage(
        current_user.id,
        "ai_request",
        business_id=business_id,
        source="marketing_seo_generate",
        metadata_json={"topic": payload.topic},
    )
    return SeoContentRead.model_validate(content)


@router.get("/{business_id}/seo", response_model=list[SeoContentRead])
async def list_seo_content(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SeoContentRead]:
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    items = await MarketingService(db).list_seo_content(business_id)
    return [SeoContentRead.model_validate(i) for i in items]


@router.patch("/{business_id}/seo/{content_id}/publish", response_model=SeoContentRead)
async def publish_seo_content(
    business_id: UUID,
    content_id: UUID,
    current_user: User = Depends(check_publish_rate_limit),
    db: AsyncSession = Depends(get_db),
) -> SeoContentRead:
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    content = await MarketingService(db).publish_seo_content(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return SeoContentRead.model_validate(content)


# ── Async Job-Based Endpoints (new job system) ────────────────────────────────

class JobStartResponse(BaseModel):
    """Response when starting a background job."""
    job_id: str
    job_type: str
    status: str
    progress_percent: int
    created_at: str | None


@router.post("/{business_id}/seo/generate-async", response_model=JobStartResponse, status_code=202)
async def generate_seo_blog_async(
    business_id: UUID,
    payload: SeoBlogRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobStartResponse:
    """Start an async SEO blog generation job.

    Returns immediately with job ID. Use GET /jobs/{job_id} to track progress.
    """
    # Verify business ownership
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    usage_svc = UsageService(db)
    await usage_svc.check_limit(current_user.id, "seo_generation")

    # Create job record
    job_svc = JobService(db)
    job = await job_svc.create_job(
        job_type=JobType.SEO_BLOG,
        job_name=f"Generate SEO blog: {payload.topic}",
        user_id=current_user.id,
        business_id=business_id,
        payload={
            "topic": payload.topic,
            "target_keyword": payload.target_keyword,
        },
        job_description=f"Generate SEO blog post about '{payload.topic}'",
        estimated_completion_seconds=120,
    )

    # Dispatch to Celery
    try:
        from app.worker import celery_app
        task = celery_app.send_task(
            "app.tasks.generate_seo_blog_job_task",
            args=[str(job.id), str(business_id)],
            kwargs={"payload": {"topic": payload.topic, "target_keyword": payload.target_keyword}},
            task_id=f"seo-blog-{job.id}",
        )
        logger.info("SEO blog job dispatched  job_id=%s  task_id=%s", job.id, task.id)
    except Exception as exc:
        logger.error("Failed to dispatch SEO blog task: %s", exc)
        await job_svc.mark_failed(job.id, error_message=str(exc), should_retry=False)
        raise HTTPException(status_code=500, detail="Failed to start background job")

    return JobStartResponse(
        job_id=str(job.id),
        job_type="seo_blog",
        status="pending",
        progress_percent=0,
        created_at=job.created_at.isoformat() if job.created_at else None,
    )


@router.post("/{business_id}/campaigns/email-async", response_model=JobStartResponse, status_code=202)
async def generate_email_campaign_async(
    business_id: UUID,
    payload: EmailCampaignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobStartResponse:
    """Start an async email campaign generation job.

    Returns immediately with job ID. Use GET /jobs/{job_id} to track progress.
    """
    # Verify business ownership
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    usage_svc = UsageService(db)
    await usage_svc.check_limit(current_user.id, "marketing_campaign")

    # Create job record
    job_svc = JobService(db)
    job = await job_svc.create_job(
        job_type=JobType.MARKETING_CAMPAIGN,
        job_name=f"Generate email campaign: {payload.name}",
        user_id=current_user.id,
        business_id=business_id,
        payload={
            "name": payload.name,
            "goal": payload.goal,
            "recipient_count": payload.recipient_count,
        },
        job_description=f"Generate email campaign '{payload.name}'",
        estimated_completion_seconds=120,
    )

    # Dispatch to Celery
    try:
        from app.worker import celery_app
        task = celery_app.send_task(
            "app.tasks.generate_email_campaign_job_task",
            args=[str(job.id), str(business_id)],
            kwargs={
                "payload": {
                    "name": payload.name,
                    "goal": payload.goal,
                    "recipient_count": payload.recipient_count,
                }
            },
            task_id=f"email-campaign-{job.id}",
        )
        logger.info("Email campaign job dispatched  job_id=%s  task_id=%s", job.id, task.id)
    except Exception as exc:
        logger.error("Failed to dispatch email campaign task: %s", exc)
        await job_svc.mark_failed(job.id, error_message=str(exc), should_retry=False)
        raise HTTPException(status_code=500, detail="Failed to start background job")

    return JobStartResponse(
        job_id=str(job.id),
        job_type="marketing_campaign",
        status="pending",
        progress_percent=0,
        created_at=job.created_at.isoformat() if job.created_at else None,
    )


# ── Campaign endpoints ────────────────────────────────────────────────────────

@router.post("/{business_id}/campaigns/email", response_model=CampaignRead, status_code=201)
async def generate_email_campaign(
    business_id: UUID,
    payload: EmailCampaignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CampaignRead:
    """Generate an email campaign. Requires approval before sending.

    For async processing, use POST /{business_id}/campaigns/email-async instead.
    """
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    selected_product = None
    if payload.product_id:
        selected_product = await ProductService(db).get(payload.product_id)
        if not selected_product or str(selected_product.business_id) != str(business_id):
            raise HTTPException(status_code=404, detail="Product not found")
    usage_svc = UsageService(db)
    await usage_svc.check_limit(current_user.id, "marketing_campaign")
    await usage_svc.check_limit(current_user.id, "ai_request")
    try:
        campaign = await MarketingService(db).generate_email_campaign(
            business_id=business_id,
            campaign_name=payload.name,
            goal=payload.goal,
            business_context={
                "name": business.name, "niche": business.niche,
                "brand_tone": business.brand_tone,
                "target_audience": business.target_audience,
            },
            product_context=(
                {
                    "name": selected_product.name,
                    "description": selected_product.description,
                    "price": str(selected_product.price),
                    "currency": selected_product.currency,
                    "product_type": selected_product.product_type,
                }
                if selected_product
                else None
            ),
            project_id=selected_product.project_id if selected_product else business.project_id,
            product_id=selected_product.id if selected_product else None,
            recipient_count=payload.recipient_count,
        )
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    await usage_svc.increment_usage(
        current_user.id,
        "marketing_campaign",
        business_id=business_id,
        source="marketing_email_generate",
        metadata_json={"campaign_name": payload.name},
    )
    await usage_svc.increment_usage(
        current_user.id,
        "ai_request",
        business_id=business_id,
        source="marketing_email_generate",
        metadata_json={"campaign_name": payload.name},
    )
    await AnalyticsService(db).track(
        AnalyticsEventCreate(
            business_id=business_id,
            product_id=campaign.product_id,
            event_type="marketing_campaign_created",
            source="email_campaign",
            metadata_json={"campaign_id": str(campaign.id), "campaign_type": campaign.campaign_type, "status": campaign.status},
        )
    )
    return CampaignRead.model_validate(campaign)


@router.post("/{business_id}/campaigns/social", response_model=CampaignRead, status_code=201)
async def generate_social_content(
    business_id: UUID,
    payload: SocialContentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CampaignRead:
    """Generate social media posts for review."""
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    selected_product = None
    if payload.product_id:
        selected_product = await ProductService(db).get(payload.product_id)
        if not selected_product or str(selected_product.business_id) != str(business_id):
            raise HTTPException(status_code=404, detail="Product not found")
    usage_svc = UsageService(db)
    await usage_svc.check_limit(current_user.id, "marketing_campaign")
    await usage_svc.check_limit(current_user.id, "ai_request")
    try:
        campaign = await MarketingService(db).generate_social_content(
            business_id=business_id,
            platform=payload.platform,
            business_context={
                "name": business.name, "niche": business.niche,
                "brand_tone": business.brand_tone,
                "target_audience": business.target_audience,
            },
            product_context=(
                {
                    "name": selected_product.name,
                    "description": selected_product.description,
                    "price": str(selected_product.price),
                    "currency": selected_product.currency,
                    "product_type": selected_product.product_type,
                }
                if selected_product
                else None
            ),
            project_id=selected_product.project_id if selected_product else business.project_id,
            product_id=selected_product.id if selected_product else None,
            post_count=payload.post_count,
        )
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    await usage_svc.increment_usage(
        current_user.id,
        "marketing_campaign",
        business_id=business_id,
        source="marketing_social_generate",
        metadata_json={"platform": payload.platform},
    )
    await usage_svc.increment_usage(
        current_user.id,
        "ai_request",
        business_id=business_id,
        source="marketing_social_generate",
        metadata_json={"platform": payload.platform},
    )
    await AnalyticsService(db).track(
        AnalyticsEventCreate(
            business_id=business_id,
            product_id=campaign.product_id,
            event_type="marketing_campaign_created",
            source=f"social_{payload.platform}",
            metadata_json={"campaign_id": str(campaign.id), "campaign_type": campaign.campaign_type, "status": campaign.status},
        )
    )
    return CampaignRead.model_validate(campaign)


@router.post("/{business_id}/campaigns/ads", response_model=CampaignRead, status_code=201)
async def generate_ad_campaign(
    business_id: UUID,
    payload: AdCampaignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CampaignRead:
    """Generate ad campaign payload. ALWAYS requires approval. Never auto-spends."""
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    products = await ProductService(db).list(business_id)
    selected_product = None
    if payload.product_id:
        selected_product = await ProductService(db).get(payload.product_id)
        if not selected_product or str(selected_product.business_id) != str(business_id):
            raise HTTPException(status_code=404, detail="Product not found")
    usage_svc = UsageService(db)
    await usage_svc.check_limit(current_user.id, "marketing_campaign")
    await usage_svc.check_limit(current_user.id, "ai_request")
    try:
        campaign = await MarketingService(db).generate_ad_campaign(
            business_id=business_id,
            platform=payload.platform,
            budget_usd=payload.budget_usd,
            business_context={
                "name": business.name, "niche": business.niche,
                "target_audience": business.target_audience,
            },
            products=[{"name": p.name, "price": str(p.price)} for p in products],
            selected_product=(
                {
                    "name": selected_product.name,
                    "description": selected_product.description,
                    "price": str(selected_product.price),
                    "currency": selected_product.currency,
                    "product_type": selected_product.product_type,
                }
                if selected_product
                else None
            ),
            project_id=selected_product.project_id if selected_product else business.project_id,
            product_id=selected_product.id if selected_product else None,
        )
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    await usage_svc.increment_usage(
        current_user.id,
        "marketing_campaign",
        business_id=business_id,
        source="marketing_ads_generate",
        metadata_json={"platform": payload.platform},
    )
    await usage_svc.increment_usage(
        current_user.id,
        "ai_request",
        business_id=business_id,
        source="marketing_ads_generate",
        metadata_json={"platform": payload.platform},
    )
    await AnalyticsService(db).track(
        AnalyticsEventCreate(
            business_id=business_id,
            product_id=campaign.product_id,
            event_type="marketing_campaign_created",
            source=f"ads_{payload.platform}",
            metadata_json={"campaign_id": str(campaign.id), "campaign_type": campaign.campaign_type, "status": campaign.status},
        )
    )
    return CampaignRead.model_validate(campaign)


@router.get("/{business_id}/campaigns", response_model=list[CampaignRead])
async def list_campaigns(
    business_id: UUID,
    campaign_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CampaignRead]:
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    campaigns = await MarketingService(db).list_campaigns(business_id, campaign_type, limit, offset)
    return [CampaignRead.model_validate(c) for c in campaigns]


@router.post("/{business_id}/campaigns/{campaign_id}/approve", response_model=CampaignRead)
async def approve_campaign(
    business_id: UUID,
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CampaignRead:
    """Approve a pending campaign. Required before any campaign is executed."""
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    campaign = await MarketingService(db).approve_campaign(campaign_id, str(current_user.email))
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found or not pending approval")
    return CampaignRead.model_validate(campaign)


@router.post("/{business_id}/campaigns/{campaign_id}/reject", response_model=CampaignRead)
async def reject_campaign(
    business_id: UUID,
    campaign_id: UUID,
    payload: RejectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CampaignRead:
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    campaign = await MarketingService(db).reject_campaign(campaign_id, payload.reason)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignRead.model_validate(campaign)


@router.post("/{business_id}/campaigns/{campaign_id}/duplicate", response_model=CampaignRead, status_code=201)
async def duplicate_campaign(
    business_id: UUID,
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CampaignRead:
    """Duplicate an existing campaign into a new draft."""
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    campaign = await MarketingService(db).duplicate_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignRead.model_validate(campaign)


@router.post("/{business_id}/campaigns/{campaign_id}/ab-test", response_model=CampaignRead)
async def generate_ab_test(
    business_id: UUID,
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CampaignRead:
    """Generate a Variant B for an existing campaign."""
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    campaign = await MarketingService(db).generate_ab_test_variant(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignRead.model_validate(campaign)


class ContentStudioRequest(BaseModel):
    content_type: str = Field(..., description="e.g. LinkedIn post, Twitter thread")
    tone: str = Field(..., description="e.g. professional, humorous")
    audience: str = Field(..., description="e.g. founders, developers")
    cta: str = Field(..., description="e.g. sign up, read more")

@router.post("/{business_id}/content-studio/generate", response_model=CampaignRead)
async def content_studio_generate(
    business_id: UUID,
    payload: ContentStudioRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CampaignRead:
    """Generate custom content via the Content Studio."""
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    
    business_context = {
        "name": business.name,
        "niche": business.niche,
    }
    
    campaign = await MarketingService(db).generate_custom_content(
        business_id, payload.content_type, payload.tone, payload.audience, payload.cta, business_context
    )
    return CampaignRead.model_validate(campaign)


@router.post("/{business_id}/agents/trend")
async def run_trend_agent(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run the Trend Agent to research current industry trends."""
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
        
    from app.services.ai_orchestrator import generate_json_smart, ProviderChoice
    prompt = (
        f"You are a market research and trend analysis agent.\n"
        f"Analyze current trends for the following business niche: {business.niche}\n"
        "Return a JSON object with 'trends' (an array of strings), 'opportunities' (an array of strings), "
        "and 'summary' (a brief string)."
    )
    data = await generate_json_smart(prompt, prefer_provider=ProviderChoice.AUTO)
    return data


@router.post("/{business_id}/campaigns/{campaign_id}/send")
async def send_email_campaign(
    business_id: UUID,
    campaign_id: UUID,
    payload: SendEmailRequest,
    current_user: User = Depends(check_publish_rate_limit),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send an approved email campaign to a list of recipients."""
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    result = await MarketingService(db).send_approved_email_campaign(
        campaign_id, payload.recipient_emails, str(current_user.id)
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Autonomous Marketing Engine ───────────────────────────────────────────────

class AutoRunRequest(BaseModel):
    goal: str = Field(min_length=5, max_length=500)
    budget_usd: float = Field(default=100.0, gt=0, le=100_000)
    platforms: list[str] = Field(default=["email", "social", "google_ads"])
    token: str = Field(description="JWT access token for SSE auth")


@router.get("/{business_id}/run")
async def run_marketing_engine(
    business_id: UUID,
    goal: str = Query(..., min_length=5),
    budget_usd: float = Query(default=100.0),
    platforms: str = Query(default="email,social,google_ads"),
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream autonomous marketing engine execution via SSE.

    Connect with EventSource:
        const es = new EventSource('/api/v1/marketing/{id}/run?goal=...&token=...')
    """
    from app.core.security import decode_access_token
    from jose import JWTError
    from app.services.marketing_agent import MarketingAgentCoordinator

    # Validate token
    try:
        payload = decode_access_token(token)
        user_id = payload["sub"]
    except (JWTError, KeyError):
        async def _err():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Invalid token'})}\n\n"
        return StreamingResponse(_err(), media_type="text/event-stream")

    # Verify business ownership
    from uuid import UUID as _UUID
    biz = await BusinessService(db).get(business_id, user_id=_UUID(user_id))
    if not biz:
        async def _err2():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Business not found'})}\n\n"
        return StreamingResponse(_err2(), media_type="text/event-stream")

    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]

    async def _stream():
        coordinator = MarketingAgentCoordinator(db)
        async for event in coordinator.run_stream(
            business_id=business_id,
            goal=goal,
            budget_usd=budget_usd,
            platforms=platform_list,
        ):
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{business_id}/campaigns/{campaign_id}/optimize")
async def optimize_campaign(
    business_id: UUID,
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run OptimizationAgent on a specific campaign."""
    from app.services.ai_service import AIService

    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    campaign = await db.get(MarketingCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    usage_svc = UsageService(db)
    await usage_svc.check_limit(current_user.id, "image_generation")

    ai = AIService()
    metrics = campaign.metrics or {}

    opt_prompt = (
        f"You are a marketing optimization expert.\n"
        f"Analyze this campaign performance and suggest specific improvements.\n"
        f"Return ONLY valid JSON with these keys:\n"
        f"  headline_suggestion, cta_suggestion, targeting_suggestion,\n"
        f"  predicted_improvement_pct, reasoning\n\n"
        f"Campaign: {campaign.name}\n"
        f"Type: {campaign.campaign_type}\n"
        f"Business: {business.name}\n"
        f"Current metrics: clicks={metrics.get('clicks', 0)}, "
        f"conversions={metrics.get('conversions', 0)}, "
        f"CTR={metrics.get('ctr', 0)}%\n"
        f"Current content preview: {str(campaign.content)[:300]}"
    )

    try:
        result = await ai.generate_json(opt_prompt)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # Update campaign metrics with optimization suggestion
    campaign.metrics = {**metrics, "optimization": result, "optimized_at": datetime.utcnow().isoformat()}
    await db.commit()

    return result


# Import needed for campaign model in optimize endpoint
from app.models.marketing import MarketingCampaign  # noqa: E402


# ── Image Generation ──────────────────────────────────────────────────────────

@router.post("/{business_id}/campaigns/{campaign_id}/generate-image")
async def generate_campaign_image(
    business_id: UUID,
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate an AI image for a campaign using DALL-E 3 or Stability AI."""
    from app.services.image_generation_service import ImageGenerationService, ImageGenerationError
    from app.services.brand_system_service import BrandSystemService

    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    campaign = await db.get(MarketingCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    brand = await BrandSystemService(db).get(str(business_id))

    prompt = (
        f"Professional marketing image for {business.name}. "
        f"Campaign: {campaign.name}. "
        f"Style: modern, clean, high-quality commercial photography."
    )

    try:
        svc = ImageGenerationService()
        image_path = await svc.generate(prompt=prompt, size="1024x1024", brand=brand)
    except ImageGenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # Save image_url to campaign
    campaign.image_url = image_path  # type: ignore[attr-defined]
    await db.commit()
    await usage_svc.increment_usage(
        current_user.id,
        "image_generation",
        business_id=business_id,
        source="campaign_image_generate",
        metadata_json={"campaign_id": str(campaign_id)},
    )

    return {"image_url": image_path, "campaign_id": str(campaign_id)}


# ── Real Publishing ───────────────────────────────────────────────────────────

@router.post("/{business_id}/campaigns/{campaign_id}/publish/{platform}")
async def publish_campaign(
    business_id: UUID,
    campaign_id: UUID,
    platform: str,
    current_user: User = Depends(check_publish_rate_limit),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Publish a campaign using the autonomous Playwright Browser Agent."""
    from app.services.business_service import BusinessService
    from app.models.marketing import MarketingCampaign
    
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    campaign = await db.get(MarketingCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await UsageService(db).check_limit(current_user.id, "browser_agent_run")

    if platform in ("google_ads", "meta_ads"):
        raise HTTPException(status_code=400, detail="Ads must be launched via Ads Manager")

    try:
        from app.worker import celery_app
        task = celery_app.send_task(
            "app.tasks.publish_via_browser_agent_task",
            args=[str(campaign_id), platform],
            task_id=f"publish-agent-{campaign_id}-{platform}",
        )
        logger.info("Browser publishing task dispatched  campaign_id=%s  platform=%s  task_id=%s", campaign_id, platform, task.id)
        
        campaign.status = "pending_publish"
        await db.commit()
        
    except Exception as exc:
        logger.error("Failed to dispatch browser publish task: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to start browser agent publishing job")

    return {
        "status": "pending_publish",
        "message": f"Autonomous agent dispatched to publish on {platform}. Check Agent Live stream.",
        "task_id": task.id
    }


@router.get("/{business_id}/campaigns/{campaign_id}/browser-stream/{platform}")
async def stream_browser_publish(
    business_id: UUID,
    campaign_id: UUID,
    platform: str,
    token: str = Query(..., description="JWT access token for SSE auth"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream a real browser-based publish run directly to the marketing UI."""
    if not settings.should_enable_browser_agent:
        async def _vps_error():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Browser agent is disabled in the current deployment mode. Deploy the full stack on a VPS to use this feature.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'status': 'failed'})}\n\n"
        return StreamingResponse(_vps_error(), media_type="text/event-stream")

    from app.core.security import decode_access_token
    from app.models.marketing import MarketingCampaign
    from app.services.browser_agent.browser_agent import BrowserAgent
    from app.services.usage_service import UsageService
    from jose import JWTError

    async def _error_stream(message: str) -> StreamingResponse:
        async def _inner():
            yield f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'status': 'failed'})}\n\n"
        return StreamingResponse(_inner(), media_type="text/event-stream")

    try:
        payload = decode_access_token(token)
        user_id = payload["sub"]
    except (JWTError, KeyError):
        return await _error_stream("Invalid or expired token")

    business = await BusinessService(db).get(business_id, user_id=UUID(user_id))
    if not business:
        return await _error_stream("Business not found or access denied")

    campaign = await db.get(MarketingCampaign, campaign_id)
    if not campaign or str(campaign.business_id).replace("-", "") != str(business_id).replace("-", ""):
        return await _error_stream("Campaign not found")

    if platform in {"email", "google_ads", "meta_ads"}:
        return await _error_stream(f"{platform} is not supported in browser publish mode")

    if campaign.status == "pending_approval":
        return await _error_stream("Approve this campaign before publishing it")
    await UsageService(db).check_limit(UUID(user_id), "browser_agent_run")
    await UsageService(db).increment_usage(
        UUID(user_id),
        "browser_agent_run",
        business_id=business_id,
        source="marketing_browser_publish",
        metadata_json={"campaign_id": str(campaign_id), "platform": platform},
    )

    goal = _build_browser_publish_goal(platform, business.name, campaign)

    async def _stream():
        agent = BrowserAgent(
            db=db,
            business_id=str(business_id),
            session_id=f"marketing-{business_id}-{platform}",
            headless=False,
            max_steps=40,
        )
        published = False
        final_summary = ""

        try:
            campaign.status = "running"
            await db.commit()
            completion_state = "failed"

            account_service = IntegrationAccountService(db)
            saved_account = await account_service.get(
                user_id=UUID(user_id),
                business_id=business_id,
                platform=platform,
            )
            fallback_account = None
            if saved_account is None and platform in {"linkedin", "instagram", "facebook"}:
                fallback_account = await account_service.get(
                    user_id=UUID(user_id),
                    business_id=business_id,
                    platform="browser_automation",
                )
            revealed_account = account_service.reveal(saved_account) if saved_account else (
                account_service.reveal(fallback_account) if fallback_account else None
            )
            if revealed_account:
                bootstrap = PlatformLoginService(agent.session_manager)
                bootstrap_result = await bootstrap.ensure_session(platform=platform, credentials=revealed_account)
                yield f"data: {json.dumps({'type': 'status', 'status': bootstrap_result.get('status', 'running'), 'message': bootstrap_result.get('message', ''), 'platform': platform, 'phase': 'session_bootstrap'})}\n\n"
                if bootstrap_result.get("status") == "failed":
                    raise HTTPException(status_code=400, detail=bootstrap_result.get("message") or f"{platform} login could not be restored")
            else:
                yield f"data: {json.dumps({'type': 'status', 'status': 'running', 'message': f'No saved {platform} browser account found. Reusing any existing browser session state instead.', 'platform': platform, 'phase': 'session_bootstrap'})}\n\n"

            direct_publishable = {"linkedin", "instagram"}
            if platform in direct_publishable:
                direct_service = PlatformPublishService(agent.session_manager)
                async for event in direct_service.publish(
                    platform=platform,
                    text=_campaign_publish_text(campaign),
                    image_hint=(campaign.content or {}).get("image_path") or campaign.image_url,
                ):
                    event.setdefault("campaign_id", str(campaign_id))
                    event.setdefault("platform", platform)
                    if event.get("type") == "result":
                        final_summary = str(event.get("text", ""))
                    if event.get("type") == "done":
                        published = event.get("status") == "done"
                        completion_state = "published" if published else "failed"
                    yield f"data: {json.dumps(event, default=str)}\n\n"
            else:
                async for event in agent.iter_events(goal):
                    event.setdefault("campaign_id", str(campaign_id))
                    event.setdefault("platform", platform)
                    if event.get("type") == "result":
                        final_summary = str(event.get("text", ""))
                    if event.get("type") == "done":
                        published = event.get("status") == "done"
                        completion_state = "awaiting_final_confirmation" if published else "failed"
                    yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as exc:
            logger.exception("Browser publish stream failed: %s", exc)
            final_summary = _public_browser_error_message(exc)
            yield f"data: {json.dumps({'type': 'error', 'message': f'Browser publish failed: {final_summary}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'status': 'failed', 'campaign_id': str(campaign_id), 'platform': platform})}\n\n"
        finally:
            db_campaign = await db.get(MarketingCampaign, campaign_id)
            if db_campaign:
                db_campaign.status = completion_state if published else "approved"
                metrics = dict(db_campaign.metrics or {})
                metrics["browser_publish"] = {
                    "platform": platform,
                    "status": completion_state if published else "failed",
                    "completed_at": datetime.utcnow().isoformat(),
                    "summary": final_summary[:4000],
                }
                db_campaign.metrics = metrics
                await db.commit()
            await agent.session_manager.close()

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Scheduling ────────────────────────────────────────────────────────────────

class ScheduleRequest(BaseModel):
    scheduled_at: str = Field(description="ISO 8601 datetime string")
    timezone: str = Field(default="UTC")
    platform: str = Field(description="Target platform for publishing")


@router.post("/{business_id}/campaigns/{campaign_id}/schedule")
async def schedule_campaign(
    business_id: UUID,
    campaign_id: UUID,
    payload: ScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Schedule a campaign for future publishing."""
    import json as _json
    from app.models.scheduled_post import ScheduledPost

    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    campaign = await db.get(MarketingCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Convert to UTC
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(payload.scheduled_at.replace("Z", "+00:00"))
        scheduled_utc = dt.astimezone(timezone.utc).isoformat()
    except Exception:
        scheduled_utc = payload.scheduled_at

    post = ScheduledPost(
        campaign_id=str(campaign_id),
        business_id=str(business_id),
        platform=payload.platform,
        content_json=_json.dumps(campaign.content or {}),
        scheduled_at_utc=scheduled_utc,
        timezone=payload.timezone,
        status="pending",
    )
    db.add(post)
    campaign.status = "scheduled"
    campaign.scheduled_at = scheduled_utc  # type: ignore[attr-defined]
    await db.commit()
    await db.refresh(post)

    return post.to_dict()


@router.get("/{business_id}/calendar")
async def get_calendar(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return all scheduled posts for a business ordered by date."""
    from sqlalchemy import select
    from app.models.scheduled_post import ScheduledPost

    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    result = await db.execute(
        select(ScheduledPost)
        .where(ScheduledPost.business_id == str(business_id))
        .order_by(ScheduledPost.scheduled_at_utc.asc())
    )
    posts = result.scalars().all()
    return [p.to_dict() for p in posts]


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/{business_id}/analytics")
async def get_marketing_analytics(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return aggregated campaign metrics for the last 30 days."""
    from sqlalchemy import select, func
    from app.models.campaign_metric import CampaignMetric
    from app.services.ai_service import AIService

    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    campaigns = await MarketingService(db).list_campaigns(business_id)

    # Aggregate metrics per campaign
    campaign_stats = []
    for c in campaigns:
        result = await db.execute(
            select(
                func.sum(CampaignMetric.impressions).label("impressions"),
                func.sum(CampaignMetric.clicks).label("clicks"),
                func.sum(CampaignMetric.conversions).label("conversions"),
                func.sum(CampaignMetric.spend_cents).label("spend_cents"),
            ).where(CampaignMetric.campaign_id == str(c.id))
        )
        row = result.one()
        impressions = row.impressions or 0
        clicks = row.clicks or 0
        conversions = row.conversions or 0
        spend_cents = row.spend_cents or 0
        campaign_stats.append({
            "campaign_id": str(c.id),
            "campaign_name": c.name,
            "campaign_type": c.campaign_type,
            "status": c.status,
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "ctr": round(clicks / max(impressions, 1) * 100, 2),
            "spend_usd": round(spend_cents / 100, 2),
            "roas": round(conversions * 50 / max(spend_cents / 100, 0.01), 2),
        })

    # AI insights
    ai_insights = ""
    try:
        ai = AIService()
        top = sorted(campaign_stats, key=lambda x: x["clicks"], reverse=True)[:3]
        insight_prompt = (
            f"You are a marketing analyst. Summarize these campaign results in 2-3 sentences.\n"
            f"Business: {business.name}\n"
            f"Top campaigns: {top}\n"
            f"Give actionable recommendations. Be specific."
        )
        ai_insights = await ai.generate_text(insight_prompt)
    except Exception:
        ai_insights = "Run campaigns to see AI-powered insights here."

    return {
        "business_id": str(business_id),
        "campaigns": campaign_stats,
        "totals": {
            "impressions": sum(c["impressions"] for c in campaign_stats),
            "clicks": sum(c["clicks"] for c in campaign_stats),
            "conversions": sum(c["conversions"] for c in campaign_stats),
            "spend_usd": sum(c["spend_usd"] for c in campaign_stats),
        },
        "ai_insights": ai_insights,
    }


class MetricSnapshot(BaseModel):
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    spend_cents: int = 0
    engagement: int = 0
    platform: str = ""


@router.post("/{business_id}/campaigns/{campaign_id}/metrics")
async def record_campaign_metrics(
    business_id: UUID,
    campaign_id: UUID,
    payload: MetricSnapshot,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Record a metric snapshot for a campaign."""
    from datetime import datetime, timezone
    from app.models.campaign_metric import CampaignMetric

    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    metric = CampaignMetric(
        campaign_id=str(campaign_id),
        recorded_at=datetime.now(timezone.utc).isoformat(),
        impressions=payload.impressions,
        clicks=payload.clicks,
        conversions=payload.conversions,
        spend_cents=payload.spend_cents,
        engagement=payload.engagement,
        platform=payload.platform,
    )
    db.add(metric)
    await db.commit()
    await db.refresh(metric)
    return metric.to_dict()
