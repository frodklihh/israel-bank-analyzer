"""
Tests for views/html.py
"""
import pytest
from leumi_analyzer.categorizer import categorize
from core.analytics import build_report
from views.html import render_html, save_html_report


class TestRenderHtml:
    def test_returns_string(self, sample_transactions):
        sample_transactions = categorize(sample_transactions)
        report = build_report(sample_transactions, [])
        html = render_html(report)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_contains_period_label(self, sample_transactions):
        sample_transactions = categorize(sample_transactions)
        report = build_report(sample_transactions, [], year=2026, month=5)
        html = render_html(report)
        # Period label is either "05/2026" or contains "2026"
        assert "2026" in html

    def test_contains_amounts(self, sample_transactions):
        sample_transactions = categorize(sample_transactions)
        report = build_report(sample_transactions, [])
        html = render_html(report)
        assert "₪" in html

    def test_by_month_tab_hidden_with_month_filter(self, sample_transactions):
        sample_transactions = categorize(sample_transactions)
        report = build_report(sample_transactions, [], year=2026, month=5)
        html = render_html(report)
        # The "By Month" tab BUTTON should NOT be rendered when filtering a single
        # month. (Match the button markup, not the bare phrase — the latter also
        # lives in the JS i18n dictionary and is always present.)
        assert "📅 By Month</button>" not in html

    def test_by_month_tab_shown_without_month_filter(self, sample_transactions):
        sample_transactions = categorize(sample_transactions)
        report = build_report(sample_transactions, [], year=2026)
        html = render_html(report)
        # The "By Month" tab button should appear when not filtering by month
        assert "📅 By Month</button>" in html

    def test_real_picture_section(self, sample_transactions):
        sample_transactions = categorize(sample_transactions)
        report = build_report(sample_transactions, [])
        html = render_html(report)
        assert "Real picture" in html
        assert "Total Income" in html
        assert "Real Expenses" in html
        assert "Real Net" in html

    def test_account_movement_section(self, sample_transactions):
        sample_transactions = categorize(sample_transactions)
        report = build_report(sample_transactions, [])
        html = render_html(report)
        assert "Account movement" in html
        assert "Opening Balance" in html
        assert "Closing Balance" in html

    def test_pending_section_present_when_pending(self, sample_transactions, sample_card_transactions):
        sample_transactions = categorize(sample_transactions)
        sample_card_transactions = categorize(sample_card_transactions)
        report = build_report(sample_transactions, sample_card_transactions)
        html = render_html(report)
        # Should show pending section since cards exist with no settlements
        assert "Pending" in html

    def test_valid_html_structure(self, sample_transactions):
        sample_transactions = categorize(sample_transactions)
        report = build_report(sample_transactions, [])
        html = render_html(report)
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html


class TestSaveHtmlReport:
    def test_creates_file(self, sample_transactions, tmp_path):
        sample_transactions = categorize(sample_transactions)
        report = build_report(sample_transactions, [])
        output = tmp_path / "report.html"
        save_html_report(report, str(output))
        assert output.exists()

    def test_file_not_empty(self, sample_transactions, tmp_path):
        sample_transactions = categorize(sample_transactions)
        report = build_report(sample_transactions, [])
        output = tmp_path / "report.html"
        save_html_report(report, str(output))
        assert output.stat().st_size > 1000

    def test_creates_parent_dirs(self, sample_transactions, tmp_path):
        sample_transactions = categorize(sample_transactions)
        report = build_report(sample_transactions, [])
        output = tmp_path / "subdir" / "nested" / "report.html"
        save_html_report(report, str(output))
        assert output.exists()