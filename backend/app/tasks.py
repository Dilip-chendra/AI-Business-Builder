"""Celery tasks for background processing.

These tasks wrap service-layer calls so long-running work runs outside the
API request/response cycle.  Each task creates its own DB session.

NOTE: This module is only imported by the Celery worker process.
      The web app dispatches tasks by name (string) to avoid importing Celery.
"""
from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_celery():
    """Lazy import of celery_app — only resolves when the worker runs."""
    from app.worker import celery_app
    return celery_app


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_db_session():
    """Create a new async DB session for use inside a Celery task."""
    from app.db.session import async_session_factory
    return async_session_factory()


# ── Task definitions (registered when the worker imports this module) ─────────

def _register_tasks():
    """Register all Celery tasks. Called by the worker, not the web app."""
    celery_app = _get_celery()

    @celery_app.task(bind=True, max_retries=3, default_retry_delay=30, name="app.tasks.generate_business_task")
    def generate_business_task(self, payload_dict: dict, user_id: str | None = None):
        async def _run():
            from app.schemas.business import BusinessGenerateRequest
            from app.services.business_service import BusinessService
            from app.services.email_service import EmailService

            async with _get_db_session() as db:
                payload = BusinessGenerateRequest(**payload_dict)
                business = await BusinessService(db).generate_and_store(payload, user_id=user_id)
                logger.info("Background task: business generated  id=%s", business.id)
                if user_id:
                    from app.models.user import User
                    user = await db.get(User, UUID(user_id))
                    if user and user.email:
                        await EmailService().send_business_created(
                            to=user.email,
                            business_name=business.name,
                            business_id=str(business.id),
                        )
                return str(business.id)
        try:
            return _run_async(_run())
        except Exception as exc:
            logger.error("generate_business_task failed: %s", exc)
            raise self.retry(exc=exc)

    @celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="app.tasks.run_agent_pipeline_task")
    def run_agent_pipeline_task(self, business_id: str, apply_decisions: bool = False):
        async def _run():
            from app.agents.coordinator import AgentCoordinator
            async with _get_db_session() as db:
                coordinator = AgentCoordinator(db)
                result = await coordinator.run_full_pipeline(
                    business_id=UUID(business_id),
                    apply_decisions=apply_decisions,
                )
                logger.info("Agent pipeline complete  business_id=%s", business_id)
                return result
        try:
            return _run_async(_run())
        except Exception as exc:
            logger.error("run_agent_pipeline_task failed: %s", exc)
            raise self.retry(exc=exc)

    @celery_app.task(name="app.tasks.run_agent_loop_task")
    def run_agent_loop_task():
        async def _run():
            from sqlalchemy import select
            from app.models.business import Business
            async with _get_db_session() as db:
                result = await db.execute(select(Business.id))
                business_ids = [str(row[0]) for row in result.all()]
            logger.info("Agent loop: dispatching pipelines for %d businesses", len(business_ids))
            for bid in business_ids:
                run_agent_pipeline_task.delay(bid, apply_decisions=True)
        _run_async(_run())

    @celery_app.task(bind=True, max_retries=2, default_retry_delay=10, name="app.tasks.aggregate_analytics_task")
    def aggregate_analytics_task(self, business_id: str):
        async def _run():
            from app.services.analytics_service import AnalyticsService
            async with _get_db_session() as db:
                await AnalyticsService(db).summary(UUID(business_id))
                logger.info("Analytics cache refreshed  business_id=%s", business_id)
        try:
            _run_async(_run())
        except Exception as exc:
            logger.error("aggregate_analytics_task failed: %s", exc)
            raise self.retry(exc=exc)

    @celery_app.task(name="app.tasks.send_email_task")
    def send_email_task(template: str, to: str, **context):
        async def _run():
            from app.services.email_service import EmailService
            svc = EmailService()
            if template == "welcome":
                await svc.send_welcome(to=to, full_name=context.get("full_name"))
            elif template == "order_confirmation":
                await svc.send_order_confirmation(
                    to=to,
                    business_name=context.get("business_name", ""),
                    product_name=context.get("product_name", ""),
                    amount_cents=context.get("amount_cents", 0),
                    currency=context.get("currency", "usd"),
                )
            elif template == "business_created":
                await svc.send_business_created(
                    to=to,
                    business_name=context.get("business_name", ""),
                    business_id=context.get("business_id", ""),
                )
            else:
                logger.warning("Unknown email template: %s", template)
        _run_async(_run())

    # ── Job-based tasks for long-running operations ────────────────────────────

    @celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="app.tasks.generate_seo_blog_job_task")
    def generate_seo_blog_job_task(self, job_id: str, business_id: str, payload: dict):
        """Generate SEO blog and track progress via Job model with smart provider routing."""
        async def _run():
            from app.services.job_service import JobService
            from app.services.marketing_service import MarketingService
            from app.services.business_service import BusinessService
            from app.services.ai_orchestrator import generate_json_smart, ProviderChoice
            from app.models.job import JobStatus

            async with _get_db_session() as db:
                job_svc = JobService(db)
                job = await job_svc.set_running(job_id, celery_task_id=self.request.id)
                if not job:
                    logger.error("Job not found: %s", job_id)
                    return None

                try:
                    await job_svc.update_progress(job_id, 20, "Fetching business context...")
                    business = await BusinessService(db).get(UUID(business_id))
                    if not business:
                        raise ValueError("Business not found")

                    await job_svc.update_progress(job_id, 40, "Generating SEO blog content with smart provider...")
                    
                    # Updated marketing service to use orchestrator internally
                    marketing_svc = MarketingService(db)
                    content = await marketing_svc.generate_seo_blog(
                        business_id=UUID(business_id),
                        topic=payload.get("topic", ""),
                        target_keyword=payload.get("target_keyword", ""),
                        business_context={
                            "name": business.name,
                            "niche": business.niche,
                            "target_audience": business.target_audience,
                        },
                    )

                    await job_svc.update_progress(job_id, 90, "Finalizing...")
                    result = {
                        "content_id": str(content.id),
                        "title": content.title,
                        "slug": content.slug,
                        "word_count": content.word_count,
                        "status": content.status,
                    }
                    await job_svc.mark_completed(job_id, result=result)
                    logger.info("SEO blog generated successfully  job_id=%s", job_id)
                    return str(content.id)

                except Exception as exc:
                    logger.exception("SEO blog generation failed: %s", exc)
                    await job_svc.mark_failed(
                        job_id,
                        error_message=str(exc),
                        error_traceback=__import__("traceback").format_exc(),
                        should_retry=True,
                    )
                    raise

        try:
            return _run_async(_run())
        except Exception as exc:
            logger.error("generate_seo_blog_job_task failed: %s", exc)
            raise self.retry(exc=exc)

    @celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="app.tasks.generate_email_campaign_job_task")
    def generate_email_campaign_job_task(self, job_id: str, business_id: str, payload: dict):
        """Generate email campaign and track progress via Job model."""
        async def _run():
            from app.services.job_service import JobService
            from app.services.marketing_service import MarketingService
            from app.services.business_service import BusinessService

            async with _get_db_session() as db:
                job_svc = JobService(db)
                job = await job_svc.set_running(job_id, celery_task_id=self.request.id)
                if not job:
                    logger.error("Job not found: %s", job_id)
                    return None

                try:
                    await job_svc.update_progress(job_id, 20, "Fetching business context...")
                    business = await BusinessService(db).get(UUID(business_id))
                    if not business:
                        raise ValueError("Business not found")

                    await job_svc.update_progress(job_id, 50, "Generating email campaign...")
                    marketing_svc = MarketingService(db)
                    campaign = await marketing_svc.generate_email_campaign(
                        business_id=UUID(business_id),
                        campaign_name=payload.get("name", "Campaign"),
                        goal=payload.get("goal", ""),
                        recipient_count=payload.get("recipient_count", 0),
                    )

                    await job_svc.update_progress(job_id, 90, "Finalizing...")
                    result = {
                        "campaign_id": str(campaign.id),
                        "name": campaign.name,
                        "status": campaign.status,
                        "content_preview": str(campaign.content)[:200],
                    }
                    await job_svc.mark_completed(job_id, result=result)
                    logger.info("Email campaign generated successfully  job_id=%s", job_id)
                    return str(campaign.id)

                except Exception as exc:
                    logger.exception("Email campaign generation failed: %s", exc)
                    await job_svc.mark_failed(
                        job_id,
                        error_message=str(exc),
                        error_traceback=__import__("traceback").format_exc(),
                        should_retry=True,
                    )
                    raise

        try:
            return _run_async(_run())
        except Exception as exc:
            logger.error("generate_email_campaign_job_task failed: %s", exc)
            raise self.retry(exc=exc)

    @celery_app.task(bind=True, max_retries=2, default_retry_delay=30, name="app.tasks.process_code_edit_job_task")
    def process_code_edit_job_task(self, job_id: str, payload: dict):
        """Process AI code edit and track progress via Job model."""
        async def _run():
            from app.services.job_service import JobService
            from app.services.ai_orchestrator import generate_text_smart, ProviderChoice

            async with _get_db_session() as db:
                job_svc = JobService(db)
                job = await job_svc.set_running(job_id, celery_task_id=self.request.id)
                if not job:
                    logger.error("Job not found: %s", job_id)
                    return None

                try:
                    await job_svc.update_progress(job_id, 10, "Initializing AI orchestrator...")
                    
                    instruction = payload.get("instruction", "")
                    max_tokens = payload.get("max_tokens", 2000)

                    await job_svc.update_progress(job_id, 50, "Processing code edit with smart provider...")
                    
                    # Use smart orchestrator for intelligent provider selection
                    result = await generate_text_smart(
                        prompt=instruction,
                        prefer_provider=ProviderChoice.AUTO,  # Auto-selects based on complexity
                    )

                    await job_svc.update_progress(job_id, 90, "Finalizing...")
                    final_result = {
                        "edited_code": result,
                        "instruction": instruction,
                        "tokens_estimated": max_tokens,
                    }
                    await job_svc.mark_completed(job_id, result=final_result)
                    logger.info("Code edit processed successfully  job_id=%s", job_id)
                    return result

                except Exception as exc:
                    logger.exception("Code edit processing failed: %s", exc)
                    await job_svc.mark_failed(
                        job_id,
                        error_message=str(exc),
                        error_traceback=__import__("traceback").format_exc(),
                        should_retry=True,
                    )
                    raise

        try:
            return _run_async(_run())
        except Exception as exc:
            logger.error("process_code_edit_job_task failed: %s", exc)
            raise self.retry(exc=exc)

    @celery_app.task(bind=True, max_retries=1, default_retry_delay=60, name="app.tasks.publish_via_browser_agent_task")
    def publish_via_browser_agent_task(self, campaign_id: str, platform: str):
        """Use the Playwright Browser Agent to autonomously log in and publish content."""
        async def _run():
            import json
            from app.models.marketing import MarketingCampaign
            from app.services.browser_agent.browser_agent import BrowserAgent

            async with _get_db_session() as db:
                campaign = await db.get(MarketingCampaign, UUID(campaign_id))
                if not campaign:
                    logger.error("Campaign not found for browser publishing: %s", campaign_id)
                    return

                logger.info("Starting autonomous browser publishing for campaign %s on %s", campaign_id, platform)
                
                # Format the goal
                content_json = json.dumps(campaign.content, indent=2)
                goal = (
                    f"Navigate to {platform}. Log in to the platform. "
                    f"Create a new post/article with the following content:\n\n{content_json}\n\n"
                    f"Publish it. If it asks for confirmation, confirm. "
                    f"Once successfully published, take a screenshot of the published post."
                )

                try:
                    agent = BrowserAgent(
                        db=db,
                        business_id=str(campaign.business_id),
                        headless=settings.browser_headless,
                        max_steps=max(settings.browser_agent_max_steps, 14),
                    )
                    result = await agent.run(goal)
                    campaign.status = "published" if result.status == "done" else "failed"
                    await db.commit()
                    logger.info(
                        "Browser publishing finished for %s with status=%s",
                        campaign_id,
                        campaign.status,
                    )
                except Exception as exc:
                    logger.error("Browser publishing failed: %s", exc)
                    campaign.status = "failed"
                    await db.commit()
                    raise

        try:
            return _run_async(_run())
        except Exception as exc:
            logger.error("publish_via_browser_agent_task failed: %s", exc)
            raise self.retry(exc=exc)

    return {
        "generate_business_task": generate_business_task,
        "run_agent_pipeline_task": run_agent_pipeline_task,
        "run_agent_loop_task": run_agent_loop_task,
        "aggregate_analytics_task": aggregate_analytics_task,
        "send_email_task": send_email_task,
        "generate_seo_blog_job_task": generate_seo_blog_job_task,
        "generate_email_campaign_job_task": generate_email_campaign_job_task,
        "process_code_edit_job_task": process_code_edit_job_task,
        "publish_via_browser_agent_task": publish_via_browser_agent_task,
    }


