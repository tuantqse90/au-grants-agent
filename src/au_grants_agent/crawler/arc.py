"""Crawler for the Australian Research Council (ARC) via their JSON API.

ARC DataPortal provides a public JSON API at:
  https://dataportal.arc.gov.au/NCGP/API/grants
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Optional

import httpx

from au_grants_agent.crawler.base import BaseCrawler
from au_grants_agent.models import CrawlResult, Grant
from au_grants_agent.utils.logger import get_logger

logger = get_logger()

API_URL = "https://dataportal.arc.gov.au/NCGP/API/grants"
DETAIL_URL = "https://dataportal.arc.gov.au/NCGP/web/grant/grant/{code}"


class ARCCrawler(BaseCrawler):
    """Crawler for Australian Research Council grants via JSON API."""

    SOURCE_NAME = "arc.gov.au"
    BASE_URL = "https://www.arc.gov.au"

    async def parse_listing(self, html: str) -> list[dict]:
        """Not used — ARC uses JSON API."""
        return []

    async def parse_detail(self, url: str, html: str) -> dict:
        """Not used — data comes from API."""
        return {}

    async def crawl(
        self, dry_run: bool = False, category: Optional[str] = None
    ) -> CrawlResult:
        """Crawl ARC grants via their public JSON API."""
        start = time.time()
        result = CrawlResult(source=self.SOURCE_NAME)
        all_grants: list[Grant] = []

        try:
            async with httpx.AsyncClient(
                headers={"Accept": "application/json"},
                follow_redirects=True,
                timeout=httpx.Timeout(30.0),
            ) as client:
                page = 1
                max_pages = 5  # Each page has 20 items = 100 grants max
                total = 0

                while page <= max_pages:
                    logger.info("[%s] Fetching API page %d", self.SOURCE_NAME, page)
                    resp = await client.get(
                        API_URL, params={"page": page, "pageSize": 20}
                    )

                    if resp.status_code != 200:
                        logger.warning("API returned %d on page %d", resp.status_code, page)
                        break

                    data = resp.json()
                    meta = data.get("meta", {})
                    items = data.get("data", [])

                    if not items:
                        break

                    total_pages = meta.get("total-pages", 1)
                    total = meta.get("total-size", 0)
                    logger.info(
                        "Page %d: %d items (total %d across %d pages)",
                        page, len(items), total, total_pages,
                    )

                    for item in items:
                        attrs = item.get("attributes", {})
                        code = attrs.get("code", "")
                        scheme = attrs.get("scheme-name", "")
                        summary = attrs.get("grant-summary", "")
                        org = attrs.get("current-admin-organisation", "")
                        lead = attrs.get("lead-investigator", "")
                        amount = attrs.get("current-funding-amount")
                        announced_amount = attrs.get("announced-funding-amount")
                        status_text = attrs.get("grant-status", "Active")
                        for_code = attrs.get("primary-field-of-research", "")
                        end_date = attrs.get("anticipated-end-date")
                        year = attrs.get("funding-commencement-year")

                        # Build title
                        title = summary[:120] if summary else f"{scheme} — {code}"
                        if lead:
                            title = f"{scheme}: {lead} — {summary[:80]}" if summary else f"{scheme}: {lead}"

                        # Category from scheme or FoR
                        grant_category = scheme or "Research"
                        if category and category.lower() not in grant_category.lower():
                            continue

                        # Description
                        nit = attrs.get("national-interest-test-statement", "")
                        description = summary
                        if nit:
                            description = f"{summary}\n\nNational Interest: {nit}"

                        # Amount
                        amt = amount or announced_amount
                        amt_min = float(amt) if amt else None
                        amt_max = amt_min

                        # Status mapping
                        status_map = {
                            "Active": "Open",
                            "Approved": "Open",
                            "Announced": "Open",
                            "Completed": "Closed",
                            "Terminated": "Closed",
                        }
                        status = status_map.get(status_text, "Open")

                        grant = Grant(
                            id=str(uuid.uuid4()),
                            go_id=code,
                            title=title[:200],
                            agency="Australian Research Council",
                            description=description[:2000] if description else None,
                            category=grant_category,
                            amount_min=amt_min,
                            amount_max=amt_max,
                            closing_date=end_date,
                            eligibility=f"Administering Organisation: {org}" if org else None,
                            status=status,
                            source_url=DETAIL_URL.format(code=code),
                            source=self.SOURCE_NAME,
                        )
                        all_grants.append(grant)

                    page += 1
                    if page > min(max_pages, total_pages):
                        break

                    await self.rate_limit()

            result.grants_found = len(all_grants)
            logger.info("[%s] Found %d grants from API", self.SOURCE_NAME, len(all_grants))

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
