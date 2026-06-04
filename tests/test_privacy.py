"""test_privacy.py — PII redaction (owner name + national-ID)."""

import pytest

from israel_bank_analyzer.privacy import clean_description, redact_pii, reset_cache
from scripts.importer import Transaction
from datetime import datetime


@pytest.fixture
def names(monkeypatch):
    """Set REDACT_NAMES for a test and clear the cached token list."""
    def _set(value: str) -> None:
        monkeypatch.setenv("REDACT_NAMES", value)
        reset_cache()
    yield _set
    reset_cache()


class TestRedactId:
    """National-ID identifiers are stripped without configuration."""

    def test_strips_mzehe_id(self, names):
        names("")
        assert redact_pii('מופ"ת חובה מזהה 347436107') == 'מופ"ת חובה'

    def test_strips_id_with_no_space(self, names):
        names("")
        assert redact_pii("ישראכרט מזהה350924363") == "ישראכרט"

    def test_keeps_text_without_id(self, names):
        names("")
        assert redact_pii("דקאתלון") == "דקאתלון"


class TestRedactNames:
    """Owner name tokens come from REDACT_NAMES."""

    def test_strips_owner_name(self, names):
        names("פרנקלך,מיכאל")
        assert redact_pii('מופ"ת חובה פרנקלך מיכאל מזהה 347436107') == 'מופ"ת חובה'

    def test_name_order_independent(self, names):
        names("פרנקלך,מיכאל")
        assert redact_pii("משרד הבינוי וה מיכאל פרנקלך מזהה 347436107") == "משרד הבינוי וה"

    def test_does_not_chop_substrings(self, names):
        # A token must match a whole word, never a fragment of another word.
        names("מיכאל")
        assert redact_pii("מיכאלי") == "מיכאלי"

    def test_keeps_counterparty_when_not_listed(self, names):
        names("פרנקלך,מיכאל")
        # A counterparty surname not in the list survives.
        assert redact_pii("העברה גולובטיוק") == "העברה גולובטיוק"

    def test_empty_config_strips_nothing_but_ids(self, names):
        names("")
        assert redact_pii("פרנקלך מיכאל") == "פרנקלך מיכאל"


class TestCleanDescription:
    """Description-only cleaning: order/account refs and Bit normalization."""

    def test_strips_order_number(self, names):
        names("")
        assert clean_description("העב' לאחר-נייד העברה הזמנה 30756966") == "העב' לאחר-נייד העברה"

    def test_strips_account_number(self, names):
        names("")
        assert clean_description("זיכוי מלאומי השלמת שכר 4/26 מח-ן:085070060") == "זיכוי מלאומי השלמת שכר 4/26"

    def test_strips_bare_long_reference(self, names):
        names("")
        # An opaque account code (letter prefix + long digit run) is removed.
        assert "U24190453" not in clean_description("העברה U24190453 לחבר")

    def test_keeps_short_numbers(self, names):
        names("")
        # Card last-4 / internet provider codes are short → preserved.
        assert clean_description("013 נטוויז'ן") == "013 נטוויז'ן"

    def test_collapses_bit_transfer(self, names):
        names("")
        assert clean_description("העברה בBIT") == "BIT"
        assert clean_description("bit העברת כסף משקה האלים") == "BIT"


class TestReferenceFieldPreserved:
    """The reference field keeps opaque transaction ids (only label-anchored
    PII is stripped, not bare digit runs)."""

    def test_reference_keeps_txn_id(self, names):
        names("")
        assert redact_pii("TXN-12345") == "TXN-12345"


class TestTransactionPostInit:
    """Transaction scrubs PII on construction, before categorization/report."""

    def test_description_redacted_on_construction(self, names):
        names("פרנקלך,מיכאל")
        tx = Transaction(
            date=datetime(2026, 5, 1),
            description='מופ"ת חובה פרנקלך מיכאל מזהה 347436107',
            reference="6275010",
            debit=0.0,
            credit=1462.67,
            balance=0.0,
            source="bank",
        )
        assert tx.description == 'מופ"ת חובה'
        assert "347436107" not in tx.description
