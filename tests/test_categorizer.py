"""
Tests for categorizer.py
"""

from datetime import datetime

from scripts.importer import Transaction

from israel_bank_analyzer.categorizer import (
    normalize_description,
    canonicalize,
    _match_keywords,
    categorize,
    UNKNOWN_CATEGORY,
)


def make_tx(description: str):

    return Transaction(
        date=datetime(2026, 5, 1),
        description=description,
        reference="0",
        debit=100.0,
        credit=0.0,
        balance=0.0,
    )


class TestNormalizeDescription:

    def test_lowercase(self):
        result = normalize_description("WOLT")
        assert result == "wolt"

    def test_remove_location(self):
        result = normalize_description(
            "AM:PM TEL AVIV"
        )

        assert "tel aviv" not in result

    def test_remove_numbers(self):
        result = normalize_description(
            "AMPM 123"
        )

        assert "123" not in result


class TestCanonicalize:

    def test_ampm_alias(self):
        result = canonicalize(
            "AM:PM DIZENGOFF"
        )

        assert result == "am:pm"

    def test_superpharm_alias(self):
        result = canonicalize(
            "SUPER PHARM"
        )

        assert result == "סופר פארם"


class TestMatchKeywords:

    def test_restaurants(self):
        assert (
            _match_keywords("WOLT")
            == "🍽️ Restaurants & Cafes"
        )

    def test_groceries(self):
        assert (
            _match_keywords("AM:PM TLV")
            == "🍎 Groceries"
        )

    def test_health(self):
        assert (
            _match_keywords("סופר פארם")
            == "🏥 Health & Medical"
        )

    def test_unknown(self):
        assert (
            _match_keywords("חנות xyz")
            is None
        )


class TestCategorize:

    def test_assigns_categories(
        self,
        sample_transactions,
    ):
        result = categorize(sample_transactions)
        categories = [tx.category for tx in result]

        assert "🏥 Health & Medical" in categories
        assert "💰 Income" in categories
        assert "🏦 Bank Fees & Commissions" in categories

    def test_subscriptions_category(self):
        tx = make_tx("Spotify")

        result = categorize([tx])

        assert (
            result[0].category
            == "💳 Subscriptions & Monthly Bills"
        )

    def test_unknown_to_other(
        self,
        sample_transactions,
    ):
        result = categorize(sample_transactions)

        unknown = [
            tx for tx in result
            if tx.description == "חנות לא ידועה"
        ]

        assert unknown[0].category == UNKNOWN_CATEGORY

    def test_returns_same_list(
        self,
        sample_transactions,
    ):
        result = categorize(sample_transactions)

        assert result is sample_transactions