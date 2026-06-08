from __future__ import annotations

import re

MOJIBAKE_REPLACEMENTS = {
    "\u2026": "...",
    "\u2022": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2192": "->",
    "\u2713": "OK",
    "\u2714": "OK",
    "\u2717": "x",
    "\u2718": "x",
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u00e2\u20ac\u00a6": "...",
    "\u00e2\u20ac\u00a2": "-",
    "\u00e2\u20ac\u201c": "-",
    "\u00e2\u20ac\u201d": "-",
    "\u00e2\u20a0\u2122": "->",
    "\u00c3\u00a2\u00e2\u201a\u00ac\u00c2\u00a6": "...",
    "\u00c3\u00a2\u00e2\u201a\u00ac\u00e2\u20ac\u201d": "-",
    "\u00c3\u00a2\u00e2\u201a\u00ac\u00e2\u20ac\u0153": "-",
    "\u00c3\u00a2\u00e2\u201a\u00ac\u00c2\u00a2": "-",
    "\u00c3\u00a2\u00e2\u20ac\u00a0\u00c3\u00a2\u00e2\u20ac\u2122": "->",
    "\u00c3\u00a2\u00c3\u2026\u0153\u00c3\u00a2\u00e2\u20ac\u0153": "OK",
    "\u00c3\u00a2\u00c3\u2026\u0153\u00c3\u00a2\u00e2\u20ac\ufffd": "OK",
    "\u00c3\u00a2\u00c3\u2026\u0153\u00c3\u00a2\u00e2\u20ac\u201d": "x",
    "\u00c3\u00a2\u00e2\u20ac\u0161\u00c3\u201a\u00c2\u00b7": "-",
    "\u00c3\u00a2\u00e2\u20ac\u0161\u00c3\u201a": "",
    "\u00c3\u2020\u2019\u00c3\u201a\u00a9": "e",
    "\u00c3\u2020\u2019\u00c3\u201a\u00a8": "e",
    "\u00c3\u2020\u2019": "",
    "\u00c3\u201a": "",
}


def _looks_mojibake(text: str) -> bool:
    suspicious_tokens = ("\u00c3", "\u00e2", "\u00c2", "\u0393", "\ufffd")
    return any(token in text for token in suspicious_tokens)


def _repair_mojibake(text: str) -> str:
    if not text or not _looks_mojibake(text):
        return text
    try:
        repaired = text.encode("cp1252", errors="ignore").decode("utf-8", errors="ignore")
        if repaired and repaired != text:
            return repaired
    except Exception:
        pass
    return text


def clean_text(value: str | None) -> str:
    """Normalize common mojibake and whitespace for UI-facing text."""
    text = _repair_mojibake(value or "")
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    text = _repair_mojibake(text)
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def looks_like_structured_blob(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    if stripped.startswith("{") or stripped.startswith("["):
        return True
    if stripped.count("{") >= 2 or stripped.count('":') >= 2:
        return True
    if "|" in stripped and "---" in stripped:
        return True
    return False
