"""Email notification service."""
from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Async email sender that skips delivery when SMTP is not configured."""

    async def send(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> bool:
        if not settings.smtp_username or not settings.smtp_password:
            logger.info("Email skipped (SMTP not configured): to=%s subject=%s", to, subject)
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.email_from_name} <{settings.email_from}>"
        msg["To"] = to

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            import aiosmtplib

            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username,
                password=settings.smtp_password,
                start_tls=True,
            )
            logger.info("Email sent to=%s subject=%s", to, subject)
            return True
        except Exception as exc:
            logger.error("Email send failed to=%s error=%s", to, exc)
            return False

    async def send_welcome(self, to: str, full_name: str | None = None) -> bool:
        name = full_name or "there"
        return await self.send(
            to=to,
            subject="Welcome to Autonomous Business Builder",
            html_body=f"""
            <h2>Welcome, {name}!</h2>
            <p>Your account is ready. Head to the dashboard to generate your first AI-powered business.</p>
            <p><a href="{settings.frontend_url}/generator">Generate a business</a></p>
            """,
            text_body=f"Welcome, {name}! Visit {settings.frontend_url}/generator to get started.",
        )

    async def send_order_confirmation(
        self,
        to: str,
        business_name: str,
        product_name: str,
        amount_cents: int,
        currency: str = "usd",
    ) -> bool:
        amount = f"{currency.upper()} {amount_cents / 100:.2f}"
        return await self.send(
            to=to,
            subject=f"Order confirmed - {product_name}",
            html_body=f"""
            <h2>Order confirmed</h2>
            <p>Thank you for purchasing <strong>{product_name}</strong> from <strong>{business_name}</strong>.</p>
            <p>Amount charged: <strong>{amount}</strong></p>
            """,
            text_body=f"Order confirmed: {product_name} from {business_name}. Amount: {amount}.",
        )

    async def send_business_created(self, to: str, business_name: str, business_id: str) -> bool:
        return await self.send(
            to=to,
            subject=f"Your business '{business_name}' is live",
            html_body=f"""
            <h2>Your business is ready!</h2>
            <p><strong>{business_name}</strong> has been generated and is ready to launch.</p>
            <p><a href="{settings.frontend_url}/landing/{business_id}">View landing page</a></p>
            """,
            text_body=f"Your business '{business_name}' is ready. View it at {settings.frontend_url}/landing/{business_id}",
        )

    async def send_marketing_campaign(self, user_id: str, to: str, subject: str, html_body: str, db) -> bool:
        """Send a marketing email using the user's configured SendGrid API key."""
        from sqlalchemy import select
        from app.models.user_ai_settings import UserAISettings
        import httpx

        res = await db.execute(select(UserAISettings).where(UserAISettings.user_id == user_id, UserAISettings.provider == "sendgrid"))
        setting = res.scalar_one_or_none()
        
        if not setting or not setting.api_key_encrypted:
            logger.error("User %s has no SendGrid API key configured.", user_id)
            return False

        # Decrypt key
        from app.api.routes.auth import _get_fernet
        try:
            f = _get_fernet()
            api_key = f.decrypt(setting.api_key_encrypted.encode()).decode()
        except Exception as e:
            logger.error("Failed to decrypt SendGrid key for user %s: %s", user_id, e)
            return False

        # Send via SendGrid v3 API
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "personalizations": [{"to": [{"email": to}]}],
                        "from": {"email": settings.email_from, "name": settings.email_from_name},
                        "subject": subject,
                        "content": [{"type": "text/html", "value": html_body}]
                    }
                )
                if resp.status_code in (200, 202):
                    logger.info("Marketing email sent via SendGrid to %s", to)
                    return True
                else:
                    logger.error("SendGrid API Error: %s", resp.text)
                    return False
        except Exception as e:
            logger.error("SendGrid HTTP Error: %s", e)
            return False
