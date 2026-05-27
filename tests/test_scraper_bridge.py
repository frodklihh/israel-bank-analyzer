"""test_scraper_bridge.py — unit tests for the scraper bridge Python side.

Tests the conversion logic (_to_transaction, _flatten) without calling the Node
bridge or hitting real bank sites.
"""

import pytest
from datetime import datetime

from config.settings import BankCredentials
from fetcher.scraper_bridge import (
    PROVIDERS,
    ProviderSpec,
    _flatten,
    _to_transaction,
)
from scripts.importer import Transaction


class TestProviderRegistry:
    """Verify that all required providers are registered with correct specs."""

    def test_leumi_spec(self) -> None:
        spec = PROVIDERS["leumi"]
        assert spec.company_id == "leumi"
        assert spec.kind == "bank"
        assert spec.credentials_keys == ("username", "password")

    def test_hapoalim_spec(self) -> None:
        spec = PROVIDERS["hapoalim"]
        assert spec.company_id == "hapoalim"
        assert spec.kind == "bank"
        assert spec.credentials_keys == ("userCode", "password")

    def test_isracard_spec(self) -> None:
        spec = PROVIDERS["isracard"]
        assert spec.company_id == "isracard"
        assert spec.kind == "credit_card"
        assert spec.credentials_keys == ("id", "password")

    def test_visaCal_spec(self) -> None:
        spec = PROVIDERS["visaCal"]
        assert spec.company_id == "visaCal"
        assert spec.kind == "credit_card"


class TestTransactionConversion:
    """Test _to_transaction conversion from scraper JSON to our Transaction format."""

    def test_positive_amount_becomes_credit(self) -> None:
        """Positive chargedAmount = money coming in = credit."""
        raw = {
            "date": "2026-05-15T00:00:00.000Z",
            "description": "Salary",
            "chargedAmount": 10000.0,  # positive = income
        }
        tx = _to_transaction(raw, kind="bank", account_balance=50000.0)
        assert tx is not None
        assert tx.debit == 0.0
        assert tx.credit == 10000.0
        assert tx.source == "bank"

    def test_negative_amount_becomes_debit(self) -> None:
        """Negative chargedAmount = money going out = debit."""
        raw = {
            "date": "2026-05-15T00:00:00.000Z",
            "description": "Rent",
            "chargedAmount": -4500.0,  # negative = expense
        }
        tx = _to_transaction(raw, kind="bank", account_balance=40000.0)
        assert tx is not None
        assert tx.debit == 4500.0
        assert tx.credit == 0.0

    def test_missing_date_returns_none(self) -> None:
        """Transactions without date are skipped."""
        raw = {
            "description": "Unknown",
            "chargedAmount": -100.0,
        }
        tx = _to_transaction(raw, kind="bank", account_balance=0.0)
        assert tx is None

    def test_fallback_to_originalAmount(self) -> None:
        """If chargedAmount is missing, try originalAmount."""
        raw = {
            "date": "2026-05-15T00:00:00.000Z",
            "description": "Test",
            "originalAmount": -50.0,
        }
        tx = _to_transaction(raw, kind="credit_card", account_balance=None)
        assert tx is not None
        assert tx.debit == 50.0

    def test_kind_is_preserved(self) -> None:
        """The 'kind' parameter becomes Transaction.source."""
        raw = {
            "date": "2026-05-15T00:00:00.000Z",
            "description": "Card transaction",
            "chargedAmount": -200.0,
        }
        tx = _to_transaction(raw, kind="credit_card", account_balance=None)
        assert tx is not None
        assert tx.source == "credit_card"

    def test_description_and_reference(self) -> None:
        """description and identifier/memo are preserved."""
        raw = {
            "date": "2026-05-15T00:00:00.000Z",
            "description": "Coffee Shop",
            "identifier": "TXN-12345",
            "chargedAmount": -35.0,
        }
        tx = _to_transaction(raw, kind="credit_card", account_balance=None)
        assert tx is not None
        assert tx.description == "Coffee Shop"
        assert tx.reference == "TXN-12345"


