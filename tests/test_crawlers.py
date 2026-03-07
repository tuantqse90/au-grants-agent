"""Tests for crawler classes — parsing logic with mocked HTTP responses."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from au_grants_agent.crawler.grants_gov import GrantsGovCrawler
from au_grants_agent.crawler.nsw_gov import NSWGovCrawler
from au_grants_agent.crawler.arc import ARCCrawler


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.init_db = MagicMock()
    db.upsert_grant = MagicMock(return_value=True)
    db.log_crawl = MagicMock()
    return db


# ── GrantsGovCrawler ──────────────────────────────────────────

GRANTS_GOV_LISTING_HTML = """
<html><body>
<div class="listInner">
  <div class="list-desc">
    <span>GO ID:</span>
    <div class="list-desc-inner"><a href="/Go/Show?GoUuid=abc-123">GO5678</a></div>
  </div>
  <div class="list-desc">
    <span>Agency:</span>
    <div class="list-desc-inner">Department of Education</div>
  </div>
  <div class="list-desc">
    <span>Close Date &amp; Time:</span>
    <div class="list-desc-inner">15-Mar-2026 5:00 pm (ACT Local Time)</div>
  </div>
  <div class="list-desc">
    <span>Category:</span>
    <div class="list-desc-inner">231015 - Education and Training</div>
  </div>
  <div class="list-desc">
    <span>Description:</span>
    <div class="list-desc-inner">Funding for educational programs in rural areas</div>
  </div>
  <div class="list-desc">
    <span></span>
    <div class="list-desc-inner"><a class="detail" href="/Go/Show?GoUuid=abc-123" title="Full Details for Rural Education Grant">Full Details</a></div>
  </div>
</div>
<div class="listInner">
  <div class="list-desc">
    <span>GO ID:</span>
    <div class="list-desc-inner"><a href="/Go/Show?GoUuid=def-456">GO9999</a></div>
  </div>
  <div class="list-desc">
    <span>Agency:</span>
    <div class="list-desc-inner">CSIRO</div>
  </div>
</div>
</body></html>
"""

GRANTS_GOV_DETAIL_HTML = """
<html><body>
<h1>Current Grant Opportunity View - Rural Education Grant</h1>
<div class="list-desc">
  <span>GO ID:</span>
  <div class="list-desc-inner">GO5678</div>
</div>
<div class="list-desc">
  <span>Agency:</span>
  <div class="list-desc-inner">Department of Education</div>
</div>
<div class="list-desc">
  <span>Total Amount:</span>
  <div class="list-desc-inner">$5,000,000</div>
</div>
<div class="list-desc">
  <span>Eligibility:</span>
  <div class="list-desc-inner">Australian registered organisations only</div>
