"""Dashboard analytics and trend analysis for grant data."""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional

from au_grants_agent.database import Database
from au_grants_agent.utils.logger import get_logger

logger = get_logger()


def get_funding_trends(db: Database) -> dict:
    """Analyze funding trends across sources and categories."""
    grants = db.list_grants()

    # Amount distribution
    amounts = []
    for g in grants:
        if g.amount_max:
            amounts.append(g.amount_max)
        elif g.amount_min:
            amounts.append(g.amount_min)

    amount_buckets = {
        "Under $50K": 0,
        "$50K - $200K": 0,
        "$200K - $500K": 0,
        "$500K - $1M": 0,
        "$1M - $5M": 0,
        "Over $5M": 0,
    }
    for a in amounts:
        if a < 50_000:
            amount_buckets["Under $50K"] += 1
        elif a < 200_000:
            amount_buckets["$50K - $200K"] += 1
        elif a < 500_000:
            amount_buckets["$200K - $500K"] += 1
        elif a < 1_000_000:
            amount_buckets["$500K - $1M"] += 1
        elif a < 5_000_000:
            amount_buckets["$1M - $5M"] += 1
        else:
            amount_buckets["Over $5M"] += 1

    # Status breakdown
    status_counts = Counter(g.status for g in grants)

    # Source breakdown
    source_counts = Counter(g.source for g in grants if g.source)

    # Category breakdown (top 15)
    cat_counts = Counter(g.category for g in grants if g.category)
    top_categories = dict(cat_counts.most_common(15))

    # Agency breakdown (top 15)
    agency_counts = Counter(g.agency for g in grants if g.agency)
    top_agencies = dict(agency_counts.most_common(15))

    return {
        "total_grants": len(grants),
        "grants_with_amounts": len(amounts),
        "amount_distribution": amount_buckets,
        "status_breakdown": dict(status_counts),
        "source_breakdown": dict(source_counts),
        "top_categories": top_categories,
        "top_agencies": top_agencies,
    }


def get_closing_timeline(db: Database, days_ahead: int = 90) -> dict:
    """Analyze grant closing dates over the next N days."""
    grants = db.list_grants(status="open")
    now = datetime.utcnow()
    cutoff = now + timedelta(days=days_ahead)

    # Weekly buckets
    weekly: dict[str, list[dict]] = defaultdict(list)
    overdue = []
    no_date = 0

    for g in grants:
        if not g.closing_date:
            no_date += 1
            continue
        try:
            cd = datetime.fromisoformat(g.closing_date)
        except ValueError:
            no_date += 1
            continue

        if cd < now:
            overdue.append({"title": g.title[:60], "date": g.closing_date, "id": g.id[:8]})
            continue

        if cd > cutoff:
            continue

        # Get week label
        week_start = cd - timedelta(days=cd.weekday())
        week_label = week_start.strftime("%Y-%m-%d")
        weekly[week_label].append({
            "title": g.title[:60],
            "date": g.closing_date,
            "id": g.id[:8],
            "agency": g.agency or "",
        })

    # Summary per week
    weekly_summary = {}
    for week, items in sorted(weekly.items()):
        weekly_summary[week] = {
            "count": len(items),
            "grants": items[:5],  # top 5 per week
        }

    return {
        "days_ahead": days_ahead,
        "total_closing": sum(len(v) for v in weekly.values()),
        "overdue": len(overdue),
        "no_closing_date": no_date,
        "weekly_timeline": weekly_summary,
        "urgent_next_7_days": [
            item for week, items in sorted(weekly.items())
            for item in items
            if datetime.fromisoformat(item["date"]) <= now + timedelta(days=7)
        ],
    }


def get_crawl_history(db: Database, limit: int = 30) -> list[dict]:
    """Get recent crawl history with trends."""
    with db._connect() as conn:
        rows = conn.execute(
            """SELECT source, status, grants_found, grants_new, grants_updated,
                      duration_seconds, error_message, crawled_at
               FROM crawl_logs
               ORDER BY crawled_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    history = []
    for r in rows:
        d = dict(r)
        history.append(d)

    # Aggregate by source
    source_stats: dict[str, dict] = defaultdict(lambda: {
        "total_crawls": 0, "total_found": 0, "total_new": 0,
        "errors": 0, "avg_duration": 0.0, "last_crawl": "",
    })
    for h in history:
        s = source_stats[h["source"]]
        s["total_crawls"] += 1
        s["total_found"] += h["grants_found"] or 0
        s["total_new"] += h["grants_new"] or 0
        if h["status"] != "success":
            s["errors"] += 1
        s["avg_duration"] += h["duration_seconds"] or 0
        if not s["last_crawl"] or h["crawled_at"] > s["last_crawl"]:
            s["last_crawl"] = h["crawled_at"]

    for s in source_stats.values():
        if s["total_crawls"] > 0:
            s["avg_duration"] = round(s["avg_duration"] / s["total_crawls"], 1)

    return {
        "recent_crawls": history[:10],
        "source_stats": dict(source_stats),
    }


def get_full_analytics(db: Database) -> dict:
    """Get comprehensive analytics dashboard data."""
    return {
        "funding_trends": get_funding_trends(db),
        "closing_timeline": get_closing_timeline(db),
        "crawl_history": get_crawl_history(db),
        "generated_at": datetime.utcnow().isoformat(),
    }
