"""Proposal template library — save, load, and reuse successful proposals as templates.

Templates are stored as YAML files in the templates/ directory.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from au_grants_agent.config import settings
from au_grants_agent.utils.logger import get_logger

logger = get_logger()

TEMPLATES_DIR = Path("templates")


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "_", slug).strip("_")
    return slug[:60]


def save_template(
    name: str,
    content: str,
    category: str = "general",
    grant_type: str = "research",
    description: str = "",
    tags: list[str] | None = None,
    source_grant_title: str = "",
    source_grant_agency: str = "",
) -> Path:
    """Save a proposal as a reusable template.

    Args:
        name: Template name (e.g., "ARC Discovery Standard")
        content: Full proposal text (Markdown)
        category: Grant category (research, business, community)
        grant_type: Specific grant type (discovery, linkage, nhmrc, etc.)
        description: Short description of what this template is good for
        tags: Searchable tags
        source_grant_title: Original grant title this was generated for
        source_grant_agency: Original grant agency
    """
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slugify(name)
    path = TEMPLATES_DIR / f"{slug}.yaml"

    template_data = {
        "name": name,
        "category": category,
        "grant_type": grant_type,
        "description": description,
        "tags": tags or [],
        "source_grant_title": source_grant_title,
        "source_grant_agency": source_grant_agency,
        "created_at": datetime.utcnow().isoformat(),
        "sections": _extract_sections(content),
        "full_content": content,
    }

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(template_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("Template saved: %s", path)
    return path


def _extract_sections(content: str) -> list[dict]:
    """Extract sections from Markdown proposal content."""
    sections = []
    current_title = ""
    current_body: list[str] = []

    for line in content.split("\n"):
        heading_match = re.match(r"^(#{1,3})\s+(.+)", line)
        if heading_match:
            if current_title:
                sections.append({
                    "title": current_title,
                    "body": "\n".join(current_body).strip(),
                })
            current_title = heading_match.group(2).strip()
            current_body = []
        else:
            current_body.append(line)

    if current_title:
        sections.append({
            "title": current_title,
            "body": "\n".join(current_body).strip(),
        })

    return sections


def load_template(name: str) -> dict:
    """Load a template by name or filename.

    Args:
        name: Template name or slug (with or without .yaml extension)

    Returns:
        Template data dict with keys: name, category, grant_type, description,
        tags, sections, full_content, created_at
    """
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    # Try exact filename
    path = TEMPLATES_DIR / name
    if not path.suffix:
        path = path.with_suffix(".yaml")
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    # Try slugified name
    slug = _slugify(name)
    path = TEMPLATES_DIR / f"{slug}.yaml"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    # Search by name field
    for yaml_file in TEMPLATES_DIR.glob("*.yaml"):
        with open(yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if data and data.get("name", "").lower() == name.lower():
                return data

    raise FileNotFoundError(f"Template '{name}' not found in {TEMPLATES_DIR}")


def list_templates(category: Optional[str] = None) -> list[dict]:
    """List all available templates.

    Returns:
        List of dicts with keys: filename, name, category, grant_type, description, tags
    """
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    templates = []

    for yaml_file in sorted(TEMPLATES_DIR.glob("*.yaml")):
        try:
            with open(yaml_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if not data:
                    continue
                if category and data.get("category", "").lower() != category.lower():
                    continue
                templates.append({
                    "filename": yaml_file.name,
                    "name": data.get("name", yaml_file.stem),
                    "category": data.get("category", "general"),
                    "grant_type": data.get("grant_type", ""),
                    "description": data.get("description", ""),
                    "tags": data.get("tags", []),
                    "sections": len(data.get("sections", [])),
                    "created_at": data.get("created_at", ""),
                })
        except Exception as e:
            logger.warning("Error reading template %s: %s", yaml_file, e)

    return templates


def delete_template(name: str) -> bool:
    """Delete a template by name or filename."""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    path = TEMPLATES_DIR / name
    if not path.suffix:
        path = path.with_suffix(".yaml")
    if path.exists():
        path.unlink()
        return True

    slug = _slugify(name)
    path = TEMPLATES_DIR / f"{slug}.yaml"
    if path.exists():
        path.unlink()
        return True

    return False


def create_example_templates() -> list[Path]:
    """Create example templates for each category."""
    paths = []

    paths.append(save_template(
        name="ARC Discovery Project",
        category="research",
        grant_type="discovery",
        description="Template for ARC Discovery Project proposals — fundamental research",
        tags=["arc", "discovery", "fundamental-research", "phd"],
        content="""# Project Title & Executive Summary

[A compelling title that captures the innovation and significance of the proposed research.]

This project proposes to [brief 2-3 sentence summary]. The research addresses a critical gap in [field] by [approach]. Expected outcomes include [key deliverables].

# Background & Significance

[400 words establishing the research context, citing key Australian and international literature. Demonstrate why this research is timely and nationally significant.]

# Research Questions & Objectives

1. [Specific, measurable research question]
2. [Specific, measurable research question]
3. [Specific, measurable research question]

