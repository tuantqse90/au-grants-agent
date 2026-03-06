"""Tests for au_grants_agent.crawler.parsers."""

import pytest

from au_grants_agent.crawler.parsers import (
    clean_text,
    extract_amount_range,
    extract_date,
    get_soup,
    safe_select_text,
)


# ── clean_text ─────────────────────────────────────────────────

class TestCleanText:
    def test_normalizes_whitespace(self):
        assert clean_text("hello   world") == "hello world"

    def test_strips_leading_trailing(self):
        assert clean_text("  hello  ") == "hello"

    def test_newlines_and_tabs(self):
        assert clean_text("hello\n\t  world") == "hello world"

    def test_none_input(self):
        assert clean_text(None) is None

    def test_empty_string(self):
        assert clean_text("") is None

    def test_whitespace_only(self):
        assert clean_text("   \n\t  ") is None

    def test_normal_text(self):
        assert clean_text("Hello World") == "Hello World"


# ── extract_amount_range ──────────────────────────────────────

class TestExtractAmountRange:
    def test_single_amount(self):
        assert extract_amount_range("$500,000") == (500_000, 500_000)

    def test_range(self):
        assert extract_amount_range("$10,000 - $500,000") == (10_000, 500_000)

    def test_million_suffix(self):
        assert extract_amount_range("$3 million") == (3_000_000, 3_000_000)

    def test_m_suffix(self):
        assert extract_amount_range("$5.5m") == (5_500_000, 5_500_000)

    def test_billion_suffix(self):
        assert extract_amount_range("$1.2 billion") == (1_200_000_000, 1_200_000_000)

    def test_k_suffix(self):
        assert extract_amount_range("$500k") == (500_000, 500_000)

    def test_thousand_suffix(self):
        assert extract_amount_range("$250 thousand") == (250_000, 250_000)

    def test_range_with_suffixes(self):
        mn, mx = extract_amount_range("from $1m to $5m")
        assert mn == 1_000_000
        assert mx == 5_000_000

    def test_none_input(self):
        assert extract_amount_range(None) == (None, None)

    def test_no_amounts(self):
        assert extract_amount_range("No funding available") == (None, None)

    def test_decimal_amount(self):
        assert extract_amount_range("$10.5 million") == (10_500_000, 10_500_000)


# ── extract_date ──────────────────────────────────────────────

class TestExtractDate:
    def test_dd_mm_yyyy(self):
        assert extract_date("15/03/2026") == "2026-03-15"

    def test_single_digit_day(self):
        assert extract_date("5/1/2025") == "2025-01-05"

    def test_dd_month_yyyy(self):
        assert extract_date("15 March 2026") == "2026-03-15"

    def test_dd_month_yyyy_case_insensitive(self):
        assert extract_date("1 january 2025") == "2025-01-01"

    def test_iso_format(self):
        assert extract_date("2026-03-15") == "2026-03-15"

    def test_none_input(self):
        assert extract_date(None) is None

    def test_empty_string(self):
        assert extract_date("") is None

    def test_no_date(self):
        assert extract_date("No date specified") is None

    def test_date_in_context(self):
        assert extract_date("Closes on 25 June 2026 at 5pm") == "2026-06-25"

    def test_all_months(self):
        months = [
            ("January", "01"), ("February", "02"), ("March", "03"),
            ("April", "04"), ("May", "05"), ("June", "06"),
            ("July", "07"), ("August", "08"), ("September", "09"),
            ("October", "10"), ("November", "11"), ("December", "12"),
        ]
        for name, num in months:
            assert extract_date(f"1 {name} 2025") == f"2025-{num}-01"


# ── get_soup ──────────────────────────────────────────────────

class TestGetSoup:
    def test_basic_html(self):
        soup = get_soup("<html><body><p>Hello</p></body></html>")
        assert soup.find("p").get_text() == "Hello"

    def test_empty_html(self):
        soup = get_soup("")
        assert soup is not None


# ── safe_select_text ──────────────────────────────────────────

class TestSafeSelectText:
    def test_finds_element(self):
        soup = get_soup('<div><span class="title">Grant Title</span></div>')
        assert safe_select_text(soup, "span.title") == "Grant Title"

    def test_missing_element(self):
        soup = get_soup("<div><p>Hello</p></div>")
        assert safe_select_text(soup, "span.missing") is None

    def test_none_element(self):
        assert safe_select_text(None, "span") is None

    def test_cleans_whitespace(self):
        soup = get_soup('<div><span class="x">  Hello   World  </span></div>')
        assert safe_select_text(soup, "span.x") == "Hello World"
