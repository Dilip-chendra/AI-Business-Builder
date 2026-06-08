"""Backend tool endpoints used by AI agents for connected integrations."""
from __future__ import annotations

import base64
from email.message import EmailMessage
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.oauth_token import OAuthToken
from app.models.user import User
from app.services.business_service import BusinessService
from app.services.integration_audit_service import IntegrationAuditService
from app.services.oauth_manager_service import OAuthManagerService, _decrypt
from app.core.config import settings

router = APIRouter()


class GmailSendPayload(BaseModel):
    to: list[str]
    subject: str
    html: str | None = None
    text: str | None = None
    from_name: str | None = None
    reply_to: str | None = None


class SocialPostPayload(BaseModel):
    text: str
    media_url: str | None = None
    page_id: str | None = None
    account_id: str | None = None


class SlackMessagePayload(BaseModel):
    channel: str
    text: str


class NotionPagePayload(BaseModel):
    parent_page_id: str
    title: str
    content: str


class WordPressPostPayload(BaseModel):
    title: str
    content: str
    status: str = "draft"
    site_id: str | None = None


class AdsDraftPayload(BaseModel):
    campaign_name: str
    objective: str | None = None
    headline: str | None = None
    body: str | None = None
    cta: str | None = None
    destination_url: str | None = None
    daily_budget_cents: int | None = None
    target_audience: str | None = None
    creative_url: str | None = None


async def _require_business(db: AsyncSession, current_user: User, business_id: UUID):
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


async def _require_oauth_token(db: AsyncSession, current_user: User, business_id: UUID, platform: str, action: str) -> tuple[OAuthToken, str]:
    await _require_business(db, current_user, business_id)
    manager = OAuthManagerService(db)
    oauth_token = await manager.get_token(str(current_user.id), str(business_id), platform)
    if platform == "gmail" and (not oauth_token or oauth_token.status != "connected"):
        oauth_token = await manager.get_token(str(current_user.id), str(business_id), "google")
    if not oauth_token or oauth_token.status != "connected":
        await IntegrationAuditService(db).record(
            user_id=current_user.id,
            business_id=business_id,
            provider=platform,
            action=action,
            status="blocked",
            message=f"{platform.title()} is not connected.",
        )
        raise HTTPException(status_code=400, detail=f"Connect {platform.title()} before using this AI tool.")
    oauth_token = await manager.refresh_if_needed(oauth_token)
    if oauth_token.status != "connected" or not oauth_token.access_token_enc:
        raise HTTPException(status_code=400, detail=f"{platform.title()} connection expired. Please reconnect.")
    secret = settings.token_encryption_key or settings.encryption_key
    try:
        access_token = _decrypt(oauth_token.access_token_enc, secret)
    except Exception:
        access_token = _decrypt(oauth_token.access_token_enc, settings.jwt_secret_key)
    return oauth_token, access_token


async def _require_access_token(db: AsyncSession, current_user: User, business_id: UUID, platform: str, action: str) -> str:
    _oauth_token, access_token = await _require_oauth_token(db, current_user, business_id, platform, action)
    return access_token


def _provider_error(provider: str, response: httpx.Response, fallback: str) -> HTTPException:
    try:
        payload = response.json()
    except Exception:
        payload = {}
    message = payload.get("error_description") or payload.get("message") or fallback
    if isinstance(payload.get("error"), dict):
        message = payload["error"].get("message") or message
    next_steps: list[str] = []
    if provider.lower() == "sendgrid":
        next_steps = [
            "Verify the sender identity or sending domain in SendGrid.",
            "Set SENDGRID_FROM_EMAIL to that verified sender in backend/.env.",
            "Confirm the API key has Mail Send permission.",
            "Restart the backend after changing email settings.",
        ]
    elif provider.lower() == "gmail":
        next_steps = ["Reconnect Google/Gmail with gmail.send permission."]
    elif provider.lower() == "linkedin":
        next_steps = ["Reconnect LinkedIn and confirm the app has w_member_social approval."]
    return HTTPException(
        status_code=response.status_code,
        detail={
            "code": f"{provider.upper().replace('/', '_')}_API_ERROR",
            "message": f"{provider} API error: {message}",
            "provider": provider,
            "status_code": response.status_code,
            "next_steps": next_steps,
        },
    )


