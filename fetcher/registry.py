from __future__ import annotations

from typing import Callable

from config.settings import (
    BankCredentials,
    cal_credentials,
    hapoalim_credentials,
    isracard_credentials,
    leumi_credentials,
)
from fetcher.base import BankFetcher
from fetcher.cal import CalCardFetcher
from fetcher.hapoalim import HapoalimFetcher
from fetcher.isracard import IsracardFetcher
from fetcher.leumi import LeumiAccountFetcher

type CredentialsFn = Callable[[], BankCredentials]

# Each entry: display-name → (fetcher class, credentials loader)
# "bank" fetchers produce bank-statement files; "card" fetchers produce card files.
BANK_REGISTRY: dict[str, tuple[type[BankFetcher], CredentialsFn]] = {
    "leumi":    (LeumiAccountFetcher, leumi_credentials),
    "hapoalim": (HapoalimFetcher,     hapoalim_credentials),
}

CARD_REGISTRY: dict[str, tuple[type[BankFetcher], CredentialsFn]] = {
    "cal":      (CalCardFetcher,   cal_credentials),
    "isracard": (IsracardFetcher,  isracard_credentials),
}


def make_bank_fetcher(name: str) -> BankFetcher:
    provider, _, profile = name.partition(":")
    if provider not in BANK_REGISTRY:
        raise ValueError(f"Unknown bank: '{provider}'. Available: {list(BANK_REGISTRY)}")
    cls, creds_fn = BANK_REGISTRY[provider]
    fetcher = cls(creds_fn(profile))
    if profile:
        fetcher.name = f"{fetcher.name}_{profile}"
    return fetcher


def make_card_fetcher(name: str) -> BankFetcher:
    provider, _, profile = name.partition(":")
    if provider not in CARD_REGISTRY:
        raise ValueError(f"Unknown card provider: '{provider}'. Available: {list(CARD_REGISTRY)}")
    cls, creds_fn = CARD_REGISTRY[provider]
    fetcher = cls(creds_fn(profile))
    if profile:
        fetcher.name = f"{fetcher.name}_{profile}"
    return fetcher
