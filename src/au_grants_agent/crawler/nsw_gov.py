"""Crawler for NSW Government grants (nsw.gov.au/grants-and-funding).

Uses the Elasticsearch API at /api/v1/elasticsearch/prod_content/_search
which returns structured JSON with all 1600+ grants.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import Optional

from au_grants_agent.crawler.base import BaseCrawler
from au_grants_agent.models import CrawlResult, Grant
from au_grants_agent.utils.logger import get_logger

logger = get_logger()

BASE_URL = "https://www.nsw.gov.au"
SEARCH_URL = f"{BASE_URL}/api/v1/elasticsearch/prod_content/_search"
PAGE_SIZE = 500  # max results per request


class NSWGovCrawler(BaseCrawler):
    """Crawler for NSW Government grants via Elasticsearch API."""

    SOURCE_NAME = "nsw.gov.au"
    BASE_URL = BASE_URL
    MAX_RESULTS = 2000  # safety cap

    # Fields to request from Elasticsearch
    SOURCE_FIELDS = [
        "title", "url", "nid", "field_summary",
        "grant_amount", "grant_amount_max", "grant_amount_min",
        "grant_amount_single", "grant_audience", "grant_category",
        "grant_dates", "grant_dates_end", "grant_is_ongoing",
        "agency_name",
    ]

    async def _fetch_json(self, body: dict) -> Optional[dict]:
        """POST JSON to Elasticsearch API and return parsed response."""
        client = await self._get_client()
        for attempt in range(1, 4):
            try:
                resp = await client.post(
                    SEARCH_URL,
                    json=body,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                logger.warning(
                    "ES API error (attempt %d/3): %s", attempt, e,
                )
                if attempt < 3:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
        return None

    def _parse_hit(self, hit: dict) -> Optional[dict]:
        """Parse a single Elasticsearch hit into a grant dict."""
        src = hit.get("_source", {})

        # Title (array field)
        title_list = src.get("title", [])
        title = title_list[0] if title_list else None
        if not title:
            return None

        data: dict = {"title": title}

        # URL
        url_list = src.get("url", [])
        if url_list:
            data["source_url"] = f"{BASE_URL}{url_list[0]}"

        # Description
        summary_list = src.get("field_summary", [])
        if summary_list:
            data["description"] = summary_list[0][:2000]

        # Agency
        agency_list = src.get("agency_name", [])
        if agency_list:
            data["agency"] = agency_list[0]

        # Amounts
        amount_type = (src.get("grant_amount", [None]) or [None])[0]
        if amount_type == "single-figure":
            single = src.get("grant_amount_single", [])
            if single:
                data["amount_min"] = single[0]
                data["amount_max"] = single[0]
        else:
            amt_min = src.get("grant_amount_min", [])
            amt_max = src.get("grant_amount_max", [])
            if amt_min:
                data["amount_min"] = amt_min[0]
            if amt_max:
                data["amount_max"] = amt_max[0]

        # Category
        cat_list = src.get("grant_category", [])
        if cat_list:
            data["category"] = ", ".join(cat_list)

        # Audience / eligibility
        aud_list = src.get("grant_audience", [])
        if aud_list:
            data["eligibility"] = ", ".join(aud_list)

        # Status and dates
        is_ongoing = src.get("grant_is_ongoing", [False])
        dates_end = src.get("grant_dates_end", [])
        dates_start = src.get("grant_dates", [])

        if is_ongoing and is_ongoing[0]:
            data["status"] = "Open"
        elif dates_end:
            try:
                end_dt = datetime.fromisoformat(dates_end[0].replace("Z", "+00:00"))
                if end_dt > datetime.now(end_dt.tzinfo):
                    data["status"] = "Open"
                    data["closing_date"] = end_dt.strftime("%Y-%m-%d")
                else:
                    data["status"] = "Closed"
                    data["closing_date"] = end_dt.strftime("%Y-%m-%d")
            except (ValueError, IndexError):
                data["status"] = "Open"
        elif dates_start:
            data["status"] = "Open"
        else:
            data["status"] = "Open"

        return data

    async def parse_listing(self, html: str) -> list[dict]:
        """Not used — this crawler uses the ES API directly."""
        return []

    async def parse_detail(self, url: str, html: str) -> dict:
        """Not used — ES API provides all needed data."""
        return {"source_url": url}

    async def crawl(
        self, dry_run: bool = False, category: Optional[str] = None
    ) -> CrawlResult:
        """Crawl NSW grants via Elasticsearch API."""
        start = time.time()
        result = CrawlResult(source=self.SOURCE_NAME)
        all_grants: list[Grant] = []
        seen_titles: set[str] = set()

        try:
            offset = 0
            total_fetched = 0

            while offset < self.MAX_RESULTS:
                body = {
                    "from": offset,
                    "size": PAGE_SIZE,
                    "query": {
                        "bool": {
                            "must": [{"term": {"type": "grant"}}],
                        }
                    },
                    "_source": self.SOURCE_FIELDS,
                    "sort": [{"utc_changed": {"order": "desc"}}],
                }

                logger.info(
                    "[%s] Fetching grants %d-%d via ES API",
                    self.SOURCE_NAME, offset + 1, offset + PAGE_SIZE,
                )

                data = await self._fetch_json(body)
                if not data:
                    logger.error("Failed to fetch from ES API")
                    break

                hits = data.get("hits", {}).get("hits", [])
                total = data.get("hits", {}).get("total", {})
                if isinstance(total, dict):
                    total_count = total.get("value", 0)
                else:
                    total_count = total

                if offset == 0:
                    logger.info(
                        "[%s] ES API reports %d total grants",
                        self.SOURCE_NAME, total_count,
                    )

                if not hits:
                    logger.info("No more hits at offset %d, stopping", offset)
                    break

                for hit in hits:
                    parsed = self._parse_hit(hit)
                    if not parsed:
                        continue

                    title = parsed["title"]
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)

                    # Category filter
                    if category:
                        grant_text = f"{title} {parsed.get('description', '')} {parsed.get('eligibility', '')}"
                        if category.lower() not in grant_text.lower():
                            continue

                    grant = Grant(
                        id=str(uuid.uuid4()),
                        title=title[:200],
                        agency=parsed.get("agency", "NSW Government"),
                        description=parsed.get("description"),
                        category=parsed.get("category"),
                        amount_min=parsed.get("amount_min"),
                        amount_max=parsed.get("amount_max"),
                        closing_date=parsed.get("closing_date"),
                        eligibility=parsed.get("eligibility"),
                        status=parsed.get("status", "Open"),
                        source_url=parsed.get("source_url"),
                        source=self.SOURCE_NAME,
                    )
                    all_grants.append(grant)

                total_fetched += len(hits)
                offset += PAGE_SIZE

                if total_fetched >= total_count:
                    break

                await self.rate_limit()

            result.grants_found = len(all_grants)
            logger.info("[%s] Found %d grants total", self.SOURCE_NAME, len(all_grants))

            if not dry_run and all_grants:
                new_count, updated_count = self.save_grants(all_grants)
                result.grants_new = new_count
                result.grants_updated = updated_count
            elif dry_run:
                logger.info("[DRY RUN] Would save %d grants", len(all_grants))

        except Exception as e:
            logger.error("[%s] Crawl failed: %s", self.SOURCE_NAME, e)
            result.status = "error"
            result.error_message = str(e)
        finally:
            result.duration_seconds = round(time.time() - start, 2)
            await self.close()
            if not dry_run:
                self.db.log_crawl(result)

        return result