class TestFlatten:
    """Test _flatten: walking the account tree and emitting Transactions."""

    def test_single_account_single_transaction(self) -> None:
        """Parse a minimal valid scraper result."""
        result = {
            "success": True,
            "accounts": [
                {
                    "accountNumber": "123456",
                    "balance": 25000.0,
                    "txns": [
                        {
                            "date": "2026-05-15T00:00:00.000Z",
                            "description": "Coffee",
                            "chargedAmount": -50.0,
                        }
                    ],
                }
            ],
        }
        txs = _flatten(result, kind="bank")
        assert len(txs) == 1
        assert txs[0].description == "Coffee"
        assert txs[0].debit == 50.0
        assert txs[0].balance == 25000.0

    def test_multiple_accounts_are_flattened(self) -> None:
        """Transactions from multiple accounts are merged into one list."""
        result = {
            "success": True,
            "accounts": [
                {
                    "accountNumber": "ACC1",
                    "balance": 10000.0,
                    "txns": [
                        {"date": "2026-05-15T00:00:00.000Z", "description": "TX1", "chargedAmount": -100.0}
                    ],
                },
                {
                    "accountNumber": "ACC2",
                    "balance": 20000.0,
                    "txns": [
                        {"date": "2026-05-14T00:00:00.000Z", "description": "TX2", "chargedAmount": -200.0}
                    ],
                },
            ],
        }
        txs = _flatten(result, kind="bank")
        assert len(txs) == 2
        assert {tx.description for tx in txs} == {"TX1", "TX2"}

    def test_empty_result_returns_empty_list(self) -> None:
        """No accounts = no transactions."""
        result = {"success": True, "accounts": []}
        txs = _flatten(result, kind="bank")
        assert txs == []

    def test_missing_txns_array_is_safe(self) -> None:
        """Account without 'txns' key doesn't crash."""
        result = {
            "success": True,
            "accounts": [
                {
                    "accountNumber": "ACC1",
                    "balance": 10000.0,
                    # no 'txns' key
                }
            ],
        }
        txs = _flatten(result, kind="bank")
        assert txs == []

    def test_skips_invalid_transactions(self) -> None:
        """Transactions without date are silently skipped."""
        result = {
            "success": True,
            "accounts": [
                {
                    "accountNumber": "ACC1",
                    "balance": 10000.0,
                    "txns": [
                        {"description": "No date", "chargedAmount": -100.0},  # missing date
                        {"date": "2026-05-15T00:00:00.000Z", "description": "Valid", "chargedAmount": -200.0},
                    ],
                }
            ],
        }
        txs = _flatten(result, kind="bank")
        assert len(txs) == 1
        assert txs[0].description == "Valid"


class TestDateParsing:
    """Test that we correctly parse Israeli-bank-scrapers date format."""

    def test_iso8601_with_z(self) -> None:
        """Parse 'YYYY-MM-DDTHH:MM:SS.sssZ' (common Israeli bank format)."""
        raw = {
            "date": "2026-05-15T14:30:45.000Z",
            "description": "Test",
            "chargedAmount": -100.0,
        }
        tx = _to_transaction(raw, kind="bank", account_balance=None)
        assert tx is not None
        assert tx.date == datetime(2026, 5, 15, 14, 30, 45)

    def test_fallback_to_processedDate(self) -> None:
        """If 'date' is missing, try 'processedDate'."""
        raw = {
            "processedDate": "2026-05-15T00:00:00.000Z",
            "description": "Test",
            "chargedAmount": -100.0,
        }
        tx = _to_transaction(raw, kind="bank", account_balance=None)
        assert tx is not None
        assert tx.date.date().isoformat() == "2026-05-15"


class TestIntegration:
    """End-to-end conversion test with realistic Israeli bank data."""

    def test_hapoalim_like_response(self) -> None:
        """Simulate a response from Bank Hapoalim (bank transactions)."""
        result = {
            "success": True,
            "accounts": [
                {
                    "accountNumber": "12-345-678901",
                    "balance": 45000.0,
                    "txns": [
                        {
                            "date": "2026-05-15T00:00:00.000Z",
                            "description": "העברה דיגיטל",
                            "chargedAmount": -4500.0,  # rent
                            "identifier": "HB-2026-05-15-001",
                        },
                        {
                            "date": "2026-05-14T00:00:00.000Z",
                            "description": "משכורת",
                            "chargedAmount": 8000.0,  # salary
                            "identifier": "HB-2026-05-14-001",
                        },
                    ],
                }
            ],
        }
        txs = _flatten(result, kind="bank")
        assert len(txs) == 2

        rent = next(tx for tx in txs if tx.description == "העברה דיגיטל")
        assert rent.debit == 4500.0
        assert rent.credit == 0.0
        assert rent.source == "bank"
        assert rent.balance == 45000.0

        salary = next(tx for tx in txs if tx.description == "משכורת")
        assert salary.debit == 0.0
        assert salary.credit == 8000.0

    def test_isracard_like_response(self) -> None:
        """Simulate a response from Isracard (card transactions)."""
        result = {
            "success": True,
            "accounts": [
                {
                    "accountNumber": "4571-5678-1234-5678",
                    "balance": 0.0,  # cards don't have balance like bank accounts
                    "txns": [
                        {
                            "date": "2026-05-15T00:00:00.000Z",
                            "description": "SUPER PHARM TEL AVIV",
                            "chargedAmount": -185.50,
                            "identifier": "IC-2026-05-15-001",
                        },
                        {
                            "date": "2026-05-12T00:00:00.000Z",
                            "description": "AMAZON.COM *PURCHASE",
                            "chargedAmount": -299.99,
                            "identifier": "IC-2026-05-12-001",
                        },
                    ],
                }
            ],
        }
        txs = _flatten(result, kind="credit_card")
        assert len(txs) == 2
        assert all(tx.source == "credit_card" for tx in txs)
        assert all(tx.debit > 0 for tx in txs)  # all charges
        assert all(tx.credit == 0 for tx in txs)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
