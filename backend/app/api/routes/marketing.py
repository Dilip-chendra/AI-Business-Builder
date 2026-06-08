"""Marketing Engine API — SEO content, email campaigns, social posts, ad payloads."""
from __future__ import annotations

import json
import logging
import csv
import io
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.analytics import AnalyticsEventCreate
from app.services.ai_service import AIProviderError
from app.services.analytics_service import AnalyticsService
from app.services.business_service import BusinessService
from app.services.marketing_service import MarketingService
from app.services.product_service import ProductService
from app.services.job_service import JobService
from app.models.job import JobType
from app.models.marketing import CampaignAsset, Contact, MarketingCalendarEvent
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


def _ids_match(left: object, right: object) -> bool:
    return str(left).replace("-", "") == str(right).replace("-", "")


def _build_browser_publish_goal(platform: str, business_name: str, campaign: "MarketingCampaign") -> str:
    """Build a concrete browser-operator goal for publishing a campaign."""
    content = getattr(campaign, "_platform_content", None) or campaign.content or {}
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

    if platform == "email":
        subject = content.get("subject") or campaign.name
        body = (
            content.get("plain_text_body")
            or content.get("body")
            or content.get("html_body")
            or json.dumps(content, indent=2)
        )
        return (
            f"Open Gmail and prepare an email campaign draft for {business_name}. "
            "Log in if needed using the saved Gmail/browser session. "
            f"Use this subject:\n{subject}\n\n"
            f"Use this email body:\n\n{body}\n\n"
            "Do not send the email. Stop at the final review/send screen, summarize what is prepared, "
            "and wait for human confirmation."
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


def _campaign_publish_text(campaign: "MarketingCampaign", content_override: dict | None = None) -> str:
    content = content_override or campaign.content or {}
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


async def _campaign_platform_content(db: AsyncSession, campaign_id: UUID, platform: str) -> dict | None:
    """Return the child campaign asset content for a parent campaign/platform."""
    from sqlalchemy import select
    from app.models.marketing import CampaignAsset

    aliases = {
        "email": {"email"},
        "social": {"social", "twitter", "linkedin", "instagram", "facebook"},
        "twitter": {"twitter", "social"},
        "linkedin": {"linkedin", "social"},
        "instagram": {"instagram", "social"},
        "facebook": {"facebook", "social"},
        "wordpress": {"wordpress", "seo_blog", "blog"},
        "google_ads": {"google_ads", "google"},
        "meta_ads": {"meta_ads", "facebook_ads", "instagram_ads"},
    }
    candidates = aliases.get(platform, {platform})
    result = await db.execute(
        select(CampaignAsset)
        .where(CampaignAsset.campaign_id == campaign_id)
        .order_by(CampaignAsset.created_at.asc())
    )
    for asset in result.scalars().all():
        asset_platform = str(asset.platform or "").lower()
        asset_type = str(asset.asset_type or "").lower()
        if asset_platform in candidates or asset_type in candidates:
            return dict(asset.content or {})
    return None

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


class ContactCreateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=80)
    source: str = Field(default="manual", max_length=120)
    consent_status: str = Field(default="unknown", max_length=40)
    segment: str | None = Field(default=None, max_length=120)


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    name: str | None
    email: str | None
    phone: str | None
    source: str
    consent_status: str
    segment: str | None
    lead_status: str
    lead_score: int
    created_at: datetime


class ContactImportResult(BaseModel):
    imported: int
    skipped_duplicates: int
    skipped_invalid: int
    total_rows: int
    contacts: list[ContactRead]


class RejectRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class CampaignUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    content: dict | None = None
    content_text: str | None = Field(default=None, max_length=20000)


class PublishCampaignRequest(BaseModel):
    recipient_emails: list[str] | None = None
    page_id: str | None = None
    account_id: str | None = None
    site_id: str | None = None
    channel: str | None = None
    parent_page_id: str | None = None
    media_url: str | None = None


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    product_id: UUID | None
    project_id: UUID | None
    parent_campaign_id: UUID | None = None
    campaign_type: str
    name: str
    goal: str | None = None
    budget_cents: int = 0
    status: str
    content: dict
    targeting: dict
    metrics: dict
    analytics_source: str = "real"
    approved_by: str | None
    rejection_reason: str | None
    lifecycle_status: str | None = None
    scheduled_at: str | None = None
    image_url: str | None = None
    ab_test_active: bool | None = None
    variant_b_content: str | None = None
    created_at: datetime


class CampaignAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    campaign_id: UUID
    platform: str
    asset_type: str
    subject: str | None
    content: dict
    creative_url: str | None
    status: str
    scheduled_at: datetime | None
    published_at: datetime | None
    external_post_id: str | None
    created_at: datetime


class CampaignDetailRead(CampaignRead):
    assets: list[CampaignAssetRead] = []


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


@router.get("/{business_id}/campaigns/{campaign_id}", response_model=CampaignDetailRead)
async def get_campaign_detail(
    business_id: UUID,
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CampaignDetailRead:
    from sqlalchemy import select
    from app.models.marketing import CampaignAsset

    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    campaign = await db.get(MarketingCampaign, campaign_id)
    if not campaign or str(campaign.business_id) != str(business_id):
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.metrics = await MarketingService(db).real_campaign_metrics(campaign_id)
    result = await db.execute(select(CampaignAsset).where(CampaignAsset.campaign_id == campaign_id).order_by(CampaignAsset.created_at.asc()))
    payload = CampaignRead.model_validate(campaign).model_dump()
    payload["assets"] = [CampaignAssetRead.model_validate(asset) for asset in result.scalars().all()]
    return CampaignDetailRead(**payload)


@router.post("/{business_id}/campaigns/{campaign_id}/approve", response_model=CampaignRead)
async def approve_campaign(
    business_id: UUID,
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CampaignRead:
    """Approve a draft or pending campaign before any execution."""
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    existing_campaign = await db.get(MarketingCampaign, campaign_id)
    if not existing_campaign or str(existing_campaign.business_id).replace("-", "") != str(business_id).replace("-", ""):
        raise HTTPException(status_code=404, detail="Campaign not found for this business")
    campaign = await MarketingService(db).approve_campaign(campaign_id, str(current_user.email))
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found or cannot be approved")
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
    existing_campaign = await db.get(MarketingCampaign, campaign_id)
    if not existing_campaign or not _ids_match(existing_campaign.business_id, business_id):
        raise HTTPException(status_code=404, detail="Campaign not found for this business")
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
    existing_campaign = await db.get(MarketingCampaign, campaign_id)
    if not existing_campaign or not _ids_match(existing_campaign.business_id, business_id):
        raise HTTPException(status_code=404, detail="Campaign not found for this business")
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
    existing_campaign = await db.get(MarketingCampaign, campaign_id)
    if not existing_campaign or not _ids_match(existing_campaign.business_id, business_id):
        raise HTTPException(status_code=404, detail="Campaign not found for this business")
    campaign = await MarketingService(db).generate_ab_test_variant(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignRead.model_validate(campaign)


class ContentStudioRequest(BaseModel):
    content_type: str = Field(..., description="e.g. LinkedIn post, Twitter thread")
    tone: str = Field(..., description="e.g. professional, humorous")
    audience: str = Field(..., description="e.g. founders, developers")
    cta: str = Field(..., description="e.g. sign up, read more")
    goal: str = Field(default="", max_length=800)
    product_id: UUID | None = None

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

    selected_product = None
    if payload.product_id:
        selected_product = await ProductService(db).get(payload.product_id)
        if not selected_product or str(selected_product.business_id) != str(business_id):
            raise HTTPException(status_code=404, detail="Product not found")

    usage_svc = UsageService(db)
    await usage_svc.check_limit(current_user.id, "marketing_campaign")
    await usage_svc.check_limit(current_user.id, "ai_request")

    business_context = {
        "name": business.name,
        "niche": business.niche,
        "description": business.description,
        "brand_tone": business.brand_tone,
        "target_audience": business.target_audience,
        "headline": business.headline,
        "product_pitch": business.product_pitch,
    }

    campaign = await MarketingService(db).generate_custom_content(
        business_id=business_id,
        content_type=payload.content_type,
        tone=payload.tone,
        audience=payload.audience,
        cta=payload.cta,
        business_context=business_context,
        goal=payload.goal,
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
    )
    await usage_svc.increment_usage(
        current_user.id,
        "marketing_campaign",
        business_id=business_id,
        source="marketing_content_studio",
        metadata_json={"content_type": payload.content_type, "campaign_id": str(campaign.id)},
    )
    await usage_svc.increment_usage(
        current_user.id,
        "ai_request",
        business_id=business_id,
        source="marketing_content_studio",
        metadata_json={"content_type": payload.content_type},
    )
    await AnalyticsService(db).track(
        AnalyticsEventCreate(
            business_id=business_id,
            product_id=campaign.product_id,
            event_type="marketing_campaign_created",
            source="content_studio",
            metadata_json={
                "campaign_id": str(campaign.id),
                "campaign_type": campaign.campaign_type,
                "content_type": payload.content_type,
                "status": campaign.status,
            },
        )
    )
    return CampaignRead.model_validate(campaign)


@router.patch("/{business_id}/campaigns/{campaign_id}", response_model=CampaignRead)
async def update_campaign(
    business_id: UUID,
    campaign_id: UUID,
    payload: CampaignUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CampaignRead:
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    campaign = await db.get(MarketingCampaign, campaign_id)
    if not campaign or str(campaign.business_id).replace("-", "") != str(business_id).replace("-", ""):
        raise HTTPException(status_code=404, detail="Campaign not found")
    updated = await MarketingService(db).update_campaign_content(
        campaign_id,
        name=payload.name,
        content=payload.content,
        content_text=payload.content_text,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await AnalyticsService(db).track(
        AnalyticsEventCreate(
            business_id=business_id,
            product_id=updated.product_id,
            campaign_id=updated.id,
            event_type="marketing_campaign_updated",
            source="campaign_editor",
            metadata_json={"campaign_id": str(updated.id), "campaign_type": updated.campaign_type},
        )
    )
    return CampaignRead.model_validate(updated)


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


@router.get("/{business_id}/contacts", response_model=list[ContactRead])
async def list_contacts(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ContactRead]:
    """Return real audience/contact records for a business."""
    from sqlalchemy import select

    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    result = await db.execute(
        select(Contact)
        .where(Contact.business_id == business_id)
        .order_by(Contact.created_at.desc())
    )
    return [ContactRead.model_validate(contact) for contact in result.scalars().all()]


@router.post("/{business_id}/contacts", response_model=ContactRead, status_code=201)
async def create_contact(
    business_id: UUID,
    payload: ContactCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactRead:
    """Create a real contact for campaign audiences and sales follow-up."""
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    if not payload.email and not payload.phone:
        raise HTTPException(status_code=400, detail="Contact requires at least email or phone.")
    contact = Contact(
        business_id=business_id,
        name=payload.name,
        email=payload.email.strip().lower() if payload.email else None,
        phone=payload.phone,
        source=payload.source,
        consent_status=payload.consent_status,
        segment=payload.segment,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return ContactRead.model_validate(contact)


@router.post("/{business_id}/contacts/import-csv", response_model=ContactImportResult)
async def import_contacts_csv(
    business_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactImportResult:
    """Import real campaign contacts from CSV.

    Accepted columns: email, name, phone, segment, consent_status, source.
    Rows without email and phone are skipped. Existing emails are not duplicated.
    """
    from sqlalchemy import select

    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV must include a header row.")

    imported_contacts: list[Contact] = []
    skipped_duplicates = 0
    skipped_invalid = 0
    total_rows = 0
    seen_emails: set[str] = set()
    for row in reader:
        total_rows += 1
        normalized = {str(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        email = normalized.get("email", "").lower()
        phone = normalized.get("phone", "")
        if not email and not phone:
            skipped_invalid += 1
            continue
        if email:
            if email in seen_emails:
                skipped_duplicates += 1
                continue
            seen_emails.add(email)
            existing = await db.execute(
                select(Contact.id).where(Contact.business_id == business_id, Contact.email == email)
            )
            if existing.scalar_one_or_none():
                skipped_duplicates += 1
                continue
        contact = Contact(
            business_id=business_id,
            name=normalized.get("name") or None,
            email=email or None,
            phone=phone or None,
            source=normalized.get("source") or "csv_import",
            consent_status=normalized.get("consent_status") or "unknown",
            segment=normalized.get("segment") or None,
        )
        db.add(contact)
        imported_contacts.append(contact)
    await db.commit()
    for contact in imported_contacts:
        await db.refresh(contact)
    return ContactImportResult(
        imported=len(imported_contacts),
        skipped_duplicates=skipped_duplicates,
        skipped_invalid=skipped_invalid,
        total_rows=total_rows,
        contacts=[ContactRead.model_validate(contact) for contact in imported_contacts],
    )


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
    campaign = await db.get(MarketingCampaign, campaign_id)
    if not campaign or not _ids_match(campaign.business_id, business_id):
        raise HTTPException(status_code=404, detail="Campaign not found for this business")
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
            user_id=user_id,
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
    """Run AI optimization without fabricating performance numbers."""
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    campaign = await db.get(MarketingCampaign, campaign_id)
    if not campaign or str(campaign.business_id).replace("-", "") != str(business_id).replace("-", ""):
        raise HTTPException(status_code=404, detail="Campaign not found")
    usage_svc = UsageService(db)
    await usage_svc.check_limit(current_user.id, "ai_request")

    metrics = await MarketingService(db).real_campaign_metrics(campaign_id)
    real_signal_count = int(metrics.get("clicks", 0)) + int(metrics.get("conversions", 0)) + int(metrics.get("opens", 0))
    from app.services.ai_service import AIService

    ai = AIService()
    if real_signal_count < 25 and int(metrics.get("conversions", 0)) < 1:
        opt_prompt = (
            "You are a senior direct-response marketing editor. Optimize the campaign creative and copy only. "
            "There is not enough real analytics data yet, so do not claim performance lift, conversion gains, "
            "or revenue impact. Return ONLY valid JSON with these keys: headline_suggestion, cta_suggestion, "
            "targeting_suggestion, reasoning, next_test.\n\n"
            f"Campaign: {campaign.name}\n"
            f"Type: {campaign.campaign_type}\n"
            f"Business: {business.name}\n"
            f"Current content: {str(campaign.content)[:2500]}"
        )
        optimization_mode = "content_review"
    else:
        opt_prompt = (
            "You are a marketing optimization expert. Analyze only the real campaign metrics provided. "
            "Do not invent performance or predicted lift. Return ONLY valid JSON with these keys: "
            "headline_suggestion, cta_suggestion, targeting_suggestion, reasoning, next_test.\n\n"
            f"Campaign: {campaign.name}\n"
            f"Type: {campaign.campaign_type}\n"
            f"Business: {business.name}\n"
            f"Real metrics: clicks={metrics.get('clicks', 0)}, opens={metrics.get('opens', 0)}, "
            f"conversions={metrics.get('conversions', 0)}, revenue_cents={metrics.get('revenue_cents', 0)}\n"
            f"Current content preview: {str(campaign.content)[:300]}"
        )
        optimization_mode = "performance_review"

    try:
        result = await ai.generate_json(opt_prompt)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    result = {
        **result,
        "analytics_source": "real",
        "optimization_mode": optimization_mode,
        "status": "completed",
        "message": (
            "Content optimized from campaign copy. Real-event optimization remains available once campaign interactions arrive."
            if optimization_mode == "content_review"
            else "Optimization completed from real campaign events."
        ),
    }

    campaign.metrics = {**metrics, "optimization": result, "optimized_at": datetime.utcnow().isoformat()}
    await db.commit()
    await usage_svc.increment_usage(
        current_user.id,
        "ai_request",
        business_id=business_id,
        source="marketing_campaign_optimize",
        metadata_json={"campaign_id": str(campaign_id), "campaign_type": campaign.campaign_type},
    )

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
    """Generate an AI image for a campaign using Hugging Face Inference."""
    from app.services.image_generation_service import ImageGenerationService, ImageGenerationError
    from app.services.brand_system_service import BrandSystemService

    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    campaign = await db.get(MarketingCampaign, campaign_id)
    if not campaign or str(campaign.business_id).replace("-", "") != str(business_id).replace("-", ""):
        raise HTTPException(status_code=404, detail="Campaign not found")
    usage_svc = UsageService(db)
    await usage_svc.check_limit(current_user.id, "image_generation")

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
        raise HTTPException(
            status_code=503,
            detail={
                "code": "IMAGE_GENERATION_FAILED",
                "message": str(exc),
                "provider": "huggingface",
                "next_steps": [
                    "Verify HUGGINGFACE_API_KEY is present in backend/.env.",
                    "Set HUGGINGFACE_IMAGE_MODEL to a working text-to-image model such as stabilityai/stable-diffusion-xl-base-1.0.",
                    "Confirm this machine can reach https://api-inference.huggingface.co; DNS errors must be fixed outside the app.",
                    "Restart the backend after changing provider settings.",
                ],
            },
        )

    campaign.image_url = image_path  # type: ignore[attr-defined]
    db.add(
        CampaignAsset(
            campaign_id=campaign_id,
            platform="all",
            asset_type="image",
            subject=campaign.name,
            content={
                "prompt": prompt,
                "provider": svc.last_provider,
                "model": svc.last_model_used,
                "models_attempted": svc.last_models_attempted,
            },
            creative_url=image_path,
            status="generated",
        )
    )
    await db.commit()
    await usage_svc.increment_usage(
        current_user.id,
        "image_generation",
        business_id=business_id,
        source="campaign_image_generate",
        metadata_json={"campaign_id": str(campaign_id)},
    )

    return {
        "image_url": image_path,
        "campaign_id": str(campaign_id),
        "provider": svc.last_provider,
        "model": svc.last_model_used,
        "models_attempted": svc.last_models_attempted,
    }


# ── Real Publishing ───────────────────────────────────────────────────────────

@router.post("/{business_id}/campaigns/{campaign_id}/publish/{platform}")
async def publish_campaign(
    business_id: UUID,
    campaign_id: UUID,
    platform: str,
    payload: PublishCampaignRequest | None = None,
    current_user: User = Depends(check_publish_rate_limit),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Publish a campaign through official OAuth/API integrations first."""
    from app.services.business_service import BusinessService
    from app.models.marketing import MarketingCampaign
    from app.api.routes.tools import (
        GmailSendPayload,
        AdsDraftPayload,
        NotionPagePayload,
        SlackMessagePayload,
        SocialPostPayload,
        WordPressPostPayload,
        facebook_post,
        gmail_send,
        google_ads_draft,
        instagram_post,
        linkedin_post,
        meta_ads_draft,
        notion_page,
        sendgrid_send,
        slack_message,
        twitter_post,
        wordpress_post,
    )
    from app.core.config import settings
    from app.services.oauth_manager_service import OAuthManagerService
    
    payload = payload or PublishCampaignRequest()
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    campaign = await db.get(MarketingCampaign, campaign_id)
    if not campaign or not _ids_match(campaign.business_id, business_id):
        raise HTTPException(status_code=404, detail="Campaign not found for this business")
    if campaign.status not in {"approved", "pending_publish", "scheduled"}:
        raise HTTPException(status_code=400, detail="Approve this campaign before publishing.")

    asset_content = await _campaign_platform_content(db, campaign_id, platform)
    content = asset_content or campaign.content or {}
    text = _campaign_publish_text(campaign, content)
    media_url = payload.media_url or content.get("image_url") or content.get("creative_url") or campaign.image_url
    ad_payload = AdsDraftPayload(
        campaign_name=campaign.name,
        objective=content.get("objective") or content.get("goal") or "traffic",
        headline=content.get("headline") or content.get("title") or campaign.name,
        body=content.get("body") or content.get("primary_text") or text,
        cta=content.get("cta") or content.get("cta_text"),
        destination_url=content.get("destination_url") or content.get("landing_page_url"),
        daily_budget_cents=content.get("daily_budget_cents"),
        target_audience=content.get("audience") or content.get("target_audience"),
        creative_url=media_url,
    )

    if platform == "email":
        recipients = payload.recipient_emails or []
        if not recipients:
            raise HTTPException(status_code=400, detail="Add at least one real recipient before sending this email campaign.")
        email_payload = GmailSendPayload(
            to=recipients,
            subject=content.get("subject") or campaign.name,
            html=content.get("html_body") or content.get("html"),
            text=content.get("plain_text") or content.get("body") or text,
            from_name=business.name,
        )
        gmail_token = await OAuthManagerService(db).get_token(str(current_user.id), str(business_id), "gmail")
        google_token = await OAuthManagerService(db).get_token(str(current_user.id), str(business_id), "google")
        if settings.sendgrid_api_key:
            try:
                result = await sendgrid_send(email_payload, business_id=business_id, current_user=current_user, db=db)
            except HTTPException as sendgrid_exc:
                if gmail_token or google_token:
                    logger.warning("SendGrid send failed; falling back to Gmail OAuth for campaign %s: %s", campaign_id, sendgrid_exc.detail)
                    result = await gmail_send(email_payload, business_id=business_id, current_user=current_user, db=db)
                    result["fallback_from"] = "sendgrid"
                    result["sendgrid_error"] = str(sendgrid_exc.detail)
                else:
                    raise
        elif gmail_token or google_token:
            result = await gmail_send(email_payload, business_id=business_id, current_user=current_user, db=db)
        else:
            raise HTTPException(status_code=400, detail="No real email sender is ready. Configure SENDGRID_API_KEY or connect Gmail before sending.")
    elif platform == "sendgrid":
        recipients = payload.recipient_emails or []
        if not recipients:
            raise HTTPException(status_code=400, detail="Add at least one real recipient before sending with SendGrid.")
        result = await sendgrid_send(
            GmailSendPayload(
                to=recipients,
                subject=content.get("subject") or campaign.name,
                html=content.get("html_body") or content.get("html"),
                text=content.get("plain_text") or content.get("body") or text,
                from_name=business.name,
            ),
            business_id=business_id,
            current_user=current_user,
            db=db,
        )
    elif platform == "linkedin":
        result = await linkedin_post(SocialPostPayload(text=text, media_url=media_url), business_id=business_id, current_user=current_user, db=db)
    elif platform == "twitter":
        result = await twitter_post(SocialPostPayload(text=text, media_url=media_url), business_id=business_id, current_user=current_user, db=db)
    elif platform == "facebook":
        if not payload.page_id:
            raise HTTPException(status_code=400, detail="Facebook Page ID is required for real Facebook publishing.")
        result = await facebook_post(SocialPostPayload(text=text, media_url=media_url, page_id=payload.page_id), business_id=business_id, current_user=current_user, db=db)
    elif platform == "instagram":
        if not payload.account_id:
            raise HTTPException(status_code=400, detail="Instagram Professional account ID is required for real Instagram publishing.")
        if not media_url:
            raise HTTPException(status_code=400, detail="Instagram publishing requires a public campaign image URL.")
        result = await instagram_post(SocialPostPayload(text=text, media_url=media_url, account_id=payload.account_id), business_id=business_id, current_user=current_user, db=db)
    elif platform == "slack":
        if not payload.channel:
            raise HTTPException(status_code=400, detail="Choose a Slack channel before sending.")
        result = await slack_message(SlackMessagePayload(channel=payload.channel, text=text), business_id=business_id, current_user=current_user, db=db)
    elif platform == "notion":
        if not payload.parent_page_id:
            raise HTTPException(status_code=400, detail="Choose a Notion parent page before creating a page.")
        result = await notion_page(NotionPagePayload(parent_page_id=payload.parent_page_id, title=campaign.name, content=text), business_id=business_id, current_user=current_user, db=db)
    elif platform == "wordpress":
        body = content.get("content_markdown") or content.get("body") or text
        result = await wordpress_post(WordPressPostPayload(title=content.get("title") or campaign.name, content=body, status="draft", site_id=payload.site_id), business_id=business_id, current_user=current_user, db=db)
    elif platform == "google_ads":
        result = await google_ads_draft(ad_payload, business_id=business_id, current_user=current_user, db=db)
    elif platform == "meta_ads":
        result = await meta_ads_draft(ad_payload, business_id=business_id, current_user=current_user, db=db)
    else:
        raise HTTPException(status_code=501, detail=f"{platform.title()} official API publishing is not implemented. Use Browser Agent only if you have configured a browser vault account.")

    publish_status = result.get("status") or "published"
    if platform in {"email", "sendgrid"} and publish_status == "sent":
        campaign.status = "sent"
    elif platform in {"google_ads", "meta_ads"} and publish_status == "draft_ready":
        campaign.status = "pending_publish"
    elif publish_status == "published":
        campaign.status = "published"
    else:
        campaign.status = "approved"
    campaign.lifecycle_status = campaign.status
    metrics = dict(campaign.metrics or {})
    metrics["official_api_publish"] = {
        "platform": platform,
        "status": publish_status,
        "attempted_at": datetime.utcnow().isoformat(),
        "result": result,
    }
    if publish_status in {"sent", "published"}:
        metrics["official_api_publish"]["published_at"] = datetime.utcnow().isoformat()
    campaign.metrics = metrics
    await db.commit()

    return {
        **result,
        "campaign_id": str(campaign_id),
        "message": result.get("message") or f"{platform.title()} publish was verified through official OAuth/API mode.",
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

    campaign = await db.get(MarketingCampaign, campaign_id)
    if not campaign or str(campaign.business_id).replace("-", "") != str(business_id).replace("-", ""):
        return await _error_stream("Campaign not found")

    business = await BusinessService(db).get(business_id, user_id=UUID(user_id))
    if not business:
        return await _error_stream("Business not found or access denied")

    if platform in {"google_ads", "meta_ads"}:
        return await _error_stream(f"{platform} is not supported in browser publish mode")

    if campaign.status in {"draft", "pending_approval", "rejected"}:
        return await _error_stream("Approve this campaign before publishing it")
    await UsageService(db).check_limit(UUID(user_id), "browser_agent_run")
    await UsageService(db).increment_usage(
        UUID(user_id),
        "browser_agent_run",
        business_id=business_id,
        source="marketing_browser_publish",
        metadata_json={"campaign_id": str(campaign_id), "platform": platform},
    )

    asset_content = await _campaign_platform_content(db, campaign_id, platform)
    if asset_content:
        setattr(campaign, "_platform_content", asset_content)
    goal = _build_browser_publish_goal(platform, business.name, campaign)

    async def _stream():
        from uuid import uuid4
        from app.services.browser_agent.run_manager import browser_run_manager

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
            if saved_account is None:
                saved_account = await account_service.get(
                    user_id=UUID(user_id),
                    business_id=None,
                    platform=platform,
                )
            if saved_account is None and platform == "email":
                saved_account = await account_service.get(
                    user_id=UUID(user_id),
                    business_id=business_id,
                    platform="gmail",
                )
                if saved_account is None:
                    saved_account = await account_service.get(
                        user_id=UUID(user_id),
                        business_id=None,
                        platform="gmail",
                    )
            fallback_account = None
            if saved_account is None and platform in {"linkedin", "instagram", "facebook", "email"}:
                fallback_account = await account_service.get(
                    user_id=UUID(user_id),
                    business_id=business_id,
                    platform="browser_automation",
                )
                if fallback_account is None:
                    fallback_account = await account_service.get(
                        user_id=UUID(user_id),
                        business_id=None,
                        platform="browser_automation",
                    )
            revealed_account = account_service.reveal(saved_account) if saved_account else (
                account_service.reveal(fallback_account) if fallback_account else None
            )
            if revealed_account:
                bootstrap = PlatformLoginService(agent.session_manager)
                login_platform = "gmail" if platform == "email" else platform
                bootstrap_result = await bootstrap.ensure_session(platform=login_platform, credentials=revealed_account)
                yield f"data: {json.dumps({'type': 'status', 'status': bootstrap_result.get('status', 'running'), 'message': bootstrap_result.get('message', ''), 'platform': platform, 'phase': 'session_bootstrap'})}\n\n"
                if bootstrap_result.get("status") == "failed":
                    completion_state = "needs_login"
                    final_summary = bootstrap_result.get("message") or f"{platform} login could not be restored"
                    yield f"data: {json.dumps({'type': 'result', 'status': 'needs_login', 'text': final_summary, 'campaign_id': str(campaign_id), 'platform': platform})}\n\n"
                    yield f"data: {json.dumps({'type': 'done', 'status': 'needs_login', 'campaign_id': str(campaign_id), 'platform': platform})}\n\n"
                    return
            else:
                yield f"data: {json.dumps({'type': 'status', 'status': 'checking_session', 'message': f'No saved {platform} browser vault account found. The browser must already be logged in, or the run will stop with needs_login.', 'platform': platform, 'phase': 'session_bootstrap'})}\n\n"

            direct_publishable = {"linkedin", "instagram"}
            if platform in direct_publishable:
                direct_run_id = str(uuid4())
                browser_run_manager.register(direct_run_id, goal)
                yield f"data: {json.dumps({'type': 'start', 'run_id': direct_run_id, 'goal': goal, 'campaign_id': str(campaign_id), 'platform': platform})}\n\n"
                direct_service = PlatformPublishService(agent.session_manager)
                async for event in direct_service.publish(
                    platform=platform,
                    text=_campaign_publish_text(campaign, asset_content),
                    image_hint=(asset_content or campaign.content or {}).get("image_path") or (asset_content or campaign.content or {}).get("image_url") or campaign.image_url,
                    run_id=direct_run_id,
                ):
                    event.setdefault("campaign_id", str(campaign_id))
                    event.setdefault("platform", platform)
                    event.setdefault("run_id", direct_run_id)
                    if event.get("type") == "result":
                        final_summary = str(event.get("text", ""))
                    if event.get("type") == "done":
                        status_value = str(event.get("status") or "failed")
                        published = status_value == "published"
                        completion_state = "published" if published else status_value
                        browser_run_manager.complete(direct_run_id, completion_state if completion_state in {"completed", "failed", "stopped", "needs_more_steps", "awaiting_final_confirmation", "paused", "running"} else "completed")
                    yield f"data: {json.dumps(event, default=str)}\n\n"
            else:
                async for event in agent.iter_events(goal):
                    event.setdefault("campaign_id", str(campaign_id))
                    event.setdefault("platform", platform)
                    if event.get("type") == "result":
                        final_summary = str(event.get("text", ""))
                    if event.get("type") == "done":
                        status_value = str(event.get("status") or "failed")
                        published = status_value == "published"
                        completion_state = "published" if published else status_value
                    yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as exc:
            logger.exception("Browser publish stream failed: %s", exc)
            final_summary = _public_browser_error_message(exc)
            completion_state = "failed"
            yield f"data: {json.dumps({'type': 'error', 'status': 'failed', 'message': final_summary, 'platform': platform, 'phase': 'browser_publish_failed'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'status': 'failed', 'campaign_id': str(campaign_id), 'platform': platform})}\n\n"
        finally:
            db_campaign = await db.get(MarketingCampaign, campaign_id)
            if db_campaign:
                db_campaign.status = "published" if published else "approved"
                metrics = dict(db_campaign.metrics or {})
                metrics["browser_publish"] = {
                    "platform": platform,
                    "status": completion_state,
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
    if not campaign or not _ids_match(campaign.business_id, business_id):
        raise HTTPException(status_code=404, detail="Campaign not found for this business")
    if campaign.status not in {"approved", "scheduled"} and campaign.lifecycle_status not in {"approved", "scheduled"}:
        raise HTTPException(status_code=400, detail="Approve this campaign before scheduling.")

    # Convert to UTC
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(payload.scheduled_at.replace("Z", "+00:00"))
        start_dt = dt.astimezone(timezone.utc)
        scheduled_utc = start_dt.isoformat()
    except Exception:
        start_dt = datetime.now(timezone.utc)
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
    db.add(
        MarketingCalendarEvent(
            business_id=business_id,
            campaign_id=campaign_id,
            title=f"{payload.platform.title()} campaign: {campaign.name}",
            description="Scheduled campaign action. Google Calendar sync can attach an external event id after OAuth sync.",
            start_time=start_dt,
            end_time=None,
            platform=payload.platform,
            status="scheduled",
        )
    )
    campaign.status = "scheduled"
    campaign.lifecycle_status = "scheduled"
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
    """Return real marketing calendar events and legacy scheduled posts ordered by date."""
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
    calendar_result = await db.execute(
        select(MarketingCalendarEvent)
        .where(MarketingCalendarEvent.business_id == business_id)
        .order_by(MarketingCalendarEvent.start_time.asc())
    )
    events = [
        {
            "id": str(event.id),
            "business_id": str(event.business_id),
            "campaign_id": str(event.campaign_id) if event.campaign_id else None,
            "google_event_id": event.google_event_id,
            "title": event.title,
            "description": event.description,
            "platform": event.platform,
            "status": event.status,
            "scheduled_at_utc": event.start_time.isoformat(),
            "end_time": event.end_time.isoformat() if event.end_time else None,
            "source": "marketing_calendar_events",
        }
        for event in calendar_result.scalars().all()
    ]
    legacy = [{**p.to_dict(), "source": "scheduled_posts"} for p in posts]
    return sorted([*events, *legacy], key=lambda item: item.get("scheduled_at_utc") or item.get("start_time") or "")


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/{business_id}/analytics")
async def get_marketing_analytics(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return real campaign metrics only. No simulated performance numbers."""

    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    campaigns = await MarketingService(db).list_campaigns(business_id)

    campaign_stats = []
    for c in campaigns:
        metrics = await MarketingService(db).real_campaign_metrics(c.id)
        campaign_stats.append({
            "campaign_id": str(c.id),
            "campaign_name": c.name,
            "campaign_type": c.campaign_type,
            "status": c.status,
            "impressions": 0,
            "clicks": metrics["clicks"],
            "conversions": metrics["conversions"],
            "ctr": 0,
            "spend_usd": 0,
            "revenue_usd": round(metrics["revenue_cents"] / 100, 2),
            "roas": 0,
            "analytics_source": "real",
        })

    total_real_events = sum(c["clicks"] + c["conversions"] for c in campaign_stats)
    ai_insights = (
        "AI creative optimization is available now; performance optimization will use real campaign events once they arrive."
        if total_real_events == 0
        else "Real campaign events are available. Optimization can now analyze actual user behavior."
    )

    return {
        "business_id": str(business_id),
        "campaigns": campaign_stats,
        "totals": {
            "impressions": sum(c["impressions"] for c in campaign_stats),
            "clicks": sum(c["clicks"] for c in campaign_stats),
            "conversions": sum(c["conversions"] for c in campaign_stats),
            "spend_usd": sum(c["spend_usd"] for c in campaign_stats),
            "revenue_usd": sum(c["revenue_usd"] for c in campaign_stats),
            "analytics_source": "real",
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
    """Manual metric snapshots are disabled. Use real tracking/conversion endpoints."""
    raise HTTPException(
        status_code=410,
        detail="Manual metric snapshots are disabled. Metrics are recorded only through real click, send, conversion, and provider webhook events.",
    )
