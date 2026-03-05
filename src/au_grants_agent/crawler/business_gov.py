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
    "/grants-and-programs/boosting-female-founders-initiative",
    "/grants-and-programs/accelerating-commercialisation",
    "/grants-and-programs/innovation-connections",
    "/grants-and-programs/supply-chain-resilience-initiative",
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
        import re as _re

        soup = get_soup(html)
        data: dict = {"source_url": url, "raw_html": html}
        full_text = soup.get_text()

        # ── Title ──
        h1 = soup.select_one("h1")
        if h1:
            data["title"] = clean_text(h1.get_text())

        # ── Status (from .tag badge) ──
        tag_el = soup.select_one(".tag")
        if tag_el:
            tag_text = clean_text(tag_el.get_text())
            if tag_text:
                data["status"] = tag_text.capitalize()

        # Fallback status from status-indicator class
        if "status" not in data:
            for cls_prefix in ["status-indicator-open", "status-indicator-closed"]:
                indicator = soup.select_one(f".{cls_prefix}")
                if indicator:
                    data["status"] = "Open" if "open" in cls_prefix else "Closed"
                    break

        # ── Closing Date (from #close-date-value) ──
        close_el = soup.select_one("#close-date-value, .date-value")
        if close_el:
            data["closing_date"] = extract_date(close_el.get_text())

        # ── Description (from "About the program" section or meta) ──
        meta_desc = soup.select_one("meta[name='description']")
        if meta_desc and meta_desc.get("content"):
            data["description"] = meta_desc["content"]

        # Enrich with "About the program" section content
        for h in soup.find_all(["h2", "h3"]):
            if "about" in (h.get_text() or "").lower():
                parts = []
                for sib in h.find_next_siblings(["p", "ul", "ol"], limit=5):
                    t = clean_text(sib.get_text())
                    if t:
                        parts.append(t)
                if parts:
                    data["description"] = " ".join(parts)
                break

        # ── Eligibility (from "Who is this for?" / "Eligible entities") ──
        for h in soup.find_all(["h2", "h3"]):
            h_text = (h.get_text() or "").lower()
            if "who is this for" in h_text or "eligible" in h_text:
                parts = []
                for sib in h.find_next_siblings(["p", "ul", "ol"], limit=5):
                    t = clean_text(sib.get_text())
                    if t:
                        parts.append(t)
                    # Stop if we hit another heading
                    if sib.find_next_sibling(["h2", "h3"]) == sib.next_sibling:
                        break
                if parts:
                    data["eligibility"] = " ".join(parts)[:1000]
                break

        # ── Funding Amount (from $ patterns in page text) ──
        if "amount_min" not in data:
            amt_min, amt_max = extract_amount_range(full_text[:15000])
            if amt_min is not None:
                data["amount_min"] = amt_min
                data["amount_max"] = amt_max

        # ── Agency (from dcterms.creator or page title pattern) ──
        meta_creator = soup.select_one("meta[name='dcterms.creator']")
        if meta_creator and meta_creator.get("content", "").strip():
            data["agency"] = meta_creator["content"].strip()

        if "agency" not in data:
            # Try to extract from title like "MRFF 2026..." -> Medical Research Future Fund
            title = data.get("title", "")
            agency_map = {
                "MRFF": "Medical Research Future Fund",
                "ARC": "Australian Research Council",
                "NHMRC": "National Health and Medical Research Council",
                "CRC": "Department of Industry, Science and Resources",
                "EMDG": "Austrade",
                "BRII": "Department of Industry, Science and Resources",
            }
            for prefix, agency in agency_map.items():
                if prefix in title.upper():
                    data["agency"] = agency
                    break

        # Fallback agency from URL slug
        if "agency" not in data:
            data["agency"] = "Australian Government"

        # ── Category (from dcterms.type or page content) ──
        meta_type = soup.select_one("meta[name='dcterms.type']")
        if meta_type and meta_type.get("content", "").strip():
            dtype = meta_type["content"].strip()
            if dtype != "grant page":
                data["category"] = dtype

        if "category" not in data:
            # Infer category from keywords in title/description
            text_check = (data.get("title", "") + " " + data.get("description", "")).lower()
            category_keywords = {
                "Research": ["research", "innovation", "science", "medical", "nhmrc", "arc"],
                "Business": ["business", "entrepreneur", "export", "manufacturing", "trade"],
                "Community": ["community", "heritage", "volunteer", "social", "region"],
                "Infrastructure": ["infrastructure", "building", "construction"],
            }
            for cat, keywords in category_keywords.items():
                if any(kw in text_check for kw in keywords):
                    data["category"] = cat
                    break

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
