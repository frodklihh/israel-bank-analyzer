"""fetch.py — Main automation script: scrape the bank + card → build report → email.

Uses the Node.js israeli-bank-scrapers bridge via scraper_bridge module.
No more Playwright; no more file downloads; no more session handling.

Which bank/card to scrape comes from .env (BANK_PROVIDER + CARDS_PROVIDER and
their credentials), so day-to-day you just run:

    python scripts/fetch.py                 # scrape configured bank + card
    python scripts/fetch.py --no-bank       # cards only
    python scripts/fetch.py --year 2026 --month 4 --email
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Console output uses emoji/Hebrew; force UTF-8 so it doesn't crash on a
# default Windows console (cp1252).
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure:
        _reconfigure(encoding="utf-8")

from config.settings import (
    bank_credentials,
    bank_provider,
    cards_credentials,
    cards_provider,
    email_config,
)
from core.analytics import build_report
from core.period import billing_month
from fetcher.scraper_bridge import ScraperBridgeError, fetch as scrape_provider
from israel_bank_analyzer.categorizer import categorize
from notifier.email import send_report
from scripts.importer import Transaction
from views.console import print_report
from views.html import save_html_report

BASE_DIR = Path(__file__).resolve().parent.parent


def _resolve_period(year: int | None, month: int | None) -> tuple[int, int]:
    """Resolve year/month to concrete billing period (default: current)."""
    if year and month:
        return year, month
    current = billing_month(datetime.today())
    return current.year, current.month


def _safe(loader, label: str):
    """Call a config loader, turning a missing-env error into a friendly note."""
    try:
        return loader()
    except Exception as e:
        print(f"  ⚠ {label} not configured: {e}")
        return None


def _scrape_one(
    provider: str,
    credentials,
    start_date: datetime,
    show_browser: bool = True,
) -> list[Transaction]:
    """Scrape one provider via the Node bridge. Returns [] on error."""
    try:
        print(f"[{provider}] scraping from {start_date.date()}...")
        return scrape_provider(
            provider,
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

    show_browser = not args.headless

    # Resolve which providers to scrape from .env (skippable via flags).
    bank_prov = None if args.no_bank else _safe(bank_provider, "BANK_PROVIDER")
    cards_prov = None if args.no_cards else _safe(cards_provider, "CARDS_PROVIDER")

    print(f"\nPeriod : {year}-{month:02d}")
    print(f"Bank   : {bank_prov or '(skipped)'}")
    print(f"Cards  : {cards_prov or '(skipped)'}")
    print(f"Output : {dest}")
    print(f"Browser: {'hidden (--headless)' if args.headless else 'visible (can enter OTP)'}\n")

    # Scrape bank
    bank_txs: list[Transaction] = []
    if bank_prov:
        creds = _safe(bank_credentials, "bank credentials")
        if creds:
            bank_txs = _scrape_one(bank_prov, creds, start_date, show_browser=show_browser)
        print(f"  {'✅' if bank_txs else '❌'} bank: {len(bank_txs)} transactions")

    # Scrape cards
    card_txs: list[Transaction] = []
    if cards_prov:
        creds = _safe(cards_credentials, "card credentials")
        if creds:
            card_txs = _scrape_one(cards_prov, creds, start_date, show_browser=show_browser)
        print(f"  {'✅' if card_txs else '❌'} cards: {len(card_txs)} transactions")

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
        "--no-bank",
        action="store_true",
        help="Skip the bank statement (cards only)",
    )
    parser.add_argument(
        "--no-cards",
        action="store_true",
        help="Skip the credit card (bank only)",
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
