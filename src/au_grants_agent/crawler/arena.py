"""Crawler for ARENA (Australian Renewable Energy Agency).

Scrapes arena.gov.au/funding/ for funding programs.
Uses links with /funding/ prefix and parses detail pages.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Optional
from urllib.parse import urljoin

from au_grants_agent.crawler.base import BaseCrawler
from au_grants_agent.crawler.parsers import clean_text, extract_amount_range, get_soup
from au_grants_agent.models import CrawlResult, Grant
from au_grants_agent.utils.logger import get_logger

logger = get_logger()

FUNDING_URL = "https://arena.gov.au/funding/"
BASE_URL = "https://arena.gov.au"


class ARENACrawler(BaseCrawler):
    """Crawler for ARENA funding programs."""

    SOURCE_NAME = "arena.gov.au"
    BASE_URL = BASE_URL

    async def parse_listing(self, html: str) -> list[dict]:
        """Parse ARENA funding page for program links."""
        soup = get_soup(html)
        grants_data = []
        seen_urls = set()

        # Find all /funding/ links (excluding the main /funding/ page itself)
        for link in soup.find_all("a", href=True):
            href = link["href"]
            full_url = urljoin(BASE_URL, href)

            # Must be an ARENA funding subpage
            if "/funding/" not in href or href.rstrip("/") == "/funding":
                continue
            if full_url in seen_urls:
                continue
            # Skip fragment and anchor links
            if "#" in href:
                continue

            seen_urls.add(full_url)
            title = clean_text(link.get_text())
            if not title or len(title) < 5:
                continue

            # Check for status in surrounding context
            parent = link.find_parent(["li", "div", "section"])
            status = "Open"
            if parent:
                parent_text = parent.get_text().lower()
                if "closed" in parent_text:
                    status = "Closed"
                elif "completed" in parent_text:
                    status = "Closed"

            grants_data.append({
                "title": title,
                "detail_url": full_url,
                "status": status,
            })

        return grants_data

    async def parse_detail(self, url: str, html: str) -> dict:
        """Parse ARENA funding detail page for program information."""
        soup = get_soup(html)
        data: dict = {"source_url": url}

        # Title from h1
        h1 = soup.select_one("h1")
        if h1:
            data["title"] = clean_text(h1.get_text())

        # Content from main article
        content = soup.select_one(".entry-content, article, main")
        if content:
            text = clean_text(content.get_text())
            if text:
                data["description"] = text[:2000]

                # Extract amounts
                amt_min, amt_max = extract_amount_range(text[:500])
                if amt_min:
                    data["amount_min"] = amt_min
                    data["amount_max"] = amt_max

                # Check for status keywords
                text_lower = text.lower()
                if "applications are now closed" in text_lower or "this program is closed" in text_lower:
                    data["status"] = "Closed"
                elif "applications are now open" in text_lower or "apply now" in text_lower:
                    data["status"] = "Open"

                # Try to find closing date
                date_match = re.search(
                    r"(?:close|closing|deadline|due)[^.]*?(\d{1,2}\s+\w+\s+\d{4})",
                    text[:1000], re.IGNORECASE,
                )
                if date_match:
                    from au_grants_agent.crawler.parsers import extract_date
                    data["closing_date"] = extract_date(date_match.group(1))

                # Eligibility
                elig_match = re.search(
                    r"(?:eligib\w+|who can apply|applicants must)[^.]*\.",
                    text[:2000], re.IGNORECASE,
                )
                if elig_match:
                    data["eligibility"] = elig_match.group(0)[:500]

        return data

    async def crawl(
        self, dry_run: bool = False, category: Optional[str] = None
    ) -> CrawlResult:
        """Crawl ARENA funding programs."""
        start = time.time()
        result = CrawlResult(source=self.SOURCE_NAME)
        all_grants: list[Grant] = []

        try:
            logger.info("[%s] Fetching funding page", self.SOURCE_NAME)
            html = await self.fetch(FUNDING_URL)
            if not html:
                raise RuntimeError("Failed to fetch ARENA funding page")

            raw_grants = await self.parse_listing(html)
            logger.info("[%s] Found %d funding program links", self.SOURCE_NAME, len(raw_grants))

            for raw in raw_grants:
                detail_url = raw.get("detail_url")
                detail_data = {}

                if detail_url:
                    await self.rate_limit()
                    detail_html = await self.fetch(detail_url)
                    if detail_html:
                        try:
                            detail_data = await self.parse_detail(detail_url, detail_html)
                        except Exception as e:
                            logger.warning("Error parsing %s: %s", detail_url, e)

                merged = {**raw, **detail_data}

                # Category filter
                if category:
                    text = f"{merged.get('title', '')} {merged.get('description', '')}"
                    if category.lower() not in text.lower():
                        continue

                title = merged.get("title", "Unknown ARENA Program")

                grant = Grant(
                    id=str(uuid.uuid4()),
                    title=title[:200],
                    agency="Australian Renewable Energy Agency",
                    description=merged.get("description"),
                    category="Renewable Energy",
                    amount_min=merged.get("amount_min"),
                    amount_max=merged.get("amount_max"),
                    closing_date=merged.get("closing_date"),
                    eligibility=merged.get("eligibility"),
                    status=merged.get("status", "Open"),
                    source_url=merged.get("detail_url") or FUNDING_URL,
                    source=self.SOURCE_NAME,
                )
                all_grants.append(grant)
                logger.info(
                    "  -> [%s] %s",
                    grant.status,
                    grant.title[:60],
                )

            result.grants_found = len(all_grants)
            logger.info("[%s] Found %d programs total", self.SOURCE_NAME, len(all_grants))

            if not dry_run and all_grants:
                new_count, updated_count = self.save_grants(all_grants)
                result.grants_new = new_count
                result.grants_updated = updated_count
            elif dry_run:
                logger.info("[DRY RUN] Would save %d programs", len(all_grants))

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
