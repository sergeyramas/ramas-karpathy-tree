"""Deterministic pre-filter: decide if a transcript is worth flushing to LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class FilterReason(str, Enum):
    OK = "ok"
    EMPTY = "empty"
    TOO_SHORT = "too_short"
    TRIVIAL_OPS = "trivial_ops"


@dataclass
class FilterDecision:
    proceed: bool
    reason: FilterReason


# Input format: lines like "**User:** ls -la" or "**Assistant:** [Bash output]" produced
# by session-end.py:extract_conversation_context. Patterns match against this format.
TRIVIAL_ASSISTANT_PATTERNS = [
    re.compile(r"^\s*\*\*Assistant:\*\*\s*\[ran tool\]\s*$", re.IGNORECASE),
    re.compile(r"^\s*\*\*Assistant:\*\*\s*\[Bash output\]\s*$", re.IGNORECASE),
    re.compile(r"^\s*\*\*Assistant:\*\*\s*\(no output\)\s*$", re.IGNORECASE),
]

TRIVIAL_USER_PATTERNS = [
    re.compile(
        r"^\s*\*\*User:\*\*\s*(ls|pwd|cd\b|cat\b|head\b|tail\b|grep\b|echo\b)",
        re.IGNORECASE,
    ),
]


def should_flush(transcript_text: str, char_threshold: int = 1000) -> FilterDecision:
    """Return whether the transcript is worth a flush API call.

    Why these checks: every flush costs money + writes a daily log entry. If the session
    is empty, too short, or only consists of trivial bash commands, the LLM has nothing
    useful to extract, and we'd be polluting the daily log with noise.
    """
    if not transcript_text or not transcript_text.strip():
        return FilterDecision(False, FilterReason.EMPTY)

    if len(transcript_text) < char_threshold:
        return FilterDecision(False, FilterReason.TOO_SHORT)

    # Detect "only trivial ops": every non-empty content matches a trivial pattern.
    content_lines = [
        line.strip() for line in transcript_text.splitlines() if line.strip()
    ]
    if content_lines:
        non_trivial = 0
        for line in content_lines:
            if any(p.search(line) for p in TRIVIAL_ASSISTANT_PATTERNS):
                continue
            if any(p.search(line) for p in TRIVIAL_USER_PATTERNS):
                continue
            non_trivial += 1
        if non_trivial == 0:
            return FilterDecision(False, FilterReason.TRIVIAL_OPS)

    return FilterDecision(True, FilterReason.OK)
