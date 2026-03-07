"""FastAPI REST API for au-grants-agent."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from au_grants_agent.config import settings
from au_grants_agent.database import Database
from au_grants_agent.utils.logger import get_logger

logger = get_logger()

app = FastAPI(
    title="AU Grants Agent API",
    description="API for crawling Australian Government grants and generating proposals",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Database:
    db = Database()
    db.init_db()
    return db


# ── Response Models ──────────────────────────────────────────

class GrantResponse(BaseModel):
    id: str
    go_id: Optional[str] = None
    title: str
    agency: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    closing_date: Optional[str] = None
    eligibility: Optional[str] = None
    status: str = "Open"
    source_url: Optional[str] = None
    source: Optional[str] = None


class StatsResponse(BaseModel):
    total_grants: int
    open_grants: int
    total_proposals: int
    sources: dict[str, int]
    top_categories: dict[str, int]


class CrawlRequest(BaseModel):
    source: Optional[str] = None
    category: Optional[str] = None
    dry_run: bool = False


class CrawlResponse(BaseModel):
    source: str
    status: str
    grants_found: int
    grants_new: int
    grants_updated: int
    duration_seconds: float
    error_message: Optional[str] = None


class TrackRequest(BaseModel):
    interest: str = "interested"
    notes: Optional[str] = None
    priority: int = 0


class TrackResponse(BaseModel):
    id: str
    grant_id: str
    interest: str
    notes: Optional[str] = None
    priority: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MatchRequest(BaseModel):
    profile_name: str
    top_n: int = 10
    min_score: float = 0.1
    status: Optional[str] = None


class MatchResult(BaseModel):
    grant_id: str
    title: str
    agency: Optional[str] = None
    score: float
    rating: str
    reasons: list[str]


class ProposeRequest(BaseModel):
    org_name: Optional[str] = None
    profile_name: Optional[str] = None
    focus_area: Optional[str] = None
    refine: bool = True


class ProposeResponse(BaseModel):
    proposal_id: str
    grant_id: str
    words: int
    model: Optional[str] = None
    tokens_used: Optional[int] = None


class ProposalContentResponse(BaseModel):
    id: str
    grant_id: str
    org_name: Optional[str] = None
    focus_area: Optional[str] = None
    content_en: Optional[str] = None
    summary_vi: Optional[str] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    generated_at: Optional[str] = None


# ── Grant Endpoints ──────────────────────────────────────────

@app.get("/api/grants", response_model=list[GrantResponse], tags=["Grants"])
def list_grants(
    status: Optional[str] = Query(None, description="Filter by status (Open, Closed)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    source: Optional[str] = Query(None, description="Filter by source"),
    closing_soon: Optional[int] = Query(None, description="Closing within N days"),
    sort_by: str = Query("closing_date", description="Sort field"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[GrantResponse]:
    """List grants with optional filters."""
    db = get_db()
    grants = db.list_grants(
        status=status, category=category,
        sort_by=sort_by, closing_soon_days=closing_soon,
    )

    # Source filter (not in DB method)
    if source:
        grants = [g for g in grants if g.source == source]

    # Pagination
    grants = grants[offset:offset + limit]
    return [GrantResponse(**g.model_dump()) for g in grants]


@app.get("/api/grants/{grant_id}", response_model=GrantResponse, tags=["Grants"])
def get_grant(grant_id: str) -> GrantResponse:
    """Get a specific grant by ID (supports partial ID)."""
    db = get_db()
    grant = db.get_grant(grant_id)
    if not grant:
        grants = db.list_grants()
        for g in grants:
            if g.id.startswith(grant_id):
                grant = g
                break
    if not grant:
        raise HTTPException(status_code=404, detail=f"Grant '{grant_id}' not found")
    return GrantResponse(**grant.model_dump())


@app.get("/api/stats", response_model=StatsResponse, tags=["Stats"])
def get_stats() -> StatsResponse:
    """Get summary statistics."""
    db = get_db()
    s = db.get_stats()
    return StatsResponse(**s)


# ── Crawl Endpoints ──────────────────────────────────────────

@app.post("/api/crawl", response_model=list[CrawlResponse], tags=["Crawl"])
def run_crawl(request: CrawlRequest) -> list[CrawlResponse]:
    """Run a crawl for one or all sources."""
    from au_grants_agent.crawler import (
        ARCCrawler, ARENACrawler, BusinessGovCrawler,
        GrantsGovCrawler, NHMRCCrawler, NSWGovCrawler,
    )

    db = get_db()
    source_map = {
        "grants.gov.au": GrantsGovCrawler,
        "business.gov.au": BusinessGovCrawler,
        "arc.gov.au": ARCCrawler,
        "nhmrc.gov.au": NHMRCCrawler,
        "nsw.gov.au": NSWGovCrawler,
        "arena.gov.au": ARENACrawler,
    }

    if request.source:
        if request.source not in source_map:
            raise HTTPException(400, f"Unknown source: {request.source}. Valid: {list(source_map.keys())}")
        crawlers = [source_map[request.source](db=db)]
    else:
        crawlers = [cls(db=db) for cls in source_map.values()]

    async def do_crawl():
        results = []
        for crawler in crawlers:
            result = await crawler.crawl(dry_run=request.dry_run, category=request.category)
            results.append(result)
        return results

    results = asyncio.run(do_crawl())
    return [CrawlResponse(
        source=r.source, status=r.status, grants_found=r.grants_found,
        grants_new=r.grants_new, grants_updated=r.grants_updated,
        duration_seconds=r.duration_seconds, error_message=r.error_message,
    ) for r in results]


# ── Tracking Endpoints ───────────────────────────────────────

@app.post("/api/grants/{grant_id}/track", response_model=TrackResponse, tags=["Tracking"])
def track_grant(grant_id: str, request: TrackRequest) -> TrackResponse:
    """Track a grant with interest status."""
    db = get_db()
    grant = db.get_grant(grant_id)
    if not grant:
        grants = db.list_grants()
        for g in grants:
            if g.id.startswith(grant_id):
                grant = g
                break
    if not grant:
        raise HTTPException(404, f"Grant '{grant_id}' not found")

    tracking = db.track_grant(
        grant.id, interest=request.interest,
        notes=request.notes, priority=request.priority,
    )
    return TrackResponse(**tracking.model_dump())


@app.delete("/api/grants/{grant_id}/track", tags=["Tracking"])
def untrack_grant(grant_id: str) -> dict:
    """Remove tracking for a grant."""
    db = get_db()
    if db.untrack_grant(grant_id):
        return {"status": "removed"}
    raise HTTPException(404, "Grant was not tracked")


@app.get("/api/tracked", response_model=list[dict], tags=["Tracking"])
def list_tracked(
    interest: Optional[str] = Query(None, description="Filter by interest status"),
) -> list[dict]:
    """List all tracked grants."""
    db = get_db()
    db.init_db()
    results = db.list_tracked(interest=interest)
    return [
        {
            "tracking": tracking.model_dump(),
            "grant": GrantResponse(**grant.model_dump()).model_dump(),
        }
        for tracking, grant in results
    ]


# ── Match Endpoints ──────────────────────────────────────────

@app.post("/api/match", response_model=list[MatchResult], tags=["Matching"])
def match_grants(request: MatchRequest) -> list[MatchResult]:
    """Match grants to an organisation profile."""
    from au_grants_agent.proposal.matcher import rank_grants
    from au_grants_agent.proposal.profiles import load_profile

    try:
        profile = load_profile(request.profile_name)
    except FileNotFoundError:
        raise HTTPException(404, f"Profile '{request.profile_name}' not found")

    db = get_db()
    grants = db.list_grants(status=request.status)
    if not grants:
        return []

    results = rank_grants(grants, profile, min_score=request.min_score, top_n=request.top_n)
    return [MatchResult(
        grant_id=m.grant.id,
        title=m.grant.title,
        agency=m.grant.agency,
        score=m.score,
        rating=m.rating,
        reasons=m.reasons,
    ) for m in results]


# ── Propose Endpoints ────────────────────────────────────────

@app.post("/api/grants/{grant_id}/propose", response_model=ProposeResponse, tags=["Proposals"])
def generate_proposal(grant_id: str, request: ProposeRequest) -> ProposeResponse:
    """Generate a proposal for a specific grant."""
    if not settings.has_api_key:
        raise HTTPException(500, "No LLM API key configured")

    db = get_db()
    grant = db.get_grant(grant_id)
    if not grant:
        grants = db.list_grants()
        for g in grants:
            if g.id.startswith(grant_id):
                grant = g
                break
    if not grant:
        raise HTTPException(404, f"Grant '{grant_id}' not found")

    org_profile = None
    if request.profile_name:
        from au_grants_agent.proposal.profiles import load_profile
        try:
            org_profile = load_profile(request.profile_name)
        except FileNotFoundError:
            raise HTTPException(404, f"Profile '{request.profile_name}' not found")

    from au_grants_agent.proposal.generator import ProposalGenerator
    generator = ProposalGenerator(db=db)
    proposal = generator.generate(
        grant=grant,
        org_name=request.org_name,
        focus_area=request.focus_area,
        refine=request.refine,
        org_profile=org_profile,
    )

    word_count = len((proposal.content_en or "").split())
    return ProposeResponse(
        proposal_id=proposal.id,
        grant_id=grant.id,
        words=word_count,
        model=proposal.model,
        tokens_used=proposal.tokens_used,
    )


@app.get("/api/proposals", response_model=list[ProposalContentResponse], tags=["Proposals"])
def list_proposals(
    limit: int = Query(50, ge=1, le=200),
) -> list[ProposalContentResponse]:
    """List all generated proposals (most recent first)."""
    db = get_db()
    proposals = db.list_proposals(limit=limit)
    return [ProposalContentResponse(**p.model_dump()) for p in proposals]


@app.get("/api/proposals/{proposal_id}", response_model=ProposalContentResponse, tags=["Proposals"])
def get_proposal(proposal_id: str) -> ProposalContentResponse:
    """Get full proposal content by ID."""
    db = get_db()
    proposal = db.get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal '{proposal_id}' not found")
    return ProposalContentResponse(**proposal.model_dump())


@app.get("/api/proposals/{proposal_id}/export", tags=["Proposals"])
def export_proposal(
    proposal_id: str,
    format: str = Query("docx", description="Export format: docx or pdf"),
):
    """Export a proposal as DOCX or PDF file."""
    import io
    from au_grants_agent.proposal.exporter import ProposalExporter

    db = get_db()
    proposal = db.get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(404, f"Proposal '{proposal_id}' not found")
    grant = db.get_grant(proposal.grant_id)
    if not grant:
        raise HTTPException(404, f"Grant '{proposal.grant_id}' not found")

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = ProposalExporter(output_dir=Path(tmpdir))
        if format == "pdf":
            filepath = exporter.export_pdf(grant, proposal)
            media_type = "application/pdf"
        elif format == "docx":
            filepath = exporter.export_docx(grant, proposal)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            raise HTTPException(400, f"Unsupported format: {format}. Use 'docx' or 'pdf'.")

        content = filepath.read_bytes()

    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filepath.name}"'},
    )


# ── Template Endpoints ───────────────────────────────────────

@app.get("/api/templates", tags=["Templates"])
def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
) -> list[dict]:
    """List available proposal templates."""
    from au_grants_agent.proposal.template_library import list_templates as _list
    return _list(category=category)


@app.get("/api/templates/{name}", tags=["Templates"])
def get_template(name: str) -> dict:
    """Get a specific template."""
    from au_grants_agent.proposal.template_library import load_template
    try:
        return load_template(name)
    except FileNotFoundError:
        raise HTTPException(404, f"Template '{name}' not found")


# ── Analytics Endpoints ──────────────────────────────────────

@app.get("/api/analytics", tags=["Analytics"])
def get_analytics() -> dict:
    """Get full dashboard analytics."""
    from au_grants_agent.analytics import get_full_analytics
    db = get_db()
    return get_full_analytics(db)


@app.get("/api/analytics/funding", tags=["Analytics"])
def get_funding_trends() -> dict:
    """Get funding amount trends and distributions."""
    from au_grants_agent.analytics import get_funding_trends as _get
    return _get(get_db())


@app.get("/api/analytics/timeline", tags=["Analytics"])
def get_closing_timeline(
    days: int = Query(90, description="Days ahead to analyze"),
) -> dict:
    """Get grant closing date timeline."""
    from au_grants_agent.analytics import get_closing_timeline as _get
    return _get(get_db(), days_ahead=days)


@app.get("/api/analytics/crawls", tags=["Analytics"])
def get_crawl_history(
    limit: int = Query(30, description="Number of recent crawls"),
) -> dict:
    """Get crawl history and source stats."""
    from au_grants_agent.analytics import get_crawl_history as _get
    return _get(get_db(), limit=limit)


# ── Scheduler Endpoints ──────────────────────────────────────

_bg_scheduler = None  # module-level ref for background scheduler


class SchedulerRequest(BaseModel):
    enabled: bool = True
    cron_hour: int = 6
    cron_minute: int = 0
    notify_profile: Optional[str] = None


@app.post("/api/scheduler", tags=["Scheduler"])
def set_scheduler(request: SchedulerRequest) -> dict:
    """Start or stop the background auto-crawl scheduler."""
    global _bg_scheduler

    if not request.enabled:
        if _bg_scheduler:
            _bg_scheduler.shutdown(wait=False)
            _bg_scheduler = None
        return {"status": "stopped"}

    # Start background scheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    if _bg_scheduler:
        _bg_scheduler.shutdown(wait=False)

    _bg_scheduler = BackgroundScheduler()

    from au_grants_agent.scheduler import _run_crawl_job, _run_notify_job
    _bg_scheduler.add_job(
        _run_crawl_job,
        trigger=CronTrigger(hour=request.cron_hour, minute=request.cron_minute),
        id="daily_crawl", name="Daily Grant Crawl", replace_existing=True,
    )

    if request.notify_profile:
        notify_min = (request.cron_minute + 30) % 60
        notify_hr = request.cron_hour + (1 if request.cron_minute + 30 >= 60 else 0)
        _bg_scheduler.add_job(
            _run_notify_job,
            trigger=CronTrigger(hour=notify_hr, minute=notify_min),
            id="daily_notify", name="Daily Notifications",
            kwargs={"profile_name": request.notify_profile},
            replace_existing=True,
        )

    _bg_scheduler.start()
    return {
        "status": "running",
        "schedule": f"{request.cron_hour:02d}:{request.cron_minute:02d} daily",
        "notify_profile": request.notify_profile,
    }


@app.get("/api/scheduler", tags=["Scheduler"])
def get_scheduler_status() -> dict:
    """Get current scheduler status."""
    if _bg_scheduler and _bg_scheduler.running:
        jobs = [{"id": j.id, "name": j.name, "next_run": str(j.next_run_time)} for j in _bg_scheduler.get_jobs()]
        return {"status": "running", "jobs": jobs}
    return {"status": "stopped", "jobs": []}


# ── Email / Notification Endpoints ──────────────────────────

class EmailConfigRequest(BaseModel):
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notify_to: str = ""
    use_tls: bool = True


@app.post("/api/notify/config", tags=["Notifications"])
def set_email_config(request: EmailConfigRequest) -> dict:
    """Update SMTP email settings (runtime only)."""
    import os
    os.environ["SMTP_HOST"] = request.smtp_host
    os.environ["SMTP_PORT"] = str(request.smtp_port)
    os.environ["SMTP_USER"] = request.smtp_user
    if request.smtp_password:
        os.environ["SMTP_PASSWORD"] = request.smtp_password
    os.environ["NOTIFY_TO"] = request.notify_to
    os.environ["SMTP_TLS"] = "true" if request.use_tls else "false"
    return {"status": "updated", "to": request.notify_to}


@app.get("/api/notify/config", tags=["Notifications"])
def get_email_config() -> dict:
    """Get current SMTP config (password masked)."""
    import os
    return {
        "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "smtp_port": int(os.getenv("SMTP_PORT", "587")),
        "smtp_user": os.getenv("SMTP_USER", ""),
        "has_password": bool(os.getenv("SMTP_PASSWORD", "")),
        "notify_to": os.getenv("NOTIFY_TO", ""),
        "use_tls": os.getenv("SMTP_TLS", "true").lower() == "true",
    }


@app.post("/api/notify/test", tags=["Notifications"])
def send_test_email() -> dict:
    """Send a test notification email."""
    from au_grants_agent.notify import send_email
    success = send_email(
        subject="AU Grants Agent — Test Notification",
        html_body="<h2 style='color:#00aa66'>Test successful!</h2><p>Your email notification is configured correctly.</p>",
    )
    if success:
        return {"status": "sent"}
    raise HTTPException(500, "Failed to send email. Check SMTP settings.")


@app.post("/api/notify/digest", tags=["Notifications"])
def send_digest_now(
    profile_name: Optional[str] = Query(None),
    min_score: float = Query(0.3),
) -> dict:
    """Send a grant matching digest email now."""
    from au_grants_agent.notify import send_digest
    success = send_digest(profile_name=profile_name, min_score=min_score)
    if success:
        return {"status": "sent"}
    raise HTTPException(500, "Failed to send digest. Check SMTP settings and profiles.")


# ── Compare Proposals Endpoint ──────────────────────────────

class CompareRequest(BaseModel):
    org_name: Optional[str] = None
    focus_area: Optional[str] = None
    providers: list[str] = ["deepseek", "anthropic"]
    refine: bool = False


class CompareResult(BaseModel):
    provider: str
    model: str
    proposal_id: str
    words: int
    tokens_used: int


@app.post("/api/grants/{grant_id}/compare", response_model=list[CompareResult], tags=["Proposals"])
def compare_proposals(grant_id: str, request: CompareRequest) -> list[CompareResult]:
    """Generate proposals with multiple providers for side-by-side comparison."""
    db = get_db()
    grant = db.get_grant(grant_id)
    if not grant:
        grants = db.list_grants()
        for g in grants:
            if g.id.startswith(grant_id):
                grant = g
                break
    if not grant:
        raise HTTPException(404, f"Grant '{grant_id}' not found")

    results = []
    for provider in request.providers:
        if not settings.get_api_key(provider):
            continue
        try:
            from au_grants_agent.proposal.generator import ProposalGenerator
            gen = ProposalGenerator(db=db, provider=provider)
            proposal = gen.generate(
                grant=grant,
                org_name=request.org_name,
                focus_area=request.focus_area,
                refine=request.refine,
            )
            words = len((proposal.content_en or "").split())
            results.append(CompareResult(
                provider=provider,
                model=proposal.model or "",
                proposal_id=proposal.id,
                words=words,
                tokens_used=proposal.tokens_used or 0,
            ))
        except Exception as e:
            logger.error("Compare failed for %s: %s", provider, e)

    if not results:
        raise HTTPException(500, "No providers could generate. Check API keys.")
    return results


# ── Health ───────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health() -> dict:
    """Health check endpoint."""
    db = get_db()
    count = db.get_grant_count()
    return {
        "status": "healthy",
        "grants_in_db": count,
        "provider": settings.llm_provider,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/", response_class=HTMLResponse, tags=["System"])
def root() -> str:
    """Dashboard UI."""
    from au_grants_agent.dashboard import DASHBOARD_HTML
    return DASHBOARD_HTML
