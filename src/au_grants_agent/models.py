"""Pydantic data models for grants, proposals, and crawl results."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Grant(BaseModel):
    """A single government grant opportunity."""

    id: str = Field(description="Internal UUID")
    go_id: Optional[str] = Field(default=None, description="Official GO ID from grants.gov.au")
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
    raw_html: Optional[str] = None
    crawled_at: Optional[str] = None
    updated_at: Optional[str] = None


class Proposal(BaseModel):
    """A generated grant proposal."""

    id: str
    grant_id: str
    org_name: Optional[str] = None
    focus_area: Optional[str] = None
    content_en: Optional[str] = None
    summary_vi: Optional[str] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    generated_at: Optional[str] = None


class CrawlResult(BaseModel):
    """Summary of a single crawl session."""

    source: str
    status: str = "success"
    grants_found: int = 0
    grants_new: int = 0
    grants_updated: int = 0
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    crawled_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
