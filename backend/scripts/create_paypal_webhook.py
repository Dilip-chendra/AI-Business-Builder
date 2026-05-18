from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings


EVENT_TYPES = [
    {"name": "BILLING.SUBSCRIPTION.ACTIVATED"},
    {"name": "BILLING.SUBSCRIPTION.CANCELLED"},
    {"name": "BILLING.SUBSCRIPTION.SUSPENDED"},
    {"name": "BILLING.SUBSCRIPTION.EXPIRED"},
    {"name": "BILLING.SUBSCRIPTION.PAYMENT.FAILED"},
    {"name": "PAYMENT.SALE.COMPLETED"},
    {"name": "PAYMENT.CAPTURE.COMPLETED"},
    {"name": "CHECKOUT.ORDER.APPROVED"},
]


def _is_public_https_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    return parsed.hostname not in {"localhost", "127.0.0.1", "::1"}


async def _get_access_token() -> tuple[str, str]:
    if not settings.paypal_client_id or not settings.paypal_client_secret:
        raise SystemExit("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be configured in backend/.env")
    base_url = "https://api-m.paypal.com" if settings.paypal_env.lower() == "live" else "https://api-m.sandbox.paypal.com"
    async with httpx.AsyncClient(timeout=30.0, auth=(settings.paypal_client_id, settings.paypal_client_secret)) as client:
        response = await client.post(
            f"{base_url}/v1/oauth2/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials"},
        )
        response.raise_for_status()
    return response.json()["access_token"], base_url


async def main() -> None:
    webhook_target = f"{settings.api_base_url.rstrip('/')}/api/v1/billing/paypal/webhook"
    if not _is_public_https_url(webhook_target):
        raise SystemExit(
            "API_BASE_URL must be a public HTTPS URL before PayPal can deliver webhooks. "
            f"Current value: {settings.api_base_url}"
        )

    access_token, base_url = await _get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        existing_response = await client.get(f"{base_url}/v1/notifications/webhooks")
        existing_response.raise_for_status()
        for webhook in existing_response.json().get("webhooks", []):
            if webhook.get("url") == webhook_target:
                print(webhook["id"])
                return

        create_response = await client.post(
            f"{base_url}/v1/notifications/webhooks",
            json={"url": webhook_target, "event_types": EVENT_TYPES},
        )
        create_response.raise_for_status()
        print(create_response.json()["id"])


if __name__ == "__main__":
    asyncio.run(main())
