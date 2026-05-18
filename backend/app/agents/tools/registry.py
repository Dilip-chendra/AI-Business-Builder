"""Tool registry — central catalogue of all available agent tools.

Every tool is a callable that:
- Accepts a params dict
- Returns a structured ToolResult
- Handles its own errors gracefully

Tools are registered by name and looked up by the ToolExecutor.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Structured result returned by every tool."""
    success: bool
    data: Any = None
    error: str | None = None
    tool_name: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "tool_name": self.tool_name,
            "metadata": self.metadata,
        }


@dataclass
class ToolDefinition:
    """Metadata about a registered tool."""
    name: str
    description: str
    category: str  # "internal" | "browser" | "external"
    params_schema: dict  # JSON Schema for params validation
    handler: Callable[..., Awaitable[ToolResult]]
    requires_confirmation: bool = False


class ToolRegistry:
    """Singleton registry of all available tools."""

    _instance: "ToolRegistry | None" = None
    _tools: dict[str, ToolDefinition] = {}
    _registered_categories: set[str] = set()

    @classmethod
    def get(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, tool: ToolDefinition) -> None:
        if tool.name not in self._tools:
            self._tools[tool.name] = tool
            logger.debug("Tool registered: %s (%s)", tool.name, tool.category)

    def register_category(self, category: str) -> bool:
        """Mark a category as registered. Returns False if already done."""
        if category in self._registered_categories:
            return False
        self._registered_categories.add(category)
        return True

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self, category: str | None = None) -> list[ToolDefinition]:
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def tool_names(self, category: str | None = None) -> list[str]:
        return [t.name for t in self.list_tools(category)]

    def describe_for_prompt(self, category: str | None = None) -> str:
        """Return a compact tool list suitable for inclusion in an AI prompt."""
        lines = []
        for t in self.list_tools(category):
            lines.append(f"- {t.name}: {t.description}")
        return "\n".join(lines)