@router.post("/gmail/send")
async def gmail_send(
    payload: GmailSendPayload,
    business_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    audit = IntegrationAuditService(db)
    access_token = await _require_access_token(db, current_user, business_id, "gmail", "gmail_send")
    message = EmailMessage()
    message["To"] = ", ".join(payload.to)
    message["Subject"] = payload.subject
    if payload.from_name:
        message["From"] = payload.from_name
    if payload.reply_to:
        message["Reply-To"] = payload.reply_to
    if payload.html:
        message.set_content(payload.text or "This email requires an HTML-capable email client.")
        message.add_alternative(payload.html, subtype="html")
    else:
        message.set_content(payload.text or "")
    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8").rstrip("=")
    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"raw": encoded},
        )
    if response.status_code >= 400:
        await audit.record(
            user_id=current_user.id,
            business_id=business_id,
            provider="gmail",
            action="gmail_send",
            status="failed",
            message="Gmail rejected the send request.",
            metadata={"status_code": response.status_code},
        )
        raise HTTPException(status_code=response.status_code, detail="Gmail rejected the send request. Reconnect Gmail with gmail.send permission.")
    data = response.json()
    await audit.record(
        user_id=current_user.id,
        business_id=business_id,
        provider="gmail",
        action="gmail_send",
        status="success",
        message="Gmail message sent.",
        metadata={"message_id": data.get("id"), "thread_id": data.get("threadId")},
    )
    return {"status": "sent", "provider": "gmail", "message_id": data.get("id"), "thread_id": data.get("threadId")}


@router.post("/sendgrid/send")
async def sendgrid_send(
    payload: GmailSendPayload,
    business_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _require_business(db, current_user, business_id)
    if not settings.sendgrid_api_key:
        await IntegrationAuditService(db).record(
            user_id=current_user.id,
            business_id=business_id,
            provider="sendgrid",
            action="sendgrid_send",
            status="blocked",
            message="SendGrid is not configured.",
        )
        raise HTTPException(status_code=400, detail="SendGrid not configured. Add SENDGRID_API_KEY to backend/.env.")

    from_email = settings.sendgrid_from_email or settings.email_from
    body = {
        "personalizations": [{"to": [{"email": email} for email in payload.to]}],
        "from": {"email": from_email, "name": payload.from_name or settings.email_from_name},
        "subject": payload.subject,
        "content": [],
    }
    if payload.reply_to:
        body["reply_to"] = {"email": payload.reply_to}
    if payload.text:
        body["content"].append({"type": "text/plain", "value": payload.text})
    if payload.html:
        body["content"].append({"type": "text/html", "value": payload.html})
    if not body["content"]:
        body["content"].append({"type": "text/plain", "value": ""})

    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {settings.sendgrid_api_key}", "Content-Type": "application/json"},
            json=body,
        )
    if response.status_code >= 400:
        await IntegrationAuditService(db).record(
            user_id=current_user.id,
            business_id=business_id,
            provider="sendgrid",
            action="sendgrid_send",
            status="failed",
            message="SendGrid rejected the send request.",
            metadata={"status_code": response.status_code},
        )
        raise _provider_error(
            "SendGrid",
            response,
            f"SendGrid rejected the send request. Verify sender identity for {from_email} or set SENDGRID_FROM_EMAIL to a verified sender.",
        )
    message_id = response.headers.get("x-message-id")
    await IntegrationAuditService(db).record(
        user_id=current_user.id,
        business_id=business_id,
        provider="sendgrid",
        action="sendgrid_send",
        status="success",
        message="SendGrid message accepted.",
        metadata={"message_id": message_id, "recipients": len(payload.to)},
    )
    return {"status": "sent", "provider": "sendgrid", "message_id": message_id, "accepted": True}


