"""Scheduled auto-crawl using APScheduler."""

from __future__ import annotations

import asyncio
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from rich.console import Console

from au_grants_agent.config import settings
from au_grants_agent.crawler import ARCCrawler, BusinessGovCrawler, GrantsGovCrawler, NHMRCCrawler
from au_grants_agent.database import Database
from au_grants_agent.utils.logger import get_logger

logger = get_logger()
console = Console()

CRAWLER_CLASSES = [GrantsGovCrawler, BusinessGovCrawler, ARCCrawler, NHMRCCrawler]


def _run_crawl_job() -> None:
    """Run a full crawl of all sources — called by scheduler."""
    logger.info("Scheduled crawl starting at %s", datetime.utcnow().isoformat())
    db = Database()
    db.init_db()

    async def crawl_all():
        for CrawlerClass in CRAWLER_CLASSES:
            crawler = CrawlerClass(db=db)
            try:
                result = await crawler.crawl()
                logger.info(
                    "[%s] %s: found=%d new=%d updated=%d duration=%.1fs",
                    result.status, result.source,
                    result.grants_found, result.grants_new,
                    result.grants_updated, result.duration_seconds,
                )
            except Exception as e:
                logger.error("[%s] Crawl failed: %s", CrawlerClass.SOURCE_NAME, e)

    asyncio.run(crawl_all())
    logger.info("Scheduled crawl completed at %s", datetime.utcnow().isoformat())


def _run_notify_job(profile_name: str | None = None, min_score: float = 0.3) -> None:
    """Check for new matching grants and send notifications."""
    from au_grants_agent.notify import send_digest

    try:
        send_digest(profile_name=profile_name, min_score=min_score)
    except Exception as e:
        logger.error("Notification job failed: %s", e)


def start_scheduler(
    cron_hour: int = 6,
    cron_minute: int = 0,
    notify_profile: str | None = None,
) -> None:
    """Start the APScheduler with daily crawl job.

    Args:
        cron_hour: Hour to run daily crawl (default 6 AM).
        cron_minute: Minute to run.
        notify_profile: If set, also run notification job after crawl.
    """
    scheduler = BlockingScheduler()

    # Daily crawl
    scheduler.add_job(
        _run_crawl_job,
        trigger=CronTrigger(hour=cron_hour, minute=cron_minute),
        id="daily_crawl",
        name="Daily Grant Crawl",
        replace_existing=True,
    )

    # Notification 30 min after crawl
    if notify_profile:
        scheduler.add_job(
            _run_notify_job,
            trigger=CronTrigger(hour=cron_hour, minute=cron_minute + 30),
            id="daily_notify",
            name="Daily Grant Notifications",
            kwargs={"profile_name": notify_profile},
            replace_existing=True,
        )

    console.print(f"[#00ff88]Scheduler started — daily crawl at {cron_hour:02d}:{cron_minute:02d}[/#00ff88]")
    if notify_profile:
        console.print(f"[dim]Notifications for profile: {notify_profile}[/dim]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        console.print("\n[yellow]Scheduler stopped.[/yellow]")
        scheduler.shutdown()
