"""privacy.py — redact personal data from transaction text.

Israeli bank/card exports often embed the account owner's name and national ID
inside the free-text "purpose" (עבור) field, e.g.:

    מופ"ת חובה פרנקלך מיכאל מזהה 347436107

We strip two things before the data ever reaches a report:

  1. National-ID identifiers — the literal "מזהה" followed by digits. This is
     generic and impersonal, so the pattern is hard-coded here.
  2. The account owner's own name(s). These are real personal data, so they are
     NOT hard-coded — they are read from the REDACT_NAMES env var (comma-
     separated tokens). Empty by default → no name redaction.

Counterparty names (other people in transfers) are left untouched.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache

# "מזהה 347436107" / "מזהה350924363" → removed (with any leading whitespace).
_ID_PATTERN = re.compile(r"\s*מזהה\s*\d+")

# Collapse the whitespace left behind after deletions.
_WS = re.compile(r"\s{2,}")


@lru_cache(maxsize=1)
def _name_tokens() -> tuple[str, ...]:
    """Owner name tokens to redact, from REDACT_NAMES (comma-separated)."""
    raw = os.getenv("REDACT_NAMES", "")
    return tuple(tok.strip() for tok in raw.split(",") if tok.strip())


def reset_cache() -> None:
    """Clear the cached REDACT_NAMES (useful in tests that set the env var)."""
    _name_tokens.cache_clear()


def redact_pii(text: str) -> str:
    """Strip national-ID identifiers and owner names from ``text``."""
    if not text:
        return text

    text = _ID_PATTERN.sub("", text)

    for token in _name_tokens():
        # Whole-token match only: bounded by whitespace or string edges, so a
        # token never chops a substring out of an unrelated word.
        text = re.sub(rf"(?<!\S){re.escape(token)}(?!\S)", "", text)

    return _WS.sub(" ", text).strip()
