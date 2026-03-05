"""Crawler for the National Health and Medical Research Council (NHMRC).

Scrapes the NHMRC find-funding page which uses Drupal-style
`.views-row` cards with `.card-description` containing status, title, and summary.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Optional
from urllib.parse import urljoin

import httpx

from au_grants_agent.crawler.base import BaseCrawler
from au_grants_agent.crawler.parsers import clean_text, get_soup
from au_grants_agent.models import CrawlResult, Grant
from au_grants_agent.utils.logger import get_logger

logger = get_logger()

FIND_FUNDING_URL = "https://www.nhmrc.gov.au/funding/find-funding"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
}


class NHMRCCrawler(BaseCrawler):
    """Crawler for NHMRC funding opportunities."""

    SOURCE_NAME = "nhmrc.gov.au"
    BASE_URL = "https://www.nhmrc.gov.au"

    async def _get_client(self) -> httpx.AsyncClient:
        if self.client is None:
            self.client = httpx.AsyncClient(
                headers=BROWSER_HEADERS,
                follow_redirects=True,
                timeout=httpx.Timeout(120.0, connect=30.0),
            )
        return self.client

    async def fetch(self, url: str) -> Optional[str]:
        """Fetch using sync httpx in a thread — NHMRC has async SSL issues."""
        import asyncio

        def _sync_fetch() -> Optional[str]:
            for attempt in range(1, 4):
                try:
                    resp = httpx.get(
                        url,
                        headers=BROWSER_HEADERS,
                        follow_redirects=True,
                        timeout=90,
                    )
                    resp.raise_for_status()
                    return resp.text
                except Exception as e:
                    logger.warning("Fetch %s failed: %s (attempt %d/3)", url, type(e).__name__, attempt)
                    if attempt < 3:
                        import time
                        time.sleep(3 * attempt)
            return None

        return await asyncio.get_event_loop().run_in_executor(None, _sync_fetch)

    async def parse_listing(self, html: str) -> list[dict]:
        """Parse the NHMRC find-funding page for grant cards."""
        soup = get_soup(html)
        grants_data = []

        rows = soup.select(".views-row")
        if not rows:
            logger.warning("No .views-row cards found on NHMRC listing page")
            return grants_data

        for row in rows:
            desc = row.select_one(".card-description")
            if not desc:
                continue

            data: dict = {}

            # Status (e.g. "Open", "Closed")
            status_el = desc.select_one("p.text-uppercase")
            if status_el:
                data["status"] = clean_text(status_el.get_text())

            # Title and detail URL from h3 > a
            link = desc.select_one("h3 a")
            if link:
                title = clean_text(link.get_text())
                data["title"] = title
                href = link.get("href", "")
                if href:
                    data["detail_url"] = urljoin(self.BASE_URL, href)

                # Extract GO ID from title, e.g. "(GO7968)"
                go_match = re.search(r"\(GO(\d+)\)", title)
                if go_match:
                    data["go_id"] = f"GO{go_match.group(1)}"

            # Description from last <p> (first <p> is the status)
            paragraphs = desc.select("p")
            if len(paragraphs) > 1:
                data["description"] = clean_text(paragraphs[-1].get_text())

            if data.get("title"):
                grants_data.append(data)

        return grants_data

    async def parse_detail(self, url: str, html: str) -> dict:
        """Parse an NHMRC grant detail page for full information."""
        soup = get_soup(html)
        data: dict = {"source_url": url}

        # Summary from field--name-field-summary
        summary_el = soup.select_one(".field--name-field-summary")
        if summary_el:
            data["summary"] = clean_text(summary_el.get_text())

        # Body text from field--name-body
        body_el = soup.select_one(".field--name-body")
        if body_el:
            body_text = clean_text(body_el.get_text())
            data["description"] = body_text[:2000]

            # Try to extract eligibility info from body
            elig_match = re.search(
                r"(?:eligib\w+|who can apply)[\s:]+(.{50,500})",
                body_text, re.IGNORECASE,
            )
            if elig_match:
                data["eligibility"] = elig_match.group(1)[:500]

        return data

    async def crawl(
        self, dry_run: bool = False, category: Optional[str] = None
    ) -> CrawlResult:
        """Crawl NHMRC funding opportunities."""
        start = time.time()
        result = CrawlResult(source=self.SOURCE_NAME)
        all_grants: list[Grant] = []

        try:
            logger.info("[%s] Fetching find-funding page", self.SOURCE_NAME)
            html = await self.fetch(FIND_FUNDING_URL)
            if not html:
                raise RuntimeError("Failed to fetch NHMRC find-funding page")

            raw_grants = await self.parse_listing(html)
            logger.info("[%s] Found %d grant entries", self.SOURCE_NAME, len(raw_grants))

            for raw in raw_grants:
                # Apply category filter
                if category:
                    title_lower = (raw.get("title") or "").lower()
                    desc_lower = (raw.get("description") or "").lower()
                    if category.lower() not in title_lower and category.lower() not in desc_lower:
                        continue

                # Fetch detail page for more info
                detail_url = raw.get("detail_url")
                detail_data = {}
                if detail_url:
                    await self.rate_limit()
                    detail_html = await self.fetch(detail_url)
                    if detail_html:
                        try:
                            detail_data = await self.parse_detail(detail_url, detail_html)
                        except Exception as e:
                            logger.warning("Error parsing detail %s: %s", detail_url, e)

                # Merge listing + detail data
                merged = {**raw, **detail_data}

                # Build description
                description = merged.get("description") or merged.get("summary") or ""

                # Status mapping
                status_text = merged.get("status", "").lower()
                if "open" in status_text:
                    status = "Open"
                elif "closed" in status_text:
                    status = "Closed"
                else:
                    status = "Open"

                # Determine category
                grant_category = "Health Research"
                title = merged.get("title", "")
                if "mrff" in title.lower():
                    grant_category = "MRFF Health Research"
                elif "nhmrc" in title.lower():
                    grant_category = "NHMRC Research"

                grant = Grant(
                    id=str(uuid.uuid4()),
                    go_id=merged.get("go_id"),
                    title=title[:200],
                    agency="National Health and Medical Research Council",
                    description=description[:2000] if description else None,
                    category=grant_category,
                    eligibility=merged.get("eligibility"),
                    status=status,
                    source_url=merged.get("detail_url") or FIND_FUNDING_URL,
                    source=self.SOURCE_NAME,
                )
                all_grants.append(grant)
                logger.info(
                    "  -> %s [%s] %s",
                    grant.go_id or "?",
                    grant.status,
                    grant.title[:60],
                )

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
