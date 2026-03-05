"""Live crawler for business.gov.au grants.

business.gov.au uses a dynamic search interface — no static listing page.
Strategy: crawl known grant detail pages directly + discover via sitemap patterns.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Optional
from urllib.parse import urljoin

from au_grants_agent.crawler.base import BaseCrawler
from au_grants_agent.crawler.parsers import (
    clean_text,
    extract_amount_range,
    extract_date,
    get_soup,
)
from au_grants_agent.models import CrawlResult, Grant
from au_grants_agent.utils.logger import get_logger

logger = get_logger()

# Known grant program URLs (updated periodically)
KNOWN_GRANT_URLS = [
    "/grants-and-programs/cooperative-research-centres-crc-grants",
    "/grants-and-programs/cooperative-research-centres-projects-crcp-grants",
    "/grants-and-programs/export-market-development-grants-emdg",
    "/grants-and-programs/business-research-and-innovation-initiative",
    "/grants-and-programs/stronger-communities-programme-round-9",
    "/grants-and-programs/business-growth-fund-qld",
    "/grants-and-programs/national-science-week-grants-2026",
    "/grants-and-programs/australian-heritage-grants-2025-2026",
    "/grants-and-programs/mrff-2026-national-critical-research-infrastructure",
    "/grants-and-programs/entrepreneurs-programme",
    "/grants-and-programs/incubator-support-initiative",
    "/grants-and-programs/boosting-female-founders-initiative",
    "/grants-and-programs/accelerating-commercialisation",
    "/grants-and-programs/innovation-connections",
    "/grants-and-programs/supply-chain-resilience-initiative",
    "/grants-and-programs/modern-manufacturing-initiative",
    "/grants-and-programs/regional-recovery-partnerships-program",
    "/grants-and-programs/building-better-regions-fund",
    "/grants-and-programs/community-development-grants-programme",
    "/grants-and-programs/volunteer-grants",
]


class BusinessGovCrawler(BaseCrawler):
    """Crawler for https://business.gov.au/grants-and-programs"""

    SOURCE_NAME = "business.gov.au"
    BASE_URL = "https://business.gov.au"
    LIST_URL = "https://business.gov.au/grants-and-programs"

    async def _discover_grant_urls(self) -> list[str]:
        """Discover grant URLs from the main page + known list."""
        urls = set()

        # Add known URLs
        for path in KNOWN_GRANT_URLS:
            urls.add(urljoin(self.BASE_URL, path))

        # Try to discover more from the listing page
        html = await self.fetch(self.LIST_URL)
        if html:
            soup = get_soup(html)
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "/grants-and-programs/" in href and href.rstrip("/") != "/grants-and-programs":
                    full_url = urljoin(self.BASE_URL, href)
                    # Filter out non-grant links (media files, etc.)
                    if not any(ext in full_url for ext in [".pdf", ".docx", ".xlsx", ".zip"]):
                        urls.add(full_url)

        logger.info("Discovered %d grant URLs to crawl", len(urls))
        return sorted(urls)

    async def parse_listing(self, html: str) -> list[dict]:
        """Not used in new strategy — kept for interface compatibility."""
        return []

    async def parse_detail(self, url: str, html: str) -> dict:
        """Parse a grant detail page from business.gov.au."""
        soup = get_soup(html)
        data: dict = {"source_url": url, "raw_html": html}

        # Title from h1
        h1 = soup.select_one("h1")
        if h1:
            data["title"] = clean_text(h1.get_text())

        # Main content
        content_el = soup.select_one("main, article, .content, #content, .page-content")
        if content_el:
            # Get description from first few paragraphs
            paragraphs = content_el.find_all("p", limit=5)
            desc_parts = [clean_text(p.get_text()) for p in paragraphs if clean_text(p.get_text())]
            if desc_parts:
                data["description"] = " ".join(desc_parts)

        # Scan all text for structured fields
        full_text = soup.get_text()

        # Status detection
        status_keywords = {
            "open": ["applications are open", "now open", "currently open", "apply now"],
            "closed": ["applications are closed", "now closed", "currently closed", "closed to applications"],
            "upcoming": ["opening soon", "not yet open", "applications will open"],
        }
        text_lower = full_text.lower()
        for status, keywords in status_keywords.items():
            if any(kw in text_lower for kw in keywords):
                data["status"] = status.capitalize()
                break

        # Scan label-value pairs
        for el in soup.find_all(["th", "dt", "strong", "h2", "h3", "h4", "b"]):
            label = (el.get_text() or "").lower().strip().rstrip(":")
            sibling = el.find_next(["td", "dd", "span", "p", "div", "ul"])
            if not sibling:
                continue
            val = sibling.get_text()

            if any(w in label for w in ["amount", "funding", "value", "grant size", "how much"]):
                amt_min, amt_max = extract_amount_range(val)
                if amt_min is not None:
                    data["amount_min"] = amt_min
                    data["amount_max"] = amt_max

            elif any(w in label for w in ["eligib", "who can apply", "who is eligible"]):
                data["eligibility"] = clean_text(val)

            elif any(w in label for w in ["closing", "deadline", "close date", "applications close"]):
                data["closing_date"] = extract_date(val)

            elif any(w in label for w in ["category", "type", "industry", "sector"]):
                data["category"] = clean_text(val)

            elif any(w in label for w in ["agency", "department", "administered by"]):
                data["agency"] = clean_text(val)

        # Try to find amounts from full text if not found yet
        if "amount_min" not in data:
            amt_min, amt_max = extract_amount_range(full_text[:3000])
            if amt_min is not None:
                data["amount_min"] = amt_min
                data["amount_max"] = amt_max

        # Try to extract agency from breadcrumb or meta
        if "agency" not in data:
            meta_dept = soup.select_one("meta[name='department'], meta[name='agency']")
            if meta_dept:
                data["agency"] = meta_dept.get("content")

        return data

    async def crawl(
        self, dry_run: bool = False, category: Optional[str] = None
    ) -> CrawlResult:
        """Crawl business.gov.au grant detail pages directly."""
        start = time.time()
        result = CrawlResult(source=self.SOURCE_NAME)
        all_grants: list[Grant] = []

        try:
            grant_urls = await self._discover_grant_urls()

            for i, url in enumerate(grant_urls, 1):
                logger.info("[%s] (%d/%d) Fetching: %s", self.SOURCE_NAME, i, len(grant_urls), url)
                await self.rate_limit()

                html = await self.fetch(url)
                if not html:
                    logger.warning("Failed to fetch %s, skipping", url)
                    continue

                try:
                    detail = await self.parse_detail(url, html)
                except Exception as e:
                    logger.warning("Error parsing %s: %s", url, e)
                    continue

                if not detail.get("title"):
                    logger.warning("No title found at %s, skipping", url)
                    continue

                if category and detail.get("category"):
                    if category.lower() not in detail["category"].lower():
                        continue

                grant = Grant(
                    id=str(uuid.uuid4()),
                    title=detail.get("title", "Unknown"),
                    agency=detail.get("agency"),
                    description=detail.get("description"),
                    category=detail.get("category"),
                    amount_min=detail.get("amount_min"),
                    amount_max=detail.get("amount_max"),
                    closing_date=detail.get("closing_date"),
                    eligibility=detail.get("eligibility"),
                    status=detail.get("status", "Open"),
                    source_url=url,
                    source=self.SOURCE_NAME,
                    raw_html=detail.get("raw_html"),
                )
                all_grants.append(grant)
                logger.info("  -> %s [%s]", grant.title, grant.status)

            result.grants_found = len(all_grants)

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
