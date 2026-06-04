from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class BankCredentials:
    user: str
    password: str
    # Only Isracard/Amex need this (last 6 card digits). Empty for all others.
    card6: str = ""


@dataclass(frozen=True)
class EmailConfig:
    host: str
    port: int
    user: str
    password: str
    sender: str
    recipient: str


def _require(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise EnvironmentError(f"Missing required env var: {key}")
    return value


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


# israeli-bank-scrapers provider ids, grouped by what they scrape. A single
# install belongs to one user: one bank + one card issuer, selected by the
# BANK_PROVIDER / CARDS_PROVIDER env vars.
BANK_PROVIDERS = {"leumi", "hapoalim"}
CARD_PROVIDERS = {"isracard", "cal", "leumi"}
# Issuers that also require the card's last 6 digits.
_CARD6_PROVIDERS = {"isracard"}


def bank_provider() -> str:
    """The configured bank provider id (e.g. 'hapoalim')."""
    return _require("BANK_PROVIDER").lower()


def cards_provider() -> str:
    """The configured credit-card provider id (e.g. 'isracard')."""
    return _require("CARDS_PROVIDER").lower()


def bank_credentials() -> BankCredentials:
    """The user's bank login, from BANK_* env vars."""
    return BankCredentials(
        user=_require("BANK_USER"),
        password=_require("BANK_PASSWORD"),
        card6=_optional("BANK_CARD6") if bank_provider() in _CARD6_PROVIDERS else "",
    )


def cards_credentials() -> BankCredentials:
    """The user's credit-card login, from CARDS_* env vars.

    Isracard also needs CARDS_CARD6 (last 6 digits of the card) on top of the
    id + password.
    """
    return BankCredentials(
        user=_require("CARDS_USER"),
        password=_require("CARDS_PASSWORD"),
        card6=_require("CARDS_CARD6") if cards_provider() in _CARD6_PROVIDERS else "",
    )


def email_config() -> EmailConfig:
    user = _require("SMTP_USER")
    # Sender defaults to the login user; set EMAIL_FROM to send "as" another
    # address (e.g. a Firefox Relay mask — must be a verified alias on the
    # SMTP account, or the provider will reject/rewrite the From header).
    sender = _optional("EMAIL_FROM") or user
    return EmailConfig(
        host=_optional("SMTP_HOST", "smtp.gmail.com"),
        port=int(_optional("SMTP_PORT", "587")),
        user=user,
        password=_require("SMTP_PASSWORD"),
        sender=sender,
        # EMAIL_TO is optional — when unset the report is sent to the sender.
        recipient=_optional("EMAIL_TO") or sender,
    )


SESSION_DIR = Path.home() / ".israel_bank_analyzer" / "sessions"
