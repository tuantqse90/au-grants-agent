"""Abstract base crawler with shared HTTP client logic, retries, and rate limiting."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from au_grants_agent.config import settings
from au_grants_agent.database import Database
from au_grants_agent.models import CrawlResult, Grant
from au_grants_agent.utils.logger import get_logger

logger = get_logger()


class BaseCrawler(ABC):
    """Abstract base for all grant website crawlers."""

    SOURCE_NAME: str = ""
    BASE_URL: str = ""

    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or Database()
        self.client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self.client is None:
            self.client = httpx.AsyncClient(
                headers={"User-Agent": settings.user_agent},
                follow_redirects=True,
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self.client

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()
            self.client = None

    async def fetch(self, url: str) -> Optional[str]:
        """Fetch a URL with retry and exponential backoff."""
        client = await self._get_client()
        for attempt in range(1, settings.max_retries + 1):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.text
            except httpx.HTTPStatusError as e:
                logger.warning(
                    "HTTP %s for %s (attempt %d/%d)",
                    e.response.status_code, url, attempt, settings.max_retries,
                )
            except httpx.RequestError as e:
                logger.warning(
                    "Request error for %s: %s (attempt %d/%d)",
                    url, e, attempt, settings.max_retries,
                )
            if attempt < settings.max_retries:
                wait = settings.backoff_base ** attempt
                logger.debug("Retrying in %.1fs...", wait)
                await asyncio.sleep(wait)
        logger.error("Failed to fetch %s after %d attempts", url, settings.max_retries)
        return None

    async def rate_limit(self) -> None:
        """Enforce crawl delay between requests."""
        await asyncio.sleep(settings.crawl_delay)

    @abstractmethod
    async def parse_listing(self, html: str) -> list[dict]:
        """Parse a listing page and return raw grant dicts."""
        ...

    @abstractmethod
    async def parse_detail(self, url: str, html: str) -> dict:
        """Parse a grant detail page and return enriched data."""
        ...

    @abstractmethod
    async def crawl(self, dry_run: bool = False, category: Optional[str] = None) -> CrawlResult:
        """Execute the full crawl pipeline."""
        ...

    def save_grants(self, grants: list[Grant]) -> tuple[int, int]:
        """Save grants to DB, return (new_count, updated_count)."""
        new_count = 0
        updated_count = 0
        for grant in grants:
            is_new = self.db.upsert_grant(grant)
            if is_new:
                new_count += 1
            else:
                updated_count += 1
        return new_count, updated_count
