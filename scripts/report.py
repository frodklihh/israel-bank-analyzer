"""report.py — Build a report from manually downloaded bank/card files.

When bank scrapers are blocked, download statements from bank websites
and feed them to this script.

The simplest path: drop your statements into the ready-made folders and run
with no arguments —

    reports/exports/bank/    ← bank statements (Leumi / Hapoalim)
    reports/exports/cards/   ← credit cards   (Isracard / Cal / Leumi)

    python scripts/report.py                 # loads both default folders

Usage:
    python scripts/report.py --bank exports/hapoalim.xlsx --cards exports/isracard.xlsx
    python scripts/report.py --bank exports/leumi.xls --cards exports/cal1.xlsx exports/cal2.xlsx
    python scripts/report.py --cards exports/isracard.xlsx --year 2026 --month 5
    python scripts/report.py --bank exports/hapoalim.xlsx --cards exports/isracard.xlsx --email
    python scripts/report.py --cards-dir exports/        # load every file in a folder
    python scripts/report.py --dir exports/daniel/       # one mixed folder, auto bank/card

Where to download files:
    Hapoalim:  https://www.bankhapoalim.co.il → עו"ש → ייצוא לאקסל
    Isracard:  https://digital.isracard.co.il → פירוט חיובים → ייצוא
    Leumi:     https://www.leumi.co.il → תנועות בחשבון → ייצוא
    Cal:       https://www.cal-online.co.il → פירוט חיובים → ייצוא
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from config.settings import email_config
from core.analytics import build_report
from core.period import billing_month
from israel_bank_analyzer.categorizer import categorize
from notifier.email import send_report
from scripts.importer import Transaction, load_file
from views.console import print_report
from views.html import save_html_report

# The console output uses emoji/Hebrew; on a default Windows console (cp1252)
# printing them raises UnicodeEncodeError. Force UTF-8 so the script runs the
# same on any tester's machine.
for _stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(_stream, "reconfigure", None)
    if reconfigure:
        reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent

# Ready-made drop folders. If the user runs the script with no path flags,
# every statement in these is loaded — bank files from one, cards from the
# other — so there's no guessing where downloads should go.
DEFAULT_BANK_DIR = BASE_DIR / "reports" / "exports" / "bank"
DEFAULT_CARDS_DIR = BASE_DIR / "reports" / "exports" / "cards"


def _resolve_period(
    year: int | None,
    month: int | None,
    transactions: list[Transaction],
) -> tuple[int, int | None]:
    """Resolve (year, month). A None month means a full-year report.

    - ``--year`` given: honoured as-is. Without ``--month`` this yields a
      full-year report (every month aggregated, recurring charges summed),
      instead of silently collapsing to a single month.
    - No ``--year``: guess the dominant period from the data (a focused
      single-month report), or fall back to today.
    """
    if year:
        return year, month

    if transactions:
        months: dict[tuple[int, int], int] = {}
        for tx in transactions:
            bm = billing_month(tx.date)
            key = (bm.year, bm.month)
            months[key] = months.get(key, 0) + 1
        best_year, best_month = max(months, key=months.get)
        return best_year, (month if month else best_month)

    now = datetime.today()
    return now.year, (month if month else now.month)


def _collect_paths(files: list[str], dirs: list[str]) -> list[str]:
    """Combine explicit files with every .xls/.xlsx inside the given dirs.

    Lets the user drop all their downloaded statements into one folder
    (e.g. ``--cards-dir exports/``) instead of listing each file by hand.
    """
    paths: list[str] = list(files)
    for d in dirs:
        directory = Path(d)
        if not directory.is_dir():
            print(f"  ⚠ Not a directory: {directory}")
            continue
        found = sorted(
            p for p in directory.iterdir()
            if p.suffix.lower() in (".xls", ".xlsx") and not p.name.startswith("~$")
        )
        if not found:
            print(f"  ⚠ No .xls/.xlsx files in: {directory}")
        paths.extend(str(p) for p in found)
    return paths


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


def _classify_dir(dirs: list[str]) -> tuple[list[Transaction], list[Transaction]]:
    """Load every .xls/.xlsx in mixed folder(s), routing each file to bank or
    cards by its auto-detected format.

    ``load_file`` already recognises the format (bank statement vs Isracard/Cal/
    Leumi card), so a single folder can hold both kinds and still run in one
    command. The scan recurses, so it works whether statements sit flat in the
    folder or are pre-split into bank/ and cards/ subfolders — classification is
    by file format, not folder name. Bank files keep source "bank"; every card
    file is normalised to "credit_card" so the report's bank-vs-card logic works
    regardless of the card issuer.
    """
    bank_txs: list[Transaction] = []
    card_txs: list[Transaction] = []
    for d in dirs:
        directory = Path(d)
        if not directory.is_dir():
            print(f"  ⚠ Not a directory: {directory}")
            continue
        found = sorted(
            p for p in directory.rglob("*")
            if p.is_file()
            and p.suffix.lower() in (".xls", ".xlsx")
            and not p.name.startswith("~$")
        )
        if not found:
            print(f"  ⚠ No .xls/.xlsx files in: {directory}")
        for p in found:
            try:
                txs = load_file(p)
            except Exception as e:
                print(f"  ❌ {p.name}: {e}")
                continue
            if not txs:
                print(f"  ⚠ {p.name}: 0 transactions")
                continue
            is_bank = txs[0].source == "bank"
            label = "bank" if is_bank else "credit_card"
            for tx in txs:
                tx.source = label
            (bank_txs if is_bank else card_txs).extend(txs)
            print(f"  ✅ {p.name}: {len(txs)} {'bank' if is_bank else 'card'}")
    return bank_txs, card_txs


def _run(args: argparse.Namespace) -> None:
    # With no path flags at all, fall back to the ready-made drop folders so
    # `python scripts/report.py` "just works" once files are in place.
    no_paths = not any([args.bank, args.cards, args.bank_dir, args.cards_dir, args.dir])
    bank_dirs = args.bank_dir or ([str(DEFAULT_BANK_DIR)] if no_paths else [])
    card_dirs = args.cards_dir or ([str(DEFAULT_CARDS_DIR)] if no_paths else [])

    bank_files = _collect_paths(args.bank or [], bank_dirs)
    card_files = _collect_paths(args.cards or [], card_dirs)

    if not bank_files and not card_files and not args.dir:
        print("❌ No files found.")
        print(f"   Drop bank statements into : {DEFAULT_BANK_DIR}")
        print(f"   Drop credit-card files into: {DEFAULT_CARDS_DIR}")
        print("   ...then run: python scripts/report.py")
        print("   Or pass paths explicitly: --bank/--cards, --bank-dir/--cards-dir, or --dir")
        sys.exit(1)

    print("\n📂 Loading bank files...")
    bank_txs = _load_files(bank_files, "bank") if bank_files else []

    print("\n💳 Loading card files...")
    card_txs = _load_files(card_files, "credit_card") if card_files else []

    # One mixed folder → auto-route each file to bank/cards by its format, so
    # the whole folder runs in a single command (no bank/ + cards/ split).
    if args.dir:
        print("\n🔀 Auto-classifying mixed folder(s)...")
        auto_bank, auto_cards = _classify_dir(args.dir)
        bank_txs += auto_bank
        card_txs += auto_cards

    all_txs = bank_txs + card_txs
    if not all_txs:
        print("\n❌ No transactions loaded from any file.")
        sys.exit(1)

    if args.all:
        # No period filter at all: every transaction across every file/year
        # is counted (the complete picture, e.g. Dec 2025 + all of 2026).
        year, month = None, None
        period_dir = "all"
        period_desc = "all data (no period filter)"
    else:
        year, month = _resolve_period(args.year, args.month, all_txs)
        period_dir = f"{year}-{month:02d}" if month else str(year)
        period_desc = f"{period_dir}{'' if month else ' (full year)'}"
    dest = BASE_DIR / "reports" / period_dir
    dest.mkdir(parents=True, exist_ok=True)

    print(f"\nPeriod : {period_desc}")
    print(f"Bank   : {len(bank_txs)} transactions")
    print(f"Cards  : {len(card_txs)} transactions")
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

    # Also refresh a stable "latest" copy at reports/report.html, so a
    # bookmarked file never goes stale (and never shows pre-redaction data).
    latest_path = BASE_DIR / "reports" / "report.html"
    shutil.copyfile(html_path, latest_path)
    print(f"Latest:       {latest_path}")

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
    parser.add_argument(
        "--bank-dir",
        nargs="+",
        metavar="DIR",
        help="Folder(s) of bank statements: every .xls/.xlsx inside is loaded",
    )
    parser.add_argument(
        "--cards-dir",
        nargs="+",
        metavar="DIR",
        help="Folder(s) of card files: every .xls/.xlsx inside is loaded",
    )
    parser.add_argument(
        "--dir",
        nargs="+",
        metavar="DIR",
        help="Folder(s) of MIXED bank + card files: each file is auto-classified "
             "by its format, so one folder runs in a single command. Recurses "
             "into subfolders, so flat or bank/+cards/ layouts both work.",
    )
    parser.add_argument(
        "--year", type=int,
        help="Billing year. Given without --month → full-year report "
             "(every month, recurring charges summed). Default: auto-detect.",
    )
    parser.add_argument("--month", type=int, help="Billing month (default: auto-detect from data)")
    parser.add_argument(
        "--all", action="store_true",
        help="Count every transaction across all files, no period filter "
             "(includes every month/year present). Overrides --year/--month.",
    )
    parser.add_argument("--email", action="store_true", help="Send report via email")
    args = parser.parse_args()
    _run(args)


if __name__ == "__main__":
    main()
