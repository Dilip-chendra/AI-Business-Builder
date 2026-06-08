"""Secure credential vault for browser automation publishing."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.business_service import BusinessService
from app.services.integration_account_service import IntegrationAccountService

router = APIRouter()

SUPPORTED_CREDENTIAL_PROVIDERS = {
    "linkedin",
    "instagram",
    "facebook",
    "gmail",
    "wordpress",
    "twitter",
    "x",
    "browser_automation",
}


class CredentialPayload(BaseModel):
    login_email: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=40)
    password: str | None = Field(default=None, min_length=1, max_length=2000)
    business_id: UUID | None = None


def _normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower().replace("twitter/x", "twitter")
    if normalized == "x":
        normalized = "twitter"
    if normalized not in SUPPORTED_CREDENTIAL_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported credential provider: {provider}")
    return normalized


async def _verify_business(db: AsyncSession, business_id: UUID | None, user: User):
    if business_id is None:
        return None
    business = await BusinessService(db).get(business_id, user_id=user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


@router.get("")
async def list_credentials(
    business_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List configured vault entries without exposing secrets."""
    await _verify_business(db, business_id, current_user)
    svc = IntegrationAccountService(db)
    accounts = await svc.list_for_business(user_id=current_user.id, business_id=business_id)
    by_provider = {}
    for account in accounts:
        summary = svc.summary(account)
        summary["provider"] = account.platform
        summary["mode"] = "browser_automation"
        by_provider[account.platform] = summary
    providers = ["linkedin", "instagram", "facebook", "twitter", "gmail", "wordpress", "browser_automation"]
    return [
        by_provider.get(
            provider,
            {
                "id": None,
                "provider": provider,
                "platform": provider,
                "status": "not_configured",
                "identifier_preview": "",
                "last_active_at": None,
                "last_tested_at": None,
                "last_error": None,
                "mode": "browser_automation",
            },
        )
        for provider in providers
    ]


@router.post("/{provider}")
async def save_credential(
    provider: str,
    payload: CredentialPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Save encrypted browser automation credentials.

    The response only includes masked metadata. Passwords are never returned.
    """
    normalized = _normalize_provider(provider)
    business = await _verify_business(db, payload.business_id, current_user)
    login_identifier = (payload.login_email or payload.username or "").strip() or None
    if not login_identifier and not payload.phone:
        raise HTTPException(status_code=400, detail="Provide an email, username, or phone number.")
    if not payload.password:
        raise HTTPException(status_code=400, detail="Password is required for browser automation credentials.")

    svc = IntegrationAccountService(db)
    account = await svc.save(
        user_id=current_user.id,
        workspace_id=getattr(business, "workspace_id", None),
        business_id=getattr(business, "id", None),
        platform=normalized,
        login_identifier=login_identifier,
        password=payload.password,
        phone=(payload.phone or "").strip() or None,
        metadata={"provider": normalized, "mode": "browser_automation", "vault": "credential_vault"},
    )
    result = svc.summary(account)
    result["provider"] = normalized
    result["mode"] = "browser_automation"
    return result


@router.delete("/{provider}")
async def delete_credential(
    provider: str,
    business_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    normalized = _normalize_provider(provider)
    await _verify_business(db, business_id, current_user)
    svc = IntegrationAccountService(db)
    account = await svc.get(user_id=current_user.id, business_id=business_id, platform=normalized)
    if not account:
        return {"status": "not_found", "provider": normalized}
    await svc.delete(account)
    return {"status": "deleted", "provider": normalized}


@router.post("/{provider}/test-login")
async def test_credential_login(
    provider: str,
    business_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Validate that required encrypted fields exist without exposing them.

    This intentionally does not perform a real third-party login. Browser login
    automation is launched only from an explicit publishing workflow.
    """
    normalized = _normalize_provider(provider)
    await _verify_business(db, business_id, current_user)
    svc = IntegrationAccountService(db)
    account = await svc.get(user_id=current_user.id, business_id=business_id, platform=normalized)
    if not account:
        raise HTTPException(status_code=404, detail="No saved credentials for this provider.")
    revealed = svc.reveal(account)
    ok = bool(revealed.get("password") and (revealed.get("email") or revealed.get("phone")))
    updated = await svc.mark_test_result(
        account,
        ok=ok,
        error=None if ok else "Missing login identifier or password.",
    )
    result = svc.summary(updated)
    result["provider"] = normalized
    result["mode"] = "browser_automation"
    return result
