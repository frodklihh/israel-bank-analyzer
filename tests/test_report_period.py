"""test_report_period.py — _resolve_period in scripts/report.py.

Regression: --year without --month must produce a full-year report
(month=None), not silently collapse to a single month.
"""

from datetime import datetime

from scripts.importer import Transaction
from scripts.report import _resolve_period


def _tx(year, month, day=5):
    return Transaction(
        date=datetime(year, month, day),
        description="x", reference="",
        debit=10, credit=0, balance=0, source="bank",
    )


class TestResolvePeriod:
    def test_year_only_means_full_year(self):
        txs = [_tx(2026, 1), _tx(2026, 2), _tx(2026, 3)]
        assert _resolve_period(2026, None, txs) == (2026, None)

    def test_year_and_month_explicit(self):
        assert _resolve_period(2026, 5, []) == (2026, 5)

    def test_no_args_guesses_dominant_month(self):
        # Most rows are in May (billing month) → focused single-month report.
        txs = [_tx(2026, 5), _tx(2026, 5), _tx(2026, 3)]
        assert _resolve_period(None, None, txs) == (2026, 5)

    def test_month_only_pairs_with_data_year(self):
        txs = [_tx(2026, 5), _tx(2026, 4)]
        assert _resolve_period(None, 4, txs) == (2026, 4)