# Methodology & Research Design

[400 words describing the detailed methodology, including data collection, analysis methods, statistical approach, and ethical considerations.]

# Expected Outcomes & National Benefit

[200 words on anticipated outcomes, KPIs, and how results benefit Australia's research priorities.]

# Work Plan & Milestones

| Phase | Timeline | Activities | Deliverables |
|-------|----------|-----------|--------------|
| 1 | Months 1-6 | [Setup and preliminary work] | [Milestone] |
| 2 | Months 7-12 | [Core research activities] | [Milestone] |
| 3 | Months 13-18 | [Analysis and validation] | [Milestone] |
| 4 | Months 19-24 | [Writing and dissemination] | [Publications, reports] |

# Budget Justification

| Item | Cost | Justification |
|------|------|--------------|
| Personnel | $X | [Role and FTE] |
| Equipment | $X | [Specific equipment needed] |
| Travel | $X | [Fieldwork, conferences] |
| Other | $X | [Consumables, software] |

# Team & Institutional Capability

[Describe the CI team's expertise, track record, and institutional facilities.]

# Risk Assessment & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| [Risk 1] | Medium | High | [Strategy] |
| [Risk 2] | Low | Medium | [Strategy] |

# References

[10-15 key references in APA format]
""",
    ))

    paths.append(save_template(
        name="Business Innovation Grant",
        category="business",
        grant_type="innovation",
        description="Template for business innovation and commercialisation grants",
        tags=["business", "innovation", "commercialisation", "sme"],
        content="""# Project Title & Executive Summary

[Commercial project title emphasising the innovation and market opportunity.]

This project will [brief commercial summary]. The total addressable market is [market size] with projected revenue of [amount] within [timeframe].

# Business Case & Market Opportunity

[400 words on market analysis, competitive landscape, customer validation, and growth potential in Australia.]

# Project Objectives & Deliverables

1. [Specific, measurable commercial objective]
2. [Specific, measurable commercial objective]
3. [Specific, measurable commercial objective]

# Project Plan & Methodology

[400 words on implementation approach, technology/process innovation, development phases.]

# Commercialisation Pathway

[300 words on go-to-market strategy, revenue model, IP protection, and scaling plans.]

# Economic Impact & Job Creation

[200 words on Australian jobs, export potential, supply chain benefits, and regional impact.]

# Work Plan & Milestones

| Phase | Timeline | Activities | Go/No-Go Criteria |
|-------|----------|-----------|-------------------|
| 1 | Months 1-6 | [Development] | [Criteria] |
| 2 | Months 7-12 | [Testing/Pilot] | [Criteria] |
| 3 | Months 13-18 | [Market launch] | [Criteria] |

# Budget Justification

| Item | Grant Funds | Co-contribution | Total |
|------|------------|----------------|-------|
| Personnel | $X | $X | $X |
| Equipment | $X | $X | $X |
| IP/Legal | $X | $X | $X |

# Team & Organisational Capability

[Management team, advisory board, past performance, financials.]

# Risk Assessment & Mitigation

| Risk | Type | Likelihood | Mitigation |
|------|------|-----------|-----------|
| [Risk 1] | Technical | Medium | [Strategy] |
| [Risk 2] | Market | Low | [Strategy] |
""",
    ))

    paths.append(save_template(
        name="Community Development Grant",
        category="community",
        grant_type="community",
        description="Template for community development and social impact grants",
        tags=["community", "social-impact", "regional", "volunteer"],
        content="""# Project Title & Summary

[Project title emphasising community benefit and engagement.]

This project will [brief community impact summary]. It addresses [specific community need] affecting [number] residents in [location].

# Community Need & Context

[400 words establishing the local need with evidence: demographics, consultation outcomes, existing gaps.]

# Project Objectives

1. [Measurable community outcome]
2. [Measurable community outcome]
3. [Measurable community outcome]

# Project Activities & Delivery Plan

[400 words on specific activities, community participation, volunteer involvement.]

# Expected Outcomes & Community Impact

[300 words on social, cultural, environmental benefits with measurable indicators.]

# Stakeholder Engagement & Partnerships

[Partner organisations, letters of support, community co-design evidence.]

# Timeline & Milestones

| Phase | Timeline | Activities | Community Outcomes |
|-------|----------|-----------|-------------------|
| 1 | Months 1-3 | [Setup, consultation] | [Outcome] |
| 2 | Months 4-9 | [Delivery] | [Outcome] |
| 3 | Months 10-12 | [Evaluation] | [Outcome] |

# Budget Justification

| Item | Grant | In-kind | Total |
|------|-------|---------|-------|
| Coordinator | $X | $X | $X |
| Materials | $X | $X | $X |
| Events | $X | $X | $X |

# Organisational Capability & Governance

[Track record, financial management, volunteer base, governance structure.]

# Sustainability Plan

[How benefits continue after grant ends — ongoing funding, partnerships, community ownership.]
""",
    ))

    return paths
