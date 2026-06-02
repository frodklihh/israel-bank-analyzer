"""report.py — Build a report from manually downloaded bank/card files.

When bank scrapers are blocked, download statements from bank websites
and feed them to this script.

Usage:
    python scripts/report.py --bank exports/hapoalim.xlsx --cards exports/isracard.xlsx
    python scripts/report.py --bank exports/leumi.xls --cards exports/cal1.xlsx exports/cal2.xlsx
    python scripts/report.py --cards exports/isracard.xlsx --year 2026 --month 5
    python scripts/report.py --bank exports/hapoalim.xlsx --cards exports/isracard.xlsx --email

Where to download files:
    Hapoalim:  https://www.bankhapoalim.co.il → עו"ש → ייצוא לאקסל
    Isracard:  https://digital.isracard.co.il → פירוט חיובים → ייצוא
    Leumi:     https://www.leumi.co.il → תנועות בחשבון → ייצוא
    Cal:       https://www.cal-online.co.il → פירוט חיובים → ייצוא
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from config.settings import email_config
from core.analytics import build_report
from core.period import billing_month
from leumi_analyzer.categorizer import categorize
from notifier.email import send_report
from scripts.importer import Transaction, load_file
from views.console import print_report
from views.html import save_html_report

BASE_DIR = Path(__file__).resolve().parent.parent


def _resolve_period(
    year: int | None,
    month: int | None,
    transactions: list[Transaction],
) -> tuple[int, int]:
    """Resolve year/month — from args, or guess from the most common month in data."""
    if year and month:
        return year, month

    if transactions:
        months: dict[tuple[int, int], int] = {}
        for tx in transactions:
            bm = billing_month(tx.date)
            key = (bm.year, bm.month)
            months[key] = months.get(key, 0) + 1
        best = max(months, key=months.get)
        return best

    now = datetime.today()
    return now.year, now.month


def _load_files(paths: list[str], source_label: str) -> list[Transaction]:
    """Load transactions from one or more files, tagging each with source."""
    all_txs: list[Transaction] = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            print(f"  ⚠ File not found: {path}")
            continue
        try:
            txs = load_file(path)
            # Override source to ensure correct bank/card classification
            for tx in txs:
                if source_label:
                    tx.source = source_label
            print(f"  ✅ {path.name}: {len(txs)} transactions")
            all_txs.extend(txs)
        except Exception as e:
            print(f"  ❌ {path.name}: {e}")
    return all_txs


def _run(args: argparse.Namespace) -> None:
    bank_files = args.bank or []
    card_files = args.cards or []

    if not bank_files and not card_files:
        print("❌ No files provided. Use --bank and/or --cards.")
        print("   Example: python scripts/report.py --bank hapoalim.xlsx --cards isracard.xlsx")
        sys.exit(1)

    print("\n📂 Loading bank files...")
    bank_txs = _load_files(bank_files, "bank") if bank_files else []

    print("\n💳 Loading card files...")
    card_txs = _load_files(card_files, "credit_card") if card_files else []

    all_txs = bank_txs + card_txs
    if not all_txs:
        print("\n❌ No transactions loaded from any file.")
        sys.exit(1)

    year, month = _resolve_period(args.year, args.month, all_txs)
    dest = BASE_DIR / "reports" / f"{year}-{month:02d}"
    dest.mkdir(parents=True, exist_ok=True)

    print(f"\nPeriod : {year}-{month:02d}")
    print(f"Bank   : {len(bank_txs)} transactions from {len(bank_files)} file(s)")
    print(f"Cards  : {len(card_txs)} transactions from {len(card_files)} file(s)")
    print(f"Output : {dest}\n")

    # Categorize
    bank_txs = categorize(bank_txs)
    card_txs = categorize(card_txs)

    # Build report
    report = build_report(bank_txs, card_txs, year=year, month=month)

    # Save outputs
    html_path = dest / "report.html"
    print_report(report, card_txs)
    save_html_report(report, output_path=str(html_path))
    print(f"\nReport saved: {html_path}")

    # Email (optional)
    if args.email:
        try:
            send_report(html_path, report, email_config())
        except Exception as e:
            print(f"[email] failed: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a financial report from manually downloaded bank/card files.",
        epilog="Download statements from bank websites, then run this script.",
    )
    parser.add_argument(
        "--bank",
        nargs="+",
        metavar="FILE",
        help="Bank statement file(s): .xls or .xlsx from Hapoalim/Leumi",
    )
    parser.add_argument(
        "--cards",
        nargs="+",
        metavar="FILE",
        help="Credit card file(s): .xlsx from Isracard/Cal/Leumi",
    )
    parser.add_argument("--year", type=int, help="Billing year (default: auto-detect from data)")
    parser.add_argument("--month", type=int, help="Billing month (default: auto-detect from data)")
    parser.add_argument("--email", action="store_true", help="Send report via email")
    args = parser.parse_args()
    _run(args)


if __name__ == "__main__":
    main()