# Register tasks when this module is imported by the worker.
try:
    _tasks = _register_tasks()
except Exception:
    # Will be registered when the worker fully initializes
    _tasks = {}

async def campaign_scheduling_task():
    """Background task that polls ScheduledPost records and publishes them."""
    import json
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.db.session import async_session_factory
    from app.models.scheduled_post import ScheduledPost
    from app.models.oauth_token import OAuthToken
    from app.services.publishing_service import PublishingService
    from app.services.oauth_manager_service import OAuthManagerService

    logger.info("Starting campaign scheduling task loop...")
    while True:
        try:
            async with async_session_factory() as db:
                now_utc = datetime.now(timezone.utc).isoformat()
                result = await db.execute(
                    select(ScheduledPost)
                    .where(ScheduledPost.status == "pending")
                    .where(ScheduledPost.scheduled_at_utc <= now_utc)
                )
                posts = result.scalars().all()

                if posts:
                    oauth_svc = OAuthManagerService(db)
                    pub_svc = PublishingService(oauth_svc)

                    for post in posts:
                        try:
                            # Try to get OAuth token for the business and platform
                            token_result = await db.execute(
                                select(OAuthToken).where(
                                    OAuthToken.business_id == str(post.business_id),
                                    OAuthToken.platform == post.platform
                                )
                            )
                            token = token_result.scalars().first()
                            if not token or token.status != "connected":
                                raise Exception(f"No valid token for platform {post.platform}")

                            token = await oauth_svc.refresh_if_needed(token)

                            content = json.loads(post.content_json)
                            if post.platform == "linkedin":
                                await pub_svc.publish_linkedin_post(token, content)
                            elif post.platform == "twitter":
                                await pub_svc.publish_twitter_post(token, content)
                            elif post.platform == "facebook":
                                await pub_svc.publish_facebook_post(token, content)
                            elif post.platform == "instagram":
                                await pub_svc.publish_instagram_post(token, content)
                            elif post.platform == "wordpress":
                                await pub_svc.publish_wordpress_post(token, content)
                            else:
                                raise Exception(f"Unsupported platform {post.platform}")

                            post.status = "published"
                        except Exception as exc:
                            logger.error("Failed to publish scheduled post %s: %s", post.id, exc)
                            post.status = "failed"
                            
                        await db.commit()
        except asyncio.CancelledError:
            logger.info("Campaign scheduling task cancelled.")
            break
        except Exception as exc:
            logger.error("Error in campaign scheduling task: %s", exc)
        
        await asyncio.sleep(30)
