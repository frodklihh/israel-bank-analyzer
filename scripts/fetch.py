"""fetch.py — Main automation script: scrape all providers → build report → email.

Uses the Node.js israeli-bank-scrapers bridge via scraper_bridge module.
No more Playwright; no more file downloads; no more session handling.

Usage:
    python scripts/fetch.py --bank hapoalim:mikhail --cards isracard:mikhail
    python scripts/fetch.py --no-bank --cards isracard:mikhail isracard:daniil --email
    python scripts/fetch.py --year 2026 --month 4
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from config.settings import (
    cal_credentials,
    email_config,
    hapoalim_credentials,
    isracard_credentials,
    leumi_credentials,
)
from core.analytics import build_report
from core.period import billing_month
from fetcher.scraper_bridge import PROVIDERS, ScraperBridgeError, fetch as scrape_provider
from leumi_analyzer.categorizer import categorize
from notifier.email import send_report
from scripts.importer import Transaction
from views.console import print_report
from views.html import save_html_report

BASE_DIR = Path(__file__).resolve().parent.parent

_DEFAULT_BANK = "leumi"
_DEFAULT_CARDS = ["cal"]

_CREDENTIAL_LOADERS = {
    "leumi":    leumi_credentials,
    "hapoalim": hapoalim_credentials,
    "isracard": isracard_credentials,
    "cal":      cal_credentials,
}


def _resolve_period(year: int | None, month: int | None) -> tuple[int, int]:
    """Resolve year/month to concrete billing period (default: current)."""
    if year and month:
        return year, month
    current = billing_month(datetime.today())
    return current.year, current.month


def _load_credentials(provider_spec: str) -> tuple[str, str]:
    """Parse "provider" or "provider:profile" and return (base_name, profile)."""
    base, _, profile = provider_spec.partition(":")
    return base, profile


def _scrape_one(
    provider: str,
    start_date: datetime,
    show_browser: bool = True,
) -> list[Transaction]:
    """Scrape one provider using the Node bridge. Returns Transaction list or empty on error."""
    base, profile = _load_credentials(provider)

    if base not in _CREDENTIAL_LOADERS:
        print(f"[{provider}] unknown provider (available: {list(_CREDENTIAL_LOADERS)})")
        return []

    try:
        credentials = _CREDENTIAL_LOADERS[base](profile)
    except Exception as e:
        print(f"[{provider}] credential error: {e}")
        return []

    try:
        print(f"[{provider}] scraping from {start_date.date()}...")
        return scrape_provider(
            base,
            credentials,
            start_date=start_date,
            show_browser=show_browser,
        )
    except ScraperBridgeError as e:
        print(f"[{provider}] bridge error [{e.error_type}]: {e.message}")
        return []
    except Exception as e:
        print(f"[{provider}] unexpected error: {e}")
        return []


def _run(args: argparse.Namespace) -> None:
    year, month = _resolve_period(args.year, args.month)
    dest = BASE_DIR / "reports" / f"{year}-{month:02d}"
    dest.mkdir(parents=True, exist_ok=True)

    # Compute start_date: 60 days before the requested month.
    # (The Node bridge fetches from startDate onward; we'll filter in analytics.)
    target_date = datetime(year, month, 1)
    start_date = target_date - timedelta(days=60)

    card_specs = args.cards
    skip_bank = args.no_bank or not args.bank

    print(f"\nPeriod : {year}-{month:02d}")
    print(f"Bank   : {'(skipped)' if skip_bank else args.bank}")
    print(f"Cards  : {', '.join(card_specs)}")
    print(f"Output : {dest}")
    print(f"Browser: {'hidden (--headless)' if args.headless else 'visible (can enter OTP)'}\n")

    # Scrape bank
    bank_txs: list[Transaction] = []
    if not skip_bank:
        bank_txs = _scrape_one(args.bank, start_date, show_browser=not args.headless)
        if bank_txs:
            print(f"  ✅ {len(bank_txs)} bank transactions")
        else:
            print(f"  ❌ bank scrape failed or returned no transactions")

    # Scrape all card providers
    card_txs: list[Transaction] = []
    for card_spec in card_specs:
        txs = _scrape_one(card_spec, start_date, show_browser=not args.headless)
        if txs:
            print(f"  ✅ {card_spec}: {len(txs)} card transactions")
        else:
            print(f"  ❌ {card_spec}: no transactions")
        card_txs.extend(txs)

    if not bank_txs and not card_txs:
        print("\n❌ No transactions scraped — nothing to analyse.")
        return

    print(f"\nTotal: {len(bank_txs)} bank + {len(card_txs)} card transactions\n")

    # Categorize
    bank_txs = categorize(bank_txs)
    card_txs = categorize(card_txs)

    # Build report
    report = build_report(bank_txs, card_txs, year=year, month=month)

    # Save outputs
    html_path = dest / "report.html"
    print_report(report, card_txs)
    save_html_report(report, output_path=str(html_path))
    print(f"Report saved: {html_path}")

    # Email (optional)
    if args.email:
        try:
            send_report(html_path, report, email_config())
        except Exception as e:
            print(f"[email] failed: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Israeli bank + card statements via israeli-bank-scrapers. "
        "No file downloads, no session files — straight JSON → report.",
    )
    parser.add_argument("--year", type=int, help="Billing year (default: current)")
    parser.add_argument("--month", type=int, help="Billing month (default: current)")
    parser.add_argument(
        "--bank",
        default=_DEFAULT_BANK,
        metavar="PROVIDER[:PROFILE]",
        help=(
            f"Bank provider with optional profile. "
            f"Providers: {list(PROVIDERS)}. "
            f"Example: hapoalim:mikhail"
        ),
    )
    parser.add_argument(
        "--no-bank",
        action="store_true",
        help="Skip bank statement (cards only)",
    )
    parser.add_argument(
        "--cards",
        nargs="+",
        default=_DEFAULT_CARDS,
        metavar="PROVIDER[:PROFILE]",
        help=(
            f"Card provider(s) with optional profile. "
            f"Providers: {list(PROVIDERS)}. "
            f"Example: isracard:mikhail isracard:daniil"
        ),
    )
    parser.add_argument(
        "--email",
        action="store_true",
        help="Send report via email (requires SMTP_* env vars)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Hide browser (default: visible for OTP entry)",
    )
    args = parser.parse_args()

    _run(args)


if __name__ == "__main__":
    main()
