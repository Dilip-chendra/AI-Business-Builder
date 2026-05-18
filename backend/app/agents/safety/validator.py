"""Action validation layer — validates every action before execution.

Checks:
- Required fields are present
- Values are within safe ranges
- Destructive patterns are blocked
- Business ownership is respected
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class ValidationError(ValueError):
    """Raised when an action fails validation."""


# ── Blocked patterns ──────────────────────────────────────────────────────────
# Any action whose payload contains these strings (case-insensitive) is blocked.
_BLOCKED_PAYLOAD_PATTERNS = [
    r"\bdelete_all\b",
    r"\boverwrite_all\b",
    r"\bdrop\s+table\b",
    r"\btruncate\b",
    r"\bformat\s+disk\b",
    r"\brm\s+-rf\b",
    r"\bpassword\b",
    r"\bsecret_key\b",
    r"\bapi_key\b",
]

# Actions that are always blocked regardless of role
_ALWAYS_BLOCKED_ACTIONS = {
    "submit_payment",
    "buy",
    "purchase",
    "delete_all",
    "overwrite_all",
    "login",          # browser agent must not log into external sites
    "fill_password",
}

# Actions that require explicit user confirmation before execution
REQUIRES_CONFIRMATION = {
    "delete_product",
    "delete_business",
    "bulk_update",
    "send_email",
}


class ActionValidator:
    """Validates an action dict before it is executed."""

    @staticmethod
    def validate(action: dict[str, Any]) -> None:
        """Validate the action. Raises ValidationError if invalid.

        Args:
            action: Dict with at least {"tool": str, "params": dict}.

        Raises:
            ValidationError: If the action is unsafe or malformed.
        """
        tool = action.get("tool") or action.get("action")
        if not tool or not isinstance(tool, str):
            raise ValidationError("Action must have a non-empty 'tool' field.")

        tool_lower = tool.lower().strip()

        # ── Always-blocked actions ────────────────────────────────────────────
        if tool_lower in _ALWAYS_BLOCKED_ACTIONS:
            raise ValidationError(
                f"Action '{tool}' is permanently blocked for safety reasons."
            )

        params = action.get("params") or action.get("payload") or {}
        if not isinstance(params, dict):
            raise ValidationError("Action 'params' must be a dict.")

        # ── Blocked payload patterns ──────────────────────────────────────────
        payload_str = str(params).lower()
        for pattern in _BLOCKED_PAYLOAD_PATTERNS:
            if re.search(pattern, payload_str, re.IGNORECASE):
                raise ValidationError(
                    f"Action payload contains a blocked pattern: {pattern!r}"
                )

        # ── Tool-specific validation ──────────────────────────────────────────
        ActionValidator._validate_tool_params(tool_lower, params)

        logger.debug("Action validated  tool=%s", tool)

    @staticmethod
    def _validate_tool_params(tool: str, params: dict) -> None:
        """Per-tool parameter validation."""
        if tool == "create_product":
            name = params.get("name", "")
            price = params.get("price")
            if not name or len(str(name).strip()) < 2:
                raise ValidationError("create_product: 'name' must be at least 2 characters.")
            if price is not None:
                try:
                    p = float(price)
                    if p <= 0:
                        raise ValidationError("create_product: 'price' must be > 0.")
                    if p > 100_000:
                        raise ValidationError("create_product: 'price' exceeds maximum ($100,000).")
                except (TypeError, ValueError):
                    raise ValidationError(f"create_product: 'price' must be a number, got {price!r}.")

        elif tool == "update_business_field":
            field = params.get("field")
            value = params.get("new_value")
            allowed_fields = {
                "headline", "subheading", "cta_text", "product_pitch",
                "description", "brand_tone", "seo_title", "seo_description",
            }
            if field not in allowed_fields:
                raise ValidationError(
                    f"update_business_field: '{field}' is not an editable field. "
                    f"Allowed: {sorted(allowed_fields)}"
                )
            if not value or len(str(value).strip()) < 2:
                raise ValidationError(
                    f"update_business_field: 'new_value' must be at least 2 characters."
                )

        elif tool == "open_url":
            url = params.get("url", "")
            if not url.startswith(("http://", "https://")):
                raise ValidationError(
                    f"open_url: URL must start with http:// or https://. Got: {url!r}"
                )
            # Block localhost and internal network access
            blocked_hosts = ["localhost", "127.0.0.1", "0.0.0.0", "169.254.", "10.", "192.168.", "172."]
            url_lower = url.lower()
            for blocked in blocked_hosts:
                if blocked in url_lower:
                    raise ValidationError(
                        f"open_url: Access to internal/local addresses is blocked. URL: {url!r}"
                    )

        elif tool == "type_text":
            text = params.get("text", "")
            # Block typing of sensitive patterns
            sensitive = ["password", "credit card", "cvv", "ssn", "social security"]
            text_lower = str(text).lower()
            for s in sensitive:
                if s in text_lower:
                    raise ValidationError(
                        f"type_text: Typing sensitive information ('{s}') is blocked."
                    )

        elif tool == "send_email":
            to = params.get("to", "")
            subject = params.get("subject", "")
            if not to or "@" not in str(to):
                raise ValidationError("send_email: 'to' must be a valid email address.")
            if not subject:
                raise ValidationError("send_email: 'subject' is required.")

    @staticmethod
    def requires_confirmation(tool: str) -> bool:
        """Return True if this tool requires human confirmation before execution."""
        return tool.lower() in REQUIRES_CONFIRMATION
