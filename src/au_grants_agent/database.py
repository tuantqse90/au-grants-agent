"""Database CRUD operations with SQLite/PostgreSQL dual backend."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from au_grants_agent.config import settings
from au_grants_agent.models import CrawlResult, Grant, GrantTracking, Proposal
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

CREATE TABLE IF NOT EXISTS grant_tracking (
    id TEXT PRIMARY KEY,
    grant_id TEXT REFERENCES grants(id),
    interest TEXT DEFAULT 'interested',
    notes TEXT,
    priority INTEGER DEFAULT 0,
    deadline_reminder TEXT,
    created_at TEXT,
    updated_at TEXT
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

# PostgreSQL schema (individual statements; SERIAL replaces AUTOINCREMENT)
PG_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS grants (
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
    )""",
    """CREATE TABLE IF NOT EXISTS proposals (
        id TEXT PRIMARY KEY,
        grant_id TEXT REFERENCES grants(id),
        org_name TEXT,
        focus_area TEXT,
        content_en TEXT,
        summary_vi TEXT,
        model TEXT,
        tokens_used INTEGER,
        generated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS grant_tracking (
        id TEXT PRIMARY KEY,
        grant_id TEXT REFERENCES grants(id),
        interest TEXT DEFAULT 'interested',
        notes TEXT,
        priority INTEGER DEFAULT 0,
        deadline_reminder TEXT,
        created_at TEXT,
        updated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS crawl_logs (
        id SERIAL PRIMARY KEY,
        source TEXT,
        status TEXT,
        grants_found INTEGER,
        grants_new INTEGER,
        grants_updated INTEGER,
        duration_seconds REAL,
        error_message TEXT,
        crawled_at TEXT
    )""",
]


# ── PostgreSQL compatibility layer ─────────────────────────────


class _RowProxy(dict):
    """Dict subclass that also supports integer-index access like sqlite3.Row."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _CursorProxy:
    """Wraps a psycopg2 cursor to match the sqlite3 cursor interface."""

    def __init__(self, cursor):
        self._cursor = cursor
        self.rowcount = cursor.rowcount

    def fetchone(self):
        row = self._cursor.fetchone()
        return _RowProxy(row) if row else None

    def fetchall(self):
        return [_RowProxy(r) for r in self._cursor.fetchall()]


class _PgConnectionProxy:
    """Wraps a psycopg2 connection to match the sqlite3 connection interface."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        from psycopg2.extras import RealDictCursor

        sql = sql.replace("?", "%s")
        cur = self._conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        return _CursorProxy(cur)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()
        return False


class Database:
    """Database manager with SQLite/PostgreSQL dual backend."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.use_postgres = settings.use_postgres
        self.database_url = settings.database_url if self.use_postgres else ""
        self.db_path = db_path or settings.db_path

    def _connect(self):
        """Return a connection (proxy for PostgreSQL, raw for SQLite)."""
        if self.use_postgres:
            import psycopg2

            conn = psycopg2.connect(self.database_url)
            return _PgConnectionProxy(conn)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def init_db(self) -> None:
        """Create all tables."""
        if self.use_postgres:
            with self._connect() as conn:
                for stmt in PG_SCHEMA:
                    conn.execute(stmt)
            logger.info("Database initialized (PostgreSQL)")
        else:
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

    # ── Grant Tracking ────────────────────────────────────────────

    def track_grant(self, grant_id: str, interest: str = "interested",
                    notes: Optional[str] = None, priority: int = 0) -> GrantTracking:
        """Add or update tracking for a grant."""
        import uuid
        now = datetime.utcnow().isoformat()

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM grant_tracking WHERE grant_id = ?", (grant_id,)
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE grant_tracking SET interest=?, notes=?, priority=?, updated_at=?
                    WHERE grant_id=?""",
                    (interest, notes or existing["notes"], priority, now, grant_id),
                )
                return GrantTracking(
                    id=existing["id"], grant_id=grant_id, interest=interest,
                    notes=notes or existing["notes"], priority=priority,
                    created_at=existing["created_at"], updated_at=now,
                )
            else:
                tracking_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO grant_tracking
                        (id, grant_id, interest, notes, priority, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?)""",
                    (tracking_id, grant_id, interest, notes, priority, now, now),
                )
                return GrantTracking(
                    id=tracking_id, grant_id=grant_id, interest=interest,
                    notes=notes, priority=priority, created_at=now, updated_at=now,
                )

    def untrack_grant(self, grant_id: str) -> bool:
        """Remove tracking for a grant. Returns True if existed."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM grant_tracking WHERE grant_id = ?", (grant_id,)
            )
            return cursor.rowcount > 0

    def get_tracking(self, grant_id: str) -> Optional[GrantTracking]:
        """Get tracking info for a grant."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM grant_tracking WHERE grant_id = ?", (grant_id,)
            ).fetchone()
            if row:
                return GrantTracking(**dict(row))
        return None

    def list_tracked(self, interest: Optional[str] = None) -> list[tuple[GrantTracking, Grant]]:
        """List all tracked grants with their grant details."""
        query = """
            SELECT t.*, g.title, g.agency, g.category, g.closing_date, g.status,
                   g.source_url, g.source, g.go_id, g.description, g.eligibility,
                   g.amount_min, g.amount_max, g.raw_html, g.crawled_at,
                   g.updated_at as g_updated_at
            FROM grant_tracking t
            JOIN grants g ON t.grant_id = g.id
        """
        params: list = []
        if interest:
            query += " WHERE t.interest = ?"
            params.append(interest)
        query += " ORDER BY t.priority DESC, g.closing_date ASC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                tracking = GrantTracking(
                    id=d["id"], grant_id=d["grant_id"], interest=d["interest"],
                    notes=d["notes"], priority=d["priority"],
                    created_at=d["created_at"], updated_at=d["updated_at"],
                )
                grant = Grant(
                    id=d["grant_id"], go_id=d["go_id"], title=d["title"],
                    agency=d["agency"], description=d["description"],
                    category=d["category"], amount_min=d["amount_min"],
                    amount_max=d["amount_max"], closing_date=d["closing_date"],
                    eligibility=d["eligibility"], status=d["status"],
                    source_url=d["source_url"], source=d["source"],
                    raw_html=d["raw_html"], crawled_at=d["crawled_at"],
                    updated_at=d["g_updated_at"],
                )
                results.append((tracking, grant))
            return results

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