</div>
</body></html>
"""


class TestGrantsGovParseListing:
    @pytest.mark.asyncio
    async def test_parses_cards(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        results = await crawler.parse_listing(GRANTS_GOV_LISTING_HTML)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_extracts_go_id(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        results = await crawler.parse_listing(GRANTS_GOV_LISTING_HTML)
        assert results[0]["go_id"] == "GO5678"
        assert results[1]["go_id"] == "GO9999"

    @pytest.mark.asyncio
    async def test_extracts_agency(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        results = await crawler.parse_listing(GRANTS_GOV_LISTING_HTML)
        assert results[0]["agency"] == "Department of Education"
        assert results[1]["agency"] == "CSIRO"

    @pytest.mark.asyncio
    async def test_extracts_closing_date(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        results = await crawler.parse_listing(GRANTS_GOV_LISTING_HTML)
        assert results[0]["closing_date"] == "2026-03-15"

    @pytest.mark.asyncio
    async def test_strips_category_number(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        results = await crawler.parse_listing(GRANTS_GOV_LISTING_HTML)
        assert results[0]["category"] == "Education and Training"

    @pytest.mark.asyncio
    async def test_extracts_description(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        results = await crawler.parse_listing(GRANTS_GOV_LISTING_HTML)
        assert "educational programs" in results[0]["description"]

    @pytest.mark.asyncio
    async def test_extracts_detail_url(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        results = await crawler.parse_listing(GRANTS_GOV_LISTING_HTML)
        assert "/Go/Show?GoUuid=abc-123" in results[0]["detail_url"]

    @pytest.mark.asyncio
    async def test_extracts_title_from_detail_link(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        results = await crawler.parse_listing(GRANTS_GOV_LISTING_HTML)
        assert results[0]["title"] == "Rural Education Grant"

    @pytest.mark.asyncio
    async def test_empty_html(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        results = await crawler.parse_listing("<html><body></body></html>")
        assert results == []


class TestGrantsGovParseDetail:
    @pytest.mark.asyncio
    async def test_extracts_amount(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        result = await crawler.parse_detail("https://example.com", GRANTS_GOV_DETAIL_HTML)
        assert result["amount_min"] == 5_000_000

    @pytest.mark.asyncio
    async def test_extracts_eligibility(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        result = await crawler.parse_detail("https://example.com", GRANTS_GOV_DETAIL_HTML)
        assert "Australian registered" in result["eligibility"]

    @pytest.mark.asyncio
    async def test_extracts_go_id(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        result = await crawler.parse_detail("https://example.com", GRANTS_GOV_DETAIL_HTML)
        assert result["go_id"] == "GO5678"

    @pytest.mark.asyncio
    async def test_strips_h1_prefix(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        result = await crawler.parse_detail("https://example.com", GRANTS_GOV_DETAIL_HTML)
        # Title should have "Current Grant Opportunity View - " stripped
        assert result.get("title", "").startswith("Rural")

    @pytest.mark.asyncio
    async def test_sets_source_url(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        result = await crawler.parse_detail("https://example.com/grant", GRANTS_GOV_DETAIL_HTML)
        assert result["source_url"] == "https://example.com/grant"


class TestGrantsGovParseAuDate:
    def test_standard_format(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        assert crawler._parse_au_date("11-Mar-2026 2:00 pm") == "2026-03-11"

    def test_all_months(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        assert crawler._parse_au_date("1-Jan-2025") == "2025-01-01"
        assert crawler._parse_au_date("15-Jun-2026") == "2026-06-15"
        assert crawler._parse_au_date("31-Dec-2025") == "2025-12-31"

    def test_none_input(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        assert crawler._parse_au_date(None) is None

    def test_empty_string(self):
        crawler = GrantsGovCrawler(db=MagicMock())
        assert crawler._parse_au_date("") is None


# ── NSWGovCrawler ──────────────────────────────────────────────

class TestNSWGovParseHit:
    def _make_hit(self, **overrides):
        src = {
            "title": ["NSW Innovation Grant"],
            "url": ["/grants/innovation-grant"],
            "field_summary": ["Funding for innovative projects in NSW"],
            "agency_name": ["NSW Department of Innovation"],
            "grant_amount": ["range"],
            "grant_amount_min": [10000],
            "grant_amount_max": [500000],
            "grant_category": ["Innovation", "Technology"],
            "grant_audience": ["Businesses", "Non-profits"],
            "grant_is_ongoing": [False],
            "grant_dates_end": ["2026-06-30T00:00:00Z"],
        }
        src.update(overrides)
        return {"_source": src}

    def test_parses_title(self):
        crawler = NSWGovCrawler(db=MagicMock())
        result = crawler._parse_hit(self._make_hit())
        assert result["title"] == "NSW Innovation Grant"

    def test_parses_source_url(self):
        crawler = NSWGovCrawler(db=MagicMock())
        result = crawler._parse_hit(self._make_hit())
        assert result["source_url"] == "https://www.nsw.gov.au/grants/innovation-grant"

    def test_parses_description(self):
        crawler = NSWGovCrawler(db=MagicMock())
        result = crawler._parse_hit(self._make_hit())
        assert "innovative projects" in result["description"]

    def test_parses_agency(self):
        crawler = NSWGovCrawler(db=MagicMock())
        result = crawler._parse_hit(self._make_hit())
        assert result["agency"] == "NSW Department of Innovation"

    def test_parses_amount_range(self):
        crawler = NSWGovCrawler(db=MagicMock())
        result = crawler._parse_hit(self._make_hit())
        assert result["amount_min"] == 10000
        assert result["amount_max"] == 500000

    def test_parses_single_amount(self):
        crawler = NSWGovCrawler(db=MagicMock())
        result = crawler._parse_hit(self._make_hit(
            grant_amount=["single-figure"],
            grant_amount_single=[75000],
        ))
        assert result["amount_min"] == 75000
        assert result["amount_max"] == 75000

    def test_parses_categories(self):
        crawler = NSWGovCrawler(db=MagicMock())
        result = crawler._parse_hit(self._make_hit())
        assert "Innovation" in result["category"]
        assert "Technology" in result["category"]

    def test_parses_eligibility(self):
        crawler = NSWGovCrawler(db=MagicMock())
        result = crawler._parse_hit(self._make_hit())
        assert "Businesses" in result["eligibility"]

    def test_open_status_with_future_date(self):
        crawler = NSWGovCrawler(db=MagicMock())
        result = crawler._parse_hit(self._make_hit(
            grant_dates_end=["2030-12-31T00:00:00Z"],
        ))
        assert result["status"] == "Open"

    def test_closed_status_with_past_date(self):
        crawler = NSWGovCrawler(db=MagicMock())
        result = crawler._parse_hit(self._make_hit(
            grant_dates_end=["2020-01-01T00:00:00Z"],
        ))
        assert result["status"] == "Closed"

    def test_ongoing_is_open(self):
        crawler = NSWGovCrawler(db=MagicMock())
        result = crawler._parse_hit(self._make_hit(
            grant_is_ongoing=[True],
            grant_dates_end=[],
        ))
        assert result["status"] == "Open"

    def test_no_title_returns_none(self):
        crawler = NSWGovCrawler(db=MagicMock())
        result = crawler._parse_hit(self._make_hit(title=[]))
        assert result is None

    def test_empty_source(self):
        crawler = NSWGovCrawler(db=MagicMock())
        result = crawler._parse_hit({"_source": {"title": []}})
        assert result is None


# ── ARCCrawler ──────────────────────────────────────────────

class TestARCCrawler:
    @pytest.mark.asyncio
    async def test_crawl_parses_api_response(self, mock_db):
        """Test that ARC crawler correctly processes API JSON data."""
        api_response = {
            "meta": {"total-pages": 1, "total-size": 2},
            "data": [
                {
                    "attributes": {
                        "code": "DP240100001",
                        "scheme-name": "Discovery Projects",
                        "grant-summary": "Investigation of quantum computing applications",
                        "current-admin-organisation": "University of Melbourne",
                        "lead-investigator": "Prof Smith",
                        "current-funding-amount": 450000,
                        "grant-status": "Active",
                        "primary-field-of-research": "Quantum Physics",
                        "anticipated-end-date": "2027-12-31",
                    }
                },
                {
                    "attributes": {
                        "code": "LP240200002",
                        "scheme-name": "Linkage Projects",
                        "grant-summary": "AI-driven environmental monitoring",
                        "current-admin-organisation": "UNSW",
                        "lead-investigator": "Dr Jones",
                        "current-funding-amount": 200000,
                        "grant-status": "Completed",
                        "primary-field-of-research": "Environmental Science",
                    }
                },
            ],
        }

        crawler = ARCCrawler(db=mock_db)

        # Mock the HTTP client to return our API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = api_response

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("au_grants_agent.crawler.arc.httpx.AsyncClient", return_value=mock_client):
            with patch.object(crawler, "rate_limit", new_callable=AsyncMock):
                result = await crawler.crawl(dry_run=True)

        assert result.grants_found == 2
        assert result.source == "arc.gov.au"
        assert result.status != "error"

    @pytest.mark.asyncio
    async def test_crawl_empty_response(self, mock_db):
        """Test ARC crawler handles empty API response."""
        api_response = {"meta": {"total-pages": 1, "total-size": 0}, "data": []}

        crawler = ARCCrawler(db=mock_db)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = api_response

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("au_grants_agent.crawler.arc.httpx.AsyncClient", return_value=mock_client):
            result = await crawler.crawl(dry_run=True)

        assert result.grants_found == 0

    @pytest.mark.asyncio
    async def test_crawl_with_category_filter(self, mock_db):
        """Test ARC crawler filters by category."""
        api_response = {
            "meta": {"total-pages": 1, "total-size": 2},
            "data": [
                {
                    "attributes": {
                        "code": "DP240100001",
                        "scheme-name": "Discovery Projects",
                        "grant-summary": "Quantum research",
                        "grant-status": "Active",
                    }
                },
                {
                    "attributes": {
                        "code": "LP240200002",
                        "scheme-name": "Linkage Projects",
                        "grant-summary": "Industry link",
                        "grant-status": "Active",
                    }
                },
            ],
        }

        crawler = ARCCrawler(db=mock_db)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = api_response

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("au_grants_agent.crawler.arc.httpx.AsyncClient", return_value=mock_client):
            result = await crawler.crawl(dry_run=True, category="Discovery")

        assert result.grants_found == 1


# ── GrantsGov full crawl integration ──────────────────────────

class TestGrantsGovCrawl:
    @pytest.mark.asyncio
    async def test_dry_run_does_not_save(self, mock_db):
        crawler = GrantsGovCrawler(db=mock_db)

        async def mock_fetch(url):
            if "page" not in url and "List" in url:
                return GRANTS_GOV_LISTING_HTML
            return None

        with patch.object(crawler, "fetch", side_effect=mock_fetch):
            with patch.object(crawler, "rate_limit", new_callable=AsyncMock):
                result = await crawler.crawl(dry_run=True)

        assert result.grants_found >= 1
        mock_db.upsert_grant.assert_not_called()

    @pytest.mark.asyncio
    async def test_crawl_saves_to_db(self, mock_db):
        crawler = GrantsGovCrawler(db=mock_db)

        async def mock_fetch(url):
            if "List" in url and "page" not in url:
                return GRANTS_GOV_LISTING_HTML
            return None

        with patch.object(crawler, "fetch", side_effect=mock_fetch):
            with patch.object(crawler, "rate_limit", new_callable=AsyncMock):
                result = await crawler.crawl(dry_run=False)

        assert result.grants_found >= 1
        assert mock_db.upsert_grant.called
        mock_db.log_crawl.assert_called_once()

    @pytest.mark.asyncio
    async def test_crawl_handles_fetch_failure(self, mock_db):
        crawler = GrantsGovCrawler(db=mock_db)

        with patch.object(crawler, "fetch", new_callable=AsyncMock, return_value=None):
            result = await crawler.crawl(dry_run=True)

        assert result.grants_found == 0


class TestNSWGovCrawl:
    @pytest.mark.asyncio
    async def test_dry_run_with_mock_api(self, mock_db):
        crawler = NSWGovCrawler(db=mock_db)

        es_response = {
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_source": {
                            "title": ["Test NSW Grant"],
                            "url": ["/test-grant"],
                            "field_summary": ["A test grant"],
                            "agency_name": ["Test Agency"],
                            "grant_amount": ["single-figure"],
                            "grant_amount_single": [50000],
                            "grant_category": ["Test"],
                            "grant_audience": ["Everyone"],
                            "grant_is_ongoing": [True],
                        }
                    }
                ],
            }
        }

        with patch.object(crawler, "_fetch_json", new_callable=AsyncMock, return_value=es_response):
            with patch.object(crawler, "rate_limit", new_callable=AsyncMock):
                result = await crawler.crawl(dry_run=True)

        assert result.grants_found == 1
        assert result.source == "nsw.gov.au"
        mock_db.upsert_grant.assert_not_called()
