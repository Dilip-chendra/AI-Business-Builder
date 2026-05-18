import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class ActionParser:
    """Safely extracts, normalizes, and validates browser action JSON."""

    ALLOWED_ACTIONS = {
        "goto",
        "search",
        "click",
        "type",
        "press",
        "hover",
        "scroll",
        "wait",
        "extract",
        "select_option",
        "upload_file",
        "download",
        "open_tab",
        "switch_tab",
        "close_tab",
        "back",
        "done",
        "error",
    }

    ACTION_ALIASES = {
        "open_url": "goto",
        "navigate": "goto",
        "visit": "goto",
        "search_google": "search",
        "google_search": "search",
        "bing_search": "search",
        "extract_text": "extract",
        "finish": "done",
        "complete": "done",
    }

    @classmethod
    def parse_action(cls, raw_output: str) -> dict[str, Any]:
        """Parse a single action object from a raw LLM response."""
        json_text = cls._extract_json_object(raw_output)
        if not json_text:
            logger.error("No JSON object found in output: %s", raw_output[:200])
            return {"action": "error", "error": "No JSON block found in response"}

        try:
            action = json.loads(json_text)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse JSON: %s. Raw text: %s", exc, json_text)
            return {"action": "error", "error": f"JSON decode error: {exc}"}

        if not isinstance(action, dict):
            return {"action": "error", "error": "Parsed JSON is not an object"}
        if "action" not in action:
            return {"action": "error", "error": "Parsed JSON missing 'action' key"}

        normalized = cls._normalize(action)
        return cls._validate(normalized)

    @staticmethod
    def _extract_json_object(raw_output: str) -> str | None:
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_output, re.DOTALL)
        if fenced:
            return fenced.group(1)

        start = raw_output.find("{")
        end = raw_output.rfind("}")
        if start != -1 and end != -1 and start < end:
            return raw_output[start : end + 1]
        return None

    @classmethod
    def _normalize(cls, action: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(action)
        raw_name = str(normalized.get("action", "")).strip().lower()
        normalized["action"] = cls.ACTION_ALIASES.get(raw_name, raw_name)

        if normalized["action"] == "click" and "target" not in normalized and "text" in normalized:
            normalized["target"] = normalized["text"]
        if normalized["action"] == "type" and "target" not in normalized and "field" in normalized:
            normalized["target"] = normalized["field"]
        if normalized["action"] == "search":
            normalized.setdefault("query", normalized.get("text", ""))
            normalized.setdefault("search_engine", normalized.get("engine", "duckduckgo"))
        if normalized["action"] == "scroll":
            normalized.setdefault("direction", "down")
            normalized.setdefault("amount", 700)
        if normalized["action"] == "wait":
            normalized.setdefault("seconds", 2)
        if normalized["action"] == "extract":
            normalized.setdefault("instruction", "Extract the information needed for the user goal.")

        return normalized

    @classmethod
    def _validate(cls, action: dict[str, Any]) -> dict[str, Any]:
        act = str(action.get("action", "")).strip().lower()
        if act not in cls.ALLOWED_ACTIONS:
            return {"action": "error", "error": f"Unsupported action '{act}'"}

        if act == "goto" and not action.get("url"):
            return {"action": "error", "error": "goto action requires a url"}
        if act == "search" and not action.get("query"):
            return {"action": "error", "error": "search action requires a query"}
        if act in {"click", "hover"} and action.get("element_id") is None and not action.get("target"):
            return {"action": "error", "error": f"{act} action requires element_id or target"}
        if act == "type":
            if action.get("element_id") is None and not action.get("target"):
                return {"action": "error", "error": "type action requires element_id or target"}
            if "text" not in action:
                return {"action": "error", "error": "type action requires text"}
        if act == "switch_tab" and "tab_index" not in action:
            return {"action": "error", "error": "switch_tab action requires tab_index"}

        return action
