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

# Order references ("הזמנה 30756966") and account numbers ("מח-ן:085070060").
# The label is impersonal but the number identifies a transaction/account, so
# both the word and the digits go.
_ORDER_PATTERN = re.compile(r"\s*הזמנה\s*\d+")
_ACCOUNT_PATTERN = re.compile(r"\s*מח[-\s]?ן[:\s]*\d+")

# Any leftover long reference token — a run of 5+ digits, optionally prefixed by
# 1-2 letters (e.g. "U24190453", "30756966"). Short numbers (card last-4, "013",
# dates) are kept. These are opaque references, never useful in a report.
_REF_PATTERN = re.compile(r"(?<![\w])[A-Za-z]{0,2}\d{5,}(?![\w])")

# Bit peer-to-peer transfers: the free text may carry a counterparty note, and
# the user just wants them shown as "BIT". Collapse the whole label.
_BIT_PATTERN = re.compile(r"(?i)(?:העבר\S*\s*ב?\s*bit|bit\s*העבר\S*)")

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
    """Strip national-ID identifiers, order/account references and owner names.

    Safe for any free-text field (description *and* reference): every pattern is
    label-anchored (מזהה / הזמנה / מח-ן) so it can't eat an opaque transaction id.
    """
    if not text:
        return text

    text = _ID_PATTERN.sub("", text)
    text = _ORDER_PATTERN.sub("", text)
    text = _ACCOUNT_PATTERN.sub("", text)

    for token in _name_tokens():
        # Whole-token match only: bounded by whitespace or string edges, so a
        # token never chops a substring out of an unrelated word.
        text = re.sub(rf"(?<!\S){re.escape(token)}(?!\S)", "", text)

    return _WS.sub(" ", text).strip()


def clean_description(text: str) -> str:
    """Full cleaning for the human-facing description field.

    On top of :func:`redact_pii`, strips bare long reference tokens (order/
    account numbers with no label) and collapses noisy transfer labels (Bit).
    NOT used on the ``reference`` field, which legitimately holds ids like
    ``TXN-12345``.
    """
    if not text:
        return text

    text = redact_pii(text)
    text = _REF_PATTERN.sub("", text)
    text = _WS.sub(" ", text).strip()

    # Bit peer-to-peer transfers → just "BIT" (drops any counterparty note).
    if _BIT_PATTERN.search(text):
        return "BIT"
    return text