@router.post("/linkedin/post")
async def linkedin_post(payload: SocialPostPayload, business_id: UUID = Query(...), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    oauth_token, access_token = await _require_oauth_token(db, current_user, business_id, "linkedin", "linkedin_post")
    if not oauth_token.account_id:
        async with httpx.AsyncClient(timeout=20.0) as client:
            profile_response = await client.get("https://api.linkedin.com/v2/userinfo", headers={"Authorization": f"Bearer {access_token}"})
        if profile_response.status_code < 400:
            profile = profile_response.json()
            oauth_token.account_id = profile.get("sub")
            oauth_token.account_name = profile.get("name") or profile.get("email")
            db.add(oauth_token)
            await db.commit()
            await db.refresh(oauth_token)
        if not oauth_token.account_id:
            raise HTTPException(status_code=400, detail="LinkedIn account profile was not captured. Reconnect LinkedIn before publishing.")
    author = f"urn:li:person:{oauth_token.account_id}"
    body = {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": payload.text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json", "X-Restli-Protocol-Version": "2.0.0"},
            json=body,
        )
    audit = IntegrationAuditService(db)
    if response.status_code >= 400:
        await audit.record(user_id=current_user.id, business_id=business_id, provider="linkedin", action="linkedin_post", status="failed", message="LinkedIn rejected the publish request.", metadata={"status_code": response.status_code})
        raise _provider_error("LinkedIn", response, "LinkedIn rejected the publish request. Confirm w_member_social approval.")
    post_id = response.headers.get("x-restli-id")
    await audit.record(user_id=current_user.id, business_id=business_id, provider="linkedin", action="linkedin_post", status="success", message="LinkedIn post published.", metadata={"post_id": post_id})
    return {"status": "published", "provider": "linkedin", "post_id": post_id}


@router.post("/instagram/post")
async def instagram_post(payload: SocialPostPayload, business_id: UUID = Query(...), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    oauth_token, access_token = await _require_oauth_token(db, current_user, business_id, "instagram", "instagram_post")
    ig_user_id = payload.account_id or oauth_token.account_id
    if not ig_user_id:
        raise HTTPException(status_code=400, detail="Select or reconnect an Instagram Professional account before publishing.")
    if not payload.media_url:
        raise HTTPException(status_code=400, detail="Instagram Graph publishing requires a public image URL.")
    async with httpx.AsyncClient(timeout=30.0) as client:
        create_resp = await client.post(
            f"https://graph.facebook.com/v18.0/{ig_user_id}/media",
            data={"image_url": payload.media_url, "caption": payload.text, "access_token": access_token},
        )
        if create_resp.status_code >= 400:
            await IntegrationAuditService(db).record(user_id=current_user.id, business_id=business_id, provider="instagram", action="instagram_create_media", status="failed", message="Instagram media container creation failed.", metadata={"status_code": create_resp.status_code})
            raise _provider_error("Instagram", create_resp, "Instagram media container creation failed.")
        creation_id = create_resp.json().get("id")
        publish_resp = await client.post(
            f"https://graph.facebook.com/v18.0/{ig_user_id}/media_publish",
            data={"creation_id": creation_id, "access_token": access_token},
        )
    if publish_resp.status_code >= 400:
        await IntegrationAuditService(db).record(user_id=current_user.id, business_id=business_id, provider="instagram", action="instagram_post", status="failed", message="Instagram publish failed.", metadata={"status_code": publish_resp.status_code})
        raise _provider_error("Instagram", publish_resp, "Instagram publish failed.")
    media_id = publish_resp.json().get("id")
    await IntegrationAuditService(db).record(user_id=current_user.id, business_id=business_id, provider="instagram", action="instagram_post", status="success", message="Instagram media published.", metadata={"media_id": media_id})
    return {"status": "published", "provider": "instagram", "media_id": media_id}


@router.post("/slack/message")
async def slack_message(payload: SlackMessagePayload, business_id: UUID = Query(...), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    access_token = await _require_access_token(db, current_user, business_id, "slack", "slack_message")
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"channel": payload.channel, "text": payload.text},
        )
    data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    if response.status_code >= 400 or not data.get("ok"):
        await IntegrationAuditService(db).record(user_id=current_user.id, business_id=business_id, provider="slack", action="slack_message", status="failed", message="Slack message failed.", metadata={"error": data.get("error"), "status_code": response.status_code})
        raise HTTPException(status_code=400, detail=f"Slack message failed: {data.get('error') or response.status_code}")
    await IntegrationAuditService(db).record(user_id=current_user.id, business_id=business_id, provider="slack", action="slack_message", status="success", message="Slack message sent.", metadata={"channel": data.get("channel"), "ts": data.get("ts")})
    return {"status": "sent", "provider": "slack", "channel": data.get("channel"), "ts": data.get("ts")}


