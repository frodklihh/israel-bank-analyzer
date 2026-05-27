"""scraper_bridge.py — Python side of the Node.js israeli-bank-scrapers bridge.

The Node side (scraper/bridge.js) is a thin JSON-in / JSON-out wrapper around
the `israeli-bank-scrapers` npm package. We call it via subprocess, hand it the
credentials over stdin, and receive a list of accounts + transactions back.

This module owns:
  - the subprocess call
  - the JSON → Transaction conversion
  - the per-provider credential mapping (Hapoalim needs userCode, Isracard
    needs id + card6Digits, etc.)
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config.settings import BankCredentials
from scripts.importer import Transaction

# Path to scraper/bridge.js relative to project root.
_BRIDGE_DIR = Path(__file__).resolve().parent.parent / "scraper"
_BRIDGE_JS = _BRIDGE_DIR / "bridge.js"


# ── Provider configuration ───────────────────────────────────────────────────
#
# Each provider maps its (user, password) BankCredentials pair onto the
# field names that israeli-bank-scrapers expects.  "kind" is used to tag
# our Transaction.source so the downstream categorizer/analytics know
# whether to treat the line as a bank movement or a card charge.


@dataclass(frozen=True)
class ProviderSpec:
    company_id: str                     # CompanyTypes key in JS
    kind: str                           # "bank" or "credit_card"
    credentials_keys: tuple[str, str]   # which JSON keys map to (user, password)


PROVIDERS: dict[str, ProviderSpec] = {
    "leumi":    ProviderSpec("leumi",    "bank",        ("username", "password")),
    "hapoalim": ProviderSpec("hapoalim", "bank",        ("userCode", "password")),
    "isracard": ProviderSpec("isracard", "credit_card", ("id",       "password")),
    # Cal uses id + last 6 card digits + password. We currently store only
    # user+password in BankCredentials; Cal will need a separate handling
    # path or an extension to BankCredentials before it works.
    "visaCal":  ProviderSpec("visaCal",  "credit_card", ("username", "password")),
}


# ── Bridge invocation ────────────────────────────────────────────────────────


class ScraperBridgeError(RuntimeError):
    """Raised when the Node bridge returns success: false or crashes."""

    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(f"{error_type}: {message}")
        self.error_type = error_type
        self.message = message


def _run_bridge(request: dict) -> dict:
    """Spawn `node bridge.js`, pipe the request as JSON to stdin, parse stdout."""
    if not _BRIDGE_JS.exists():
        raise FileNotFoundError(
            f"Bridge script not found at {_BRIDGE_JS}. "
            f"Did you run `npm install` inside {_BRIDGE_DIR}?"
        )

    proc = subprocess.run(
        ["node", str(_BRIDGE_JS)],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(_BRIDGE_DIR),
        # No timeout here — login may require manual OTP entry in the browser.
    )

    # Mirror bridge progress messages (use binary write to avoid encoding issues on Windows).
    if proc.stderr:
        sys.stdout.buffer.write(proc.stderr.encode("utf-8"))
        sys.stdout.buffer.flush()

    if not proc.stdout.strip():
        raise ScraperBridgeError(
            "BRIDGE_NO_OUTPUT",
            f"Bridge produced no stdout (exit code {proc.returncode}).",
        )

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ScraperBridgeError(
            "BRIDGE_BAD_JSON",
            f"Could not parse bridge stdout as JSON: {e}\n--- stdout ---\n{proc.stdout}",
        )


# ── Conversion: scraper JSON → our Transaction ───────────────────────────────


def _to_transaction(raw: dict, kind: str, account_balance: float | None) -> Transaction | None:
    """Convert a single scraper transaction dict to our Transaction.

    Returns None for entries that should be skipped (missing date, pending
    rows that we don't want yet, etc.).
    """
    date_str = raw.get("date") or raw.get("processedDate")
    if not date_str:
        return None

    try:
        # israeli-bank-scrapers emits ISO 8601 with timezone, e.g.
        # "2026-05-12T00:00:00.000Z"
        date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None

    amount = raw.get("chargedAmount")
    if amount is None:
        amount = raw.get("originalAmount", 0.0)
    amount = float(amount)

    # The scraper uses signed amounts: negative = money leaving (debit/expense),
    # positive = money coming in (credit/refund/income).
    if amount < 0:
        debit = abs(amount)
        credit = 0.0
    else:
        debit = 0.0
        credit = amount

    description = (raw.get("description") or "").strip()
    reference = str(raw.get("identifier") or raw.get("memo") or "").strip()

    return Transaction(
        date=date,
        description=description,
        reference=reference,
        debit=debit,
        credit=credit,
        balance=account_balance or 0.0,
        source=kind,
    )


def _flatten(result: dict, kind: str) -> list[Transaction]:
    """Walk the scraper result tree (accounts → txns) and emit Transactions."""
    transactions: list[Transaction] = []
    for account in result.get("accounts", []):
        # Balance is reported per-account, not per-row, so every transaction
        # gets the same closing balance. Good enough for the analytics layer
        # which only uses opening/closing.
        balance = account.get("balance")
        for raw_tx in account.get("txns", []):
            tx = _to_transaction(raw_tx, kind, balance)
            if tx is not None:
                transactions.append(tx)
    return transactions


# ── Public API ───────────────────────────────────────────────────────────────


def fetch(
    provider: str,
    credentials: BankCredentials,
    *,
    start_date: datetime,
    show_browser: bool = True,
    combine_installments: bool = False,
) -> list[Transaction]:
    """Run the bridge for one provider, return the transactions it scraped."""
    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider}'. Available: {list(PROVIDERS)}"
        )

    spec = PROVIDERS[provider]
    user_key, pass_key = spec.credentials_keys

    request = {
        "provider":            spec.company_id,
        "credentials":         {user_key: credentials.user, pass_key: credentials.password},
        "startDate":           start_date.strftime("%Y-%m-%d"),
        "showBrowser":         show_browser,
        "combineInstallments": combine_installments,
    }

    print(f"[bridge] launching scraper for {provider} (showBrowser={show_browser})...")
    result = _run_bridge(request)

    if not result.get("success"):
        raise ScraperBridgeError(
            result.get("errorType", "UNKNOWN"),
            result.get("errorMessage", "(no message)"),
        )

    return _flatten(result, spec.kind)
