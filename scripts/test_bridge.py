"""test_bridge.py — quick sanity-check for the scraper bridge.

Usage:
    python scripts/test_bridge.py hapoalim:mikhail
    python scripts/test_bridge.py isracard --start 2026-04-01

It does *not* go through the full analytics pipeline — it just calls the
bridge for ONE provider and prints what came back. Use this to verify that
the Node side is working before wiring it into fetch.py.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta

from config.settings import (
    cal_credentials,
    hapoalim_credentials,
    isracard_credentials,
    leumi_credentials,
)
from fetcher.scraper_bridge import PROVIDERS, ScraperBridgeError, fetch

_CREDENTIAL_LOADERS = {
    "leumi":    leumi_credentials,
    "hapoalim": hapoalim_credentials,
    "isracard": isracard_credentials,
    "cal":      cal_credentials,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Test one scraper-bridge provider end-to-end.")
    parser.add_argument(
        "provider",
        metavar="PROVIDER[:PROFILE]",
        help=f"Provider to test. Available: {list(PROVIDERS)}. Optional profile, e.g. hapoalim:mikhail",
    )
    parser.add_argument(
        "--start",
        help="Start date YYYY-MM-DD (default: 60 days ago)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Hide the browser (default: visible, so you can solve OTP)",
    )
    args = parser.parse_args()

    name, _, profile = args.provider.partition(":")
    if name not in _CREDENTIAL_LOADERS:
        parser.error(f"Unknown provider '{name}'. Available: {list(_CREDENTIAL_LOADERS)}")

    start = datetime.fromisoformat(args.start) if args.start else datetime.today() - timedelta(days=60)
    credentials = _CREDENTIAL_LOADERS[name](profile)

    print(f"Provider : {name} (profile={profile or '<default>'})")
    print(f"Since    : {start.date()}")
    print(f"Browser  : {'hidden' if args.headless else 'visible'}\n")

    try:
        txs = fetch(
            name,
            credentials,
            start_date=start,
            show_browser=not args.headless,
        )
    except ScraperBridgeError as e:
        print(f"\n❌ Bridge error [{e.error_type}]: {e.message}")
        return

    print(f"\n✅ Got {len(txs)} transactions")
    for tx in txs[:10]:
        sign = "-" if tx.debit else "+"
        amount = tx.debit or tx.credit
        print(f"  {tx.date.strftime('%d.%m.%Y')}  {sign}₪{amount:>9,.2f}  {tx.description[:50]}")

    if len(txs) > 10:
        print(f"  ... and {len(txs) - 10} more")


if __name__ == "__main__":
    main()
