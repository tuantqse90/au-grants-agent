"""SQLite database CRUD operations."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from au_grants_agent.config import settings
from au_grants_agent.models import CrawlResult, Grant, Proposal
from au_grants_agent.utils.logger import get_logger

logger = get_logger()

SCHEMA = """
CREATE TABLE IF NOT EXISTS grants (
    id TEXT PRIMARY KEY,
    go_id TEXT UNIQUE,
    title TEXT NOT NULL,
    agency TEXT,
    description TEXT,
    category TEXT,
    amount_min REAL,
    amount_max REAL,
    closing_date TEXT,
    eligibility TEXT,
    status TEXT DEFAULT 'Open',
    source_url TEXT,
    source TEXT,
    raw_html TEXT,
    crawled_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    grant_id TEXT REFERENCES grants(id),
    org_name TEXT,
    focus_area TEXT,
    content_en TEXT,
    summary_vi TEXT,
    model TEXT,
    tokens_used INTEGER,
    generated_at TEXT
);

CREATE TABLE IF NOT EXISTS crawl_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    status TEXT,
    grants_found INTEGER,
    grants_new INTEGER,
    grants_updated INTEGER,
    duration_seconds REAL,
    error_message TEXT,
    crawled_at TEXT
);
"""


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or settings.db_path

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def init_db(self) -> None:
        """Create all tables."""
        with self._connect() as conn:
            conn.executescript(SCHEMA)
        logger.info("Database initialized at %s", self.db_path)

    # ── Grant CRUD ──────────────────────────────────────────────

    def upsert_grant(self, grant: Grant) -> bool:
        """Insert or update a grant. Returns True if new, False if updated."""
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM grants WHERE go_id = ? OR (go_id IS NULL AND title = ?)",
                (grant.go_id, grant.title),
            ).fetchone()

            now = datetime.utcnow().isoformat()
            if existing:
                conn.execute(
                    """UPDATE grants SET
                        title=?, agency=?, description=?, category=?,
                        amount_min=?, amount_max=?, closing_date=?, eligibility=?,
                        status=?, source_url=?, source=?, raw_html=?, updated_at=?
                    WHERE id=?""",
                    (
                        grant.title, grant.agency, grant.description, grant.category,
                        grant.amount_min, grant.amount_max, grant.closing_date,
                        grant.eligibility, grant.status, grant.source_url, grant.source,
                        grant.raw_html, now, existing["id"],
                    ),
                )
                return False
            else:
                conn.execute(
                    """INSERT INTO grants
                        (id, go_id, title, agency, description, category,
                         amount_min, amount_max, closing_date, eligibility,
                         status, source_url, source, raw_html, crawled_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        grant.id, grant.go_id, grant.title, grant.agency,
                        grant.description, grant.category, grant.amount_min,
                        grant.amount_max, grant.closing_date, grant.eligibility,
                        grant.status, grant.source_url, grant.source, grant.raw_html,
                        now, now,
                    ),
                )
                return True

    def get_grant(self, grant_id: str) -> Optional[Grant]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM grants WHERE id = ?", (grant_id,)).fetchone()
            if row:
                return Grant(**dict(row))
        return None

    def list_grants(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        sort_by: str = "closing_date",
        closing_soon_days: Optional[int] = None,
    ) -> list[Grant]:
        query = "SELECT * FROM grants WHERE 1=1"
        params: list = []

        if status:
            query += " AND LOWER(status) = LOWER(?)"
            params.append(status)
        if category:
            query += " AND LOWER(category) LIKE LOWER(?)"
            params.append(f"%{category}%")
        if closing_soon_days is not None:
            cutoff = (datetime.utcnow() + timedelta(days=closing_soon_days)).isoformat()
            query += " AND closing_date IS NOT NULL AND closing_date <= ? AND LOWER(status) = 'open'"
            params.append(cutoff)

        query += f" ORDER BY {sort_by} ASC NULLS LAST"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [Grant(**dict(r)) for r in rows]

    def get_grant_count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]

    def get_stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
            open_count = conn.execute(
                "SELECT COUNT(*) FROM grants WHERE LOWER(status)='open'"
            ).fetchone()[0]
            sources = conn.execute(
                "SELECT source, COUNT(*) as cnt FROM grants GROUP BY source"
            ).fetchall()
            categories = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM grants WHERE category IS NOT NULL GROUP BY category ORDER BY cnt DESC LIMIT 10"
            ).fetchall()
            proposals_count = conn.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]
            return {
                "total_grants": total,
                "open_grants": open_count,
                "sources": {r["source"]: r["cnt"] for r in sources},
                "top_categories": {r["category"]: r["cnt"] for r in categories},
                "total_proposals": proposals_count,
            }

    # ── Proposal CRUD ───────────────────────────────────────────

    def save_proposal(self, proposal: Proposal) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO proposals
                    (id, grant_id, org_name, focus_area, content_en, summary_vi,
                     model, tokens_used, generated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    proposal.id, proposal.grant_id, proposal.org_name,
                    proposal.focus_area, proposal.content_en, proposal.summary_vi,
                    proposal.model, proposal.tokens_used, proposal.generated_at,
                ),
            )

    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
            if row:
                return Proposal(**dict(row))
        return None

    # ── Crawl Logs ──────────────────────────────────────────────

    def log_crawl(self, result: CrawlResult) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO crawl_logs
                    (source, status, grants_found, grants_new, grants_updated,
                     duration_seconds, error_message, crawled_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    result.source, result.status, result.grants_found,
                    result.grants_new, result.grants_updated,
                    result.duration_seconds, result.error_message, result.crawled_at,
                ),
            )
