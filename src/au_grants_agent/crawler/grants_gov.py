"""Live crawler for grants.gov.au (GrantConnect).

GrantConnect blocks simple bot User-Agents. Strategy:
1. Use browser-like headers to fetch listing pages
2. Parse grant cards from search results
3. Follow detail links for full info
"""

from __future__ import annotations

import time
import uuid
from typing import Optional
from urllib.parse import urljoin, urlencode

import httpx

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

# Browser-like headers to avoid 403
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Known grant detail URLs as fallback
KNOWN_GRANT_UUIDS = [
    "294278e6-ffba-428a-be0d-acc9fa4dcb5b",  # GO7626
    "85a6106f-7a2e-4574-8c31-90f36d3b5738",  # GO7867
    "cd6c079c-ae01-47b5-8df4-59e38e21f034",  # GO7781
]


class GrantsGovCrawler(BaseCrawler):
    """Crawler for https://www.grants.gov.au"""

    SOURCE_NAME = "grants.gov.au"
    BASE_URL = "https://www.grants.gov.au"
    LIST_URL = "https://www.grants.gov.au/Go/List"

    async def _get_client(self) -> httpx.AsyncClient:
        """Override to use browser-like headers."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                headers=BROWSER_HEADERS,
                follow_redirects=True,
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self.client

    async def parse_listing(self, html: str) -> list[dict]:
        """Parse the grants listing page for grant entries."""
        soup = get_soup(html)
        grants_data = []

        # Try multiple selectors for different page layouts
        selectors = [
            "div.grant-item",
            "div.search-result",
            "tr.grant-row",
            "div.card",
            "article.grant",
            "div.listing-item",
            "div.row div.col",
            "table tbody tr",
        ]

        items = []
        for sel in selectors:
            items = soup.select(sel)
            if items and len(items) > 1:
                logger.debug("Found %d items with selector '%s'", len(items), sel)
                break

        if not items:
            # Fallback: scan all links containing /Go/Show
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                if "/Go/Show" in href:
                    title = clean_text(link.get_text())
                    if title and len(title) > 10:
                        grants_data.append({
                            "title": title,
                            "detail_url": urljoin(self.BASE_URL, href),
                        })

            logger.info("Link scan found %d grant links", len(grants_data))
            return grants_data

        for item in items:
            try:
                data = self._parse_card(item)
                if data and data.get("title"):
                    grants_data.append(data)
            except Exception as e:
                logger.warning("Error parsing grant card: %s", e)

        return grants_data

    def _parse_card(self, card) -> Optional[dict]:
        """Extract data from a grant card/row element."""
        data = {}

        # Find title + link
        for tag in ["h3", "h4", "h2", "a.title", ".grant-title", "td:first-child a", "a"]:
            el = card.select_one(tag)
            if el and clean_text(el.get_text()):
                data["title"] = clean_text(el.get_text())
                link = el if el.name == "a" else el.find("a")
                if link and link.get("href"):
                    data["detail_url"] = urljoin(self.BASE_URL, link["href"])
                break

        # GO ID
        text = card.get_text()
        import re
        go_match = re.search(r"(GO\d{4,6})", text)
        if go_match:
            data["go_id"] = go_match.group(1)

        # Status
        for sel in [".status", ".badge", ".label", ".tag"]:
            el = card.select_one(sel)
            if el:
                data["status"] = clean_text(el.get_text())
                break

        # Closing date from text
        date = extract_date(text)
        if date:
            data["closing_date"] = date

        # Agency
        for sel in [".agency", ".department", "td:nth-child(2)"]:
            el = card.select_one(sel)
            if el:
                agency = clean_text(el.get_text())
                if agency and len(agency) > 3 and agency != data.get("title"):
                    data["agency"] = agency
                    break

        return data if data.get("title") else None

    async def parse_detail(self, url: str, html: str) -> dict:
        """Parse a grant detail page for full information."""
        soup = get_soup(html)
        data: dict = {"source_url": url, "raw_html": html}

        # Title
        h1 = soup.select_one("h1, .grant-title, .page-title")
        if h1:
            data["title"] = clean_text(h1.get_text())

        # GO ID from page
        import re
        text = soup.get_text()
        go_match = re.search(r"(GO\d{4,6})", text)
        if go_match:
            data["go_id"] = go_match.group(1)

        # Description
        desc_el = soup.select_one(
            ".grant-description, .description, .content, article, .main-content, #main-content"
        )
        if desc_el:
            data["description"] = clean_text(desc_el.get_text())[:2000]

        # Scan label-value pairs
        for label in soup.find_all(["th", "dt", "strong", "label", "h3", "h4"]):
            label_text = (label.get_text() or "").lower().strip().rstrip(":")
            sibling = label.find_next(["td", "dd", "span", "p", "div"])
            if not sibling:
                continue
            val = sibling.get_text()

            if any(w in label_text for w in ["amount", "funding", "value"]):
                amt_min, amt_max = extract_amount_range(val)
                if amt_min is not None:
                    data["amount_min"] = amt_min
                    data["amount_max"] = amt_max

            elif "eligib" in label_text:
                data["eligibility"] = clean_text(val)

            elif "clos" in label_text and "date" in label_text:
                data["closing_date"] = extract_date(val)

            elif "category" in label_text or "type" in label_text:
                data["category"] = clean_text(val)

            elif "agency" in label_text or "department" in label_text:
                data["agency"] = clean_text(val)

        return data

    async def _get_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        """Find next page URL from pagination."""
        soup = get_soup(html)
        for sel in ["a.next", "a[rel='next']", "li.next a", ".pagination .active + li a"]:
            link = soup.select_one(sel)
            if link and link.get("href"):
                return urljoin(self.BASE_URL, link["href"])
        return None

    async def crawl(
        self, dry_run: bool = False, category: Optional[str] = None
    ) -> CrawlResult:
        """Execute the full grants.gov.au crawl."""
        start = time.time()
        result = CrawlResult(source=self.SOURCE_NAME)
        all_grants: list[Grant] = []

        try:
            # Try listing page first
            current_url = self.LIST_URL
            page = 1
            max_pages = 10
            listing_worked = False

            while current_url and page <= max_pages:
                logger.info("[%s] Fetching page %d: %s", self.SOURCE_NAME, page, current_url)
                html = await self.fetch(current_url)
                if not html:
                    logger.warning("Failed to fetch listing page %d (likely 403)", page)
                    break

                raw_grants = await self.parse_listing(html)
                if raw_grants:
                    listing_worked = True
                    logger.info("Page %d: found %d grant entries", page, len(raw_grants))

                    for raw in raw_grants:
                        if category and raw.get("category"):
                            if category.lower() not in raw["category"].lower():
                                continue

                        detail_url = raw.get("detail_url")
                        detail_data = {}
                        if detail_url:
                            await self.rate_limit()
                            detail_html = await self.fetch(detail_url)
                            if detail_html:
                                detail_data = await self.parse_detail(detail_url, detail_html)

                        merged = {**raw, **detail_data}
                        grant = Grant(
                            id=str(uuid.uuid4()),
                            go_id=merged.get("go_id"),
                            title=merged.get("title", "Unknown"),
                            agency=merged.get("agency"),
                            description=merged.get("description"),
                            category=merged.get("category"),
                            amount_min=merged.get("amount_min"),
                            amount_max=merged.get("amount_max"),
                            closing_date=merged.get("closing_date"),
                            eligibility=merged.get("eligibility"),
                            status=merged.get("status", "Open"),
                            source_url=merged.get("detail_url") or merged.get("source_url"),
                            source=self.SOURCE_NAME,
                            raw_html=merged.get("raw_html"),
                        )
                        all_grants.append(grant)

                    next_url = await self._get_next_page_url(html, current_url)
                    if next_url and next_url != current_url:
                        current_url = next_url
                        page += 1
                        await self.rate_limit()
                    else:
                        break
                else:
                    break

            # Fallback: crawl known grant UUIDs directly
            if not listing_worked:
                logger.info("Listing page unavailable. Falling back to known grant UUIDs.")
                for go_uuid in KNOWN_GRANT_UUIDS:
                    url = f"{self.BASE_URL}/Go/Show?GoUuid={go_uuid}"
                    logger.info("  Fetching: %s", url)
                    await self.rate_limit()
                    html = await self.fetch(url)
                    if not html:
                        continue

                    try:
                        detail = await self.parse_detail(url, html)
                    except Exception as e:
                        logger.warning("Error parsing %s: %s", url, e)
                        continue

                    if not detail.get("title"):
                        continue

                    grant = Grant(
                        id=str(uuid.uuid4()),
                        go_id=detail.get("go_id"),
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
                    logger.info("  -> %s", grant.title)

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
