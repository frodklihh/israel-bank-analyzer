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


def _credentials(provider: str, profile: str = "", *, needs_card6: bool = False) -> BankCredentials:
    """Load credentials for a provider, optionally scoped to a named profile.

    No profile:   ISRACARD_USER / ISRACARD_PASSWORD
    Profile=elena: ISRACARD_ELENA_USER / ISRACARD_ELENA_PASSWORD

    When ``needs_card6`` is set (Isracard/Amex), also require ``{PREFIX}CARD6``
    — the last 6 digits of the card, which israeli-bank-scrapers needs in
    addition to id + password.
    """
    prefix = f"{provider.upper()}_{profile.upper()}_" if profile else f"{provider.upper()}_"
    return BankCredentials(
        user=_require(f"{prefix}USER"),
        password=_require(f"{prefix}PASSWORD"),
        card6=_require(f"{prefix}CARD6") if needs_card6 else "",
    )


def leumi_credentials(profile: str = "") -> BankCredentials:
    return _credentials("leumi", profile)


def cal_credentials(profile: str = "") -> BankCredentials:
    return _credentials("cal", profile)


def hapoalim_credentials(profile: str = "") -> BankCredentials:
    return _credentials("hapoalim", profile)


def isracard_credentials(profile: str = "") -> BankCredentials:
    return _credentials("isracard", profile, needs_card6=True)


def email_config() -> EmailConfig:
    return EmailConfig(
        host=_optional("SMTP_HOST", "smtp.gmail.com"),
        port=int(_optional("SMTP_PORT", "587")),
        user=_require("SMTP_USER"),
        password=_require("SMTP_PASSWORD"),
        sender=_optional("EMAIL_FROM") or _require("SMTP_USER"),
        recipient=_require("EMAIL_TO"),
    )


SESSION_DIR = Path.home() / ".leumi_analyzer" / "sessions"