@router.post("/notion/page")
async def notion_page(payload: NotionPagePayload, business_id: UUID = Query(...), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    access_token = await _require_access_token(db, current_user, business_id, "notion", "notion_page")
    body = {
        "parent": {"page_id": payload.parent_page_id},
        "properties": {"title": {"title": [{"text": {"content": payload.title}}]}},
        "children": [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": payload.content[:1900]}}]}}],
    }
    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.post(
            "https://api.notion.com/v1/pages",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"},
            json=body,
        )
    if response.status_code >= 400:
        await IntegrationAuditService(db).record(user_id=current_user.id, business_id=business_id, provider="notion", action="notion_page", status="failed", message="Notion page creation failed.", metadata={"status_code": response.status_code})
        raise _provider_error("Notion", response, "Notion page creation failed.")
    data = response.json()
    await IntegrationAuditService(db).record(user_id=current_user.id, business_id=business_id, provider="notion", action="notion_page", status="success", message="Notion page created.", metadata={"page_id": data.get("id"), "url": data.get("url")})
    return {"status": "created", "provider": "notion", "page_id": data.get("id"), "url": data.get("url")}


@router.post("/wordpress/post")
async def wordpress_post(payload: WordPressPostPayload, business_id: UUID = Query(...), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    oauth_token, access_token = await _require_oauth_token(db, current_user, business_id, "wordpress", "wordpress_post")
    site_id = payload.site_id or oauth_token.account_id
    if not site_id:
        raise HTTPException(status_code=400, detail="Select a WordPress site before publishing a post.")
    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.post(
            f"https://public-api.wordpress.com/rest/v1.1/sites/{site_id}/posts/new",
            headers={"Authorization": f"Bearer {access_token}"},
            data={"title": payload.title, "content": payload.content, "status": payload.status},
        )
    if response.status_code >= 400:
        await IntegrationAuditService(db).record(user_id=current_user.id, business_id=business_id, provider="wordpress", action="wordpress_post", status="failed", message="WordPress post creation failed.", metadata={"status_code": response.status_code})
        raise _provider_error("WordPress", response, "WordPress post creation failed.")
    data = response.json()
    await IntegrationAuditService(db).record(user_id=current_user.id, business_id=business_id, provider="wordpress", action="wordpress_post", status="success", message="WordPress post created.", metadata={"post_id": data.get("ID"), "url": data.get("URL")})
    return {"status": data.get("status") or payload.status, "provider": "wordpress", "post_id": data.get("ID"), "url": data.get("URL")}


@router.post("/twitter/post")
async def twitter_post(payload: SocialPostPayload, business_id: UUID = Query(...), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    access_token = await _require_access_token(db, current_user, business_id, "twitter", "twitter_post")
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            "https://api.twitter.com/2/tweets",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"text": payload.text},
        )
    if response.status_code >= 400:
        await IntegrationAuditService(db).record(user_id=current_user.id, business_id=business_id, provider="twitter", action="twitter_post", status="failed", message="Twitter/X post failed.", metadata={"status_code": response.status_code})
        raise _provider_error("Twitter/X", response, "Twitter/X post failed.")
    data = response.json().get("data", {})
    await IntegrationAuditService(db).record(user_id=current_user.id, business_id=business_id, provider="twitter", action="twitter_post", status="success", message="Twitter/X post published.", metadata={"tweet_id": data.get("id")})
    return {"status": "published", "provider": "twitter", "tweet_id": data.get("id")}


@router.post("/facebook/post")
async def facebook_post(payload: SocialPostPayload, business_id: UUID = Query(...), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    access_token = await _require_access_token(db, current_user, business_id, "facebook", "facebook_post")
    if not payload.page_id:
        raise HTTPException(status_code=400, detail="Facebook publishing requires a selected Page ID.")
    data = {"message": payload.text, "access_token": access_token}
    if payload.media_url:
        data["link"] = payload.media_url
    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.post(f"https://graph.facebook.com/v18.0/{payload.page_id}/feed", data=data)
    if response.status_code >= 400:
        await IntegrationAuditService(db).record(user_id=current_user.id, business_id=business_id, provider="facebook", action="facebook_post", status="failed", message="Facebook Page post failed.", metadata={"status_code": response.status_code})
        raise _provider_error("Facebook", response, "Facebook Page post failed.")
    post_id = response.json().get("id")
    await IntegrationAuditService(db).record(user_id=current_user.id, business_id=business_id, provider="facebook", action="facebook_post", status="success", message="Facebook Page post published.", metadata={"post_id": post_id})
    return {"status": "published", "provider": "facebook", "post_id": post_id}


def _ads_draft_payload(provider: str, payload: AdsDraftPayload) -> dict:
    return {
        "provider": provider,
        "campaign_name": payload.campaign_name,
        "objective": payload.objective or "traffic",
        "headline": payload.headline,
        "body": payload.body,
        "cta": payload.cta,
        "destination_url": payload.destination_url,
        "daily_budget_cents": payload.daily_budget_cents,
        "target_audience": payload.target_audience,
        "creative_url": payload.creative_url,
        "approval_required": True,
        "launch_blocked_until_user_confirms_budget": True,
    }


@router.post("/google-ads/draft")
async def google_ads_draft(payload: AdsDraftPayload, business_id: UUID = Query(...), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    await _require_access_token(db, current_user, business_id, "google_ads", "google_ads_draft")
    draft = _ads_draft_payload("google_ads", payload)
    await IntegrationAuditService(db).record(
        user_id=current_user.id,
        business_id=business_id,
        provider="google_ads",
        action="google_ads_draft",
        status="success",
        message="Google Ads draft payload prepared. No spend was launched.",
        metadata={"campaign_name": payload.campaign_name, "approval_required": True},
    )
    return {"status": "draft_ready", "provider": "google_ads", "draft": draft, "message": "Google Ads draft prepared. Review and approve budget before launch."}


@router.post("/meta-ads/draft")
async def meta_ads_draft(payload: AdsDraftPayload, business_id: UUID = Query(...), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    await _require_access_token(db, current_user, business_id, "meta_ads", "meta_ads_draft")
    draft = _ads_draft_payload("meta_ads", payload)
    await IntegrationAuditService(db).record(
        user_id=current_user.id,
        business_id=business_id,
        provider="meta_ads",
        action="meta_ads_draft",
        status="success",
        message="Meta Ads draft payload prepared. No spend was launched.",
        metadata={"campaign_name": payload.campaign_name, "approval_required": True},
    )
    return {"status": "draft_ready", "provider": "meta_ads", "draft": draft, "message": "Meta Ads draft prepared. Review and approve budget before launch."}
