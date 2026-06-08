"""Role-Based Access Control for agent actions.

Every tool call must pass through PermissionService.check() before execution.
Roles: admin > user > agent (most restricted)
"""
from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"
    AGENT = "agent"


class ForbiddenError(PermissionError):
    """Raised when an action is not permitted for the given role."""


# ── Permission matrix ─────────────────────────────────────────────────────────
# Maps tool_name → minimum role required to execute it.
# Tools not listed here are DENIED by default.
_PERMISSION_MATRIX: dict[str, Role] = {
    # Read-only — all roles
    "get_analytics": Role.AGENT,
    "get_business": Role.AGENT,
    "list_products": Role.AGENT,
    "get_page_content": Role.AGENT,
    "extract_text": Role.AGENT,
    "open_url": Role.AGENT,
    "scroll": Role.AGENT,
    "take_screenshot": Role.AGENT,
    "search_google": Role.AGENT,
    # Write — user and above
    "create_product": Role.USER,
    "update_product": Role.USER,
    "update_business_field": Role.USER,
    "run_agent_pipeline": Role.USER,
    "send_email": Role.USER,
    "click": Role.USER,
    "type_text": Role.USER,
    # Destructive — admin only
    "delete_product": Role.ADMIN,
    "delete_business": Role.ADMIN,
    "bulk_update": Role.ADMIN,
    "submit_payment": Role.ADMIN,
}

# Role hierarchy: higher index = more permissions
_ROLE_LEVEL = {Role.AGENT: 0, Role.USER: 1, Role.ADMIN: 2}


class PermissionService:
    """Checks whether a role is allowed to execute a given tool."""

    @staticmethod
    def check(role: Role | str, tool_name: str) -> None:
        """Raise ForbiddenError if the role cannot execute tool_name.

        Args:
            role:      The caller's role (Role enum or string).
            tool_name: The name of the tool being invoked.

        Raises:
            ForbiddenError: If the action is not permitted.
        """
        if isinstance(role, str):
            try:
                role = Role(role)
            except ValueError:
                raise ForbiddenError(f"Unknown role: {role!r}")

        required = _PERMISSION_MATRIX.get(tool_name)
        if required is None:
            raise ForbiddenError(
                f"Tool '{tool_name}' is not registered in the permission matrix. "
                "Add it explicitly to grant access."
            )

        caller_level = _ROLE_LEVEL.get(role, -1)
        required_level = _ROLE_LEVEL.get(required, 99)

        if caller_level < required_level:
            raise ForbiddenError(
                f"Role '{role.value}' cannot execute '{tool_name}'. "
                f"Requires '{required.value}' or higher."
            )

        logger.debug("Permission granted  role=%s  tool=%s", role.value, tool_name)

    @staticmethod
    def is_allowed(role: Role | str, tool_name: str) -> bool:
        """Return True if allowed, False otherwise. Never raises."""
        try:
            PermissionService.check(role, tool_name)
            return True
        except (ForbiddenError, PermissionError):
            return False
