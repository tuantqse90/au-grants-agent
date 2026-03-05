"""Live crawler for grants.gov.au (GrantConnect).

GrantConnect uses div.listInner cards with div.list-desc label/value pairs.
Pagination via ?page=N query parameter.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Optional
from urllib.parse import urljoin

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


class GrantsGovCrawler(BaseCrawler):
    """Crawler for https://www.grants.gov.au (GrantConnect)."""

    SOURCE_NAME = "grants.gov.au"
    BASE_URL = "https://www.grants.gov.au"
    LIST_URL = "https://www.grants.gov.au/Go/List"
    MAX_PAGES = 10

    async def _get_client(self) -> httpx.AsyncClient:
        """Override to use browser-like headers."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                headers=BROWSER_HEADERS,
                follow_redirects=True,
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self.client

    def _parse_list_desc(self, card) -> dict:
        """Parse a div.listInner card into a grant dict.

        Each card contains multiple div.list-desc blocks:
          <div class="list-desc">
            <span>Label:</span>
            <div class="list-desc-inner">Value</div>
          </div>
        """
        data: dict = {}
        descs = card.find_all("div", class_="list-desc")

        for desc in descs:
            label_el = desc.find("span")
            value_el = desc.find("div", class_="list-desc-inner")
            if not label_el or not value_el:
                continue

            label = label_el.get_text().strip().rstrip(":").strip()
            label_lower = label.lower()

            if label_lower == "go id":
                link = value_el.find("a")
                if link:
                    data["go_id"] = clean_text(link.get_text())
                    href = link.get("href", "")
                    if href:
                        data["detail_url"] = urljoin(self.BASE_URL, href)

            elif "close date" in label_lower:
                raw = value_el.get_text().strip()
                # Format: "11-Mar-2026 2:00 pm  (ACT Local Time)"
                raw = re.sub(r"\(.*?\)", "", raw).strip()
                data["closing_date"] = self._parse_au_date(raw)

            elif label_lower == "agency":
                data["agency"] = clean_text(value_el.get_text())

            elif "category" in label_lower:
                cat_text = clean_text(value_el.get_text())
                # Strip numeric prefix like "231015 - Mental Health"
                if cat_text:
                    cat_text = re.sub(r"^\d+\s*-\s*", "", cat_text)
                    data["category"] = cat_text

            elif label_lower == "description":
                data["description"] = clean_text(value_el.get_text())

            elif not label.strip():
                # "Full Details" link
                link = value_el.find("a", class_="detail")
                if link and link.get("href"):
                    data["detail_url"] = urljoin(self.BASE_URL, link["href"])
                    # Title from the link's title attribute
                    title_attr = link.get("title", "")
                    if title_attr.startswith("Full Details for "):
                        data["title"] = title_attr[len("Full Details for "):]

        return data

    def _parse_au_date(self, text: str) -> Optional[str]:
        """Parse Australian date format like '11-Mar-2026 2:00 pm' to ISO."""
        if not text:
            return None
        months = {
            "jan": "01", "feb": "02", "mar": "03", "apr": "04",
            "may": "05", "jun": "06", "jul": "07", "aug": "08",
            "sep": "09", "oct": "10", "nov": "11", "dec": "12",
        }
        m = re.search(r"(\d{1,2})-(\w{3})-(\d{4})", text)
        if m:
            day = m.group(1).zfill(2)
            month = months.get(m.group(2).lower(), "01")
            year = m.group(3)
            return f"{year}-{month}-{day}"
        # Fallback to generic parser
        return extract_date(text)

    async def parse_listing(self, html: str) -> list[dict]:
        """Parse the grants listing page for grant card entries."""
        soup = get_soup(html)
        grants_data = []

        cards = soup.select("div.listInner")
        if not cards:
            logger.warning("No div.listInner cards found on listing page")
            return grants_data

        for card in cards:
            data = self._parse_list_desc(card)
            if data.get("go_id") or data.get("title"):
                grants_data.append(data)

        return grants_data

    async def parse_detail(self, url: str, html: str) -> dict:
        """Parse a grant detail page for full information."""
        soup = get_soup(html)
        data: dict = {"source_url": url, "raw_html": html}

        # Title from h1 — strip "Current Grant Opportunity View - " prefix
        h1 = soup.select_one("h1")
        if h1:
            title = clean_text(h1.get_text())
            if title:
                title = re.sub(
                    r"^Current Grant Opportunity View\s*-\s*",
                    "",
                    title,
                )
                # GO ID in title is not the real title, we get it from Full Details link
                if not title.startswith("GO"):
                    data["title"] = title

        # Parse list-desc fields on detail page
        for desc in soup.find_all("div", class_="list-desc"):
            label_el = desc.find("span")
            value_el = desc.find("div", class_="list-desc-inner")
            if not label_el or not value_el:
                continue

            label = label_el.get_text().strip().rstrip(":").strip().lower()
            value = value_el.get_text().strip()

            if label == "go id":
                data["go_id"] = clean_text(value)

            elif label == "agency":
                data["agency"] = clean_text(value)

            elif "close date" in label:
                raw = re.sub(r"\(.*?\)", "", value).strip()
                data["closing_date"] = self._parse_au_date(raw)

            elif "category" in label:
                cat = clean_text(value)
                if cat:
                    cat = re.sub(r"^\d+\s*-\s*", "", cat)
                    data["category"] = cat

            elif label == "description":
                data["description"] = clean_text(value)[:2000]

            elif "eligib" in label:
                data["eligibility"] = clean_text(value)[:1500]

            elif "total amount" in label or "amount" in label:
                amt_min, amt_max = extract_amount_range(value)
                if amt_min is not None:
                    data["amount_min"] = amt_min
                    data["amount_max"] = amt_max

            elif label == "location":
                data["location"] = clean_text(value)

            elif "selection" in label:
                data["selection_process"] = clean_text(value)

        return data

    async def crawl(
        self, dry_run: bool = False, category: Optional[str] = None
    ) -> CrawlResult:
        """Execute the full grants.gov.au crawl with pagination."""
        start = time.time()
        result = CrawlResult(source=self.SOURCE_NAME)
        all_grants: list[Grant] = []
        seen_go_ids: set[str] = set()

        try:
            for page in range(1, self.MAX_PAGES + 1):
                url = self.LIST_URL if page == 1 else f"{self.LIST_URL}?page={page}"
                logger.info("[%s] Fetching page %d: %s", self.SOURCE_NAME, page, url)

                html = await self.fetch(url)
                if not html:
                    logger.warning("Failed to fetch page %d", page)
                    break

                raw_grants = await self.parse_listing(html)
                if not raw_grants:
                    logger.info("No more grants on page %d, stopping", page)
                    break

                logger.info("Page %d: found %d grant entries", page, len(raw_grants))

                for raw in raw_grants:
                    go_id = raw.get("go_id")
                    if go_id and go_id in seen_go_ids:
                        continue
                    if go_id:
                        seen_go_ids.add(go_id)

                    # Fetch detail page for full info
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

                    # Merge listing + detail data (detail takes priority)
                    merged = {**raw, **detail_data}

                    # Apply category filter
                    if category and merged.get("category"):
                        if category.lower() not in merged["category"].lower():
                            continue

                    title = merged.get("title") or f"Grant {merged.get('go_id', 'Unknown')}"

                    grant = Grant(
                        id=str(uuid.uuid4()),
                        go_id=merged.get("go_id"),
                        title=title,
                        agency=merged.get("agency"),
                        description=merged.get("description"),
                        category=merged.get("category"),
                        amount_min=merged.get("amount_min"),
                        amount_max=merged.get("amount_max"),
                        closing_date=merged.get("closing_date"),
                        eligibility=merged.get("eligibility"),
                        status="Open",
                        source_url=merged.get("detail_url") or merged.get("source_url"),
                        source=self.SOURCE_NAME,
                        raw_html=merged.get("raw_html"),
                    )
                    all_grants.append(grant)
                    logger.info(
                        "  -> %s [%s] %s",
                        grant.go_id or "?",
                        grant.agency or "?",
                        grant.title[:60],
                    )

                await self.rate_limit()

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
