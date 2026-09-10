"""Prompt content validation to prevent injection attacks."""

import re

BLOCKLIST_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"ignore previous instructions",
        r"you are now",
        r"disregard all",
        r"forget your instructions",
        r"new system prompt",
        r"<script",
        r"javascript:",
        r"data:text/html",
        r"ignore all previous",
        r"override your",
    ]
]

URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)


def validate_prompt(text: str, max_length: int = 10000) -> tuple:
    """Validate prompt text. Returns (is_valid, reason)."""
    if len(text) > max_length:
        return (False, f"exceeds max length of {max_length} characters")

    for pattern in BLOCKLIST_PATTERNS:
        if pattern.search(text):
            return (False, f"contains blocked pattern: {pattern.pattern}")

    if URL_PATTERN.search(text):
        return (False, "contains URL")

    return (True, "valid")
