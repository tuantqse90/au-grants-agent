"""Post-generation validation for proposals, focusing on reference plausibility."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from au_grants_agent.utils.logger import get_logger

logger = get_logger()


@dataclass
class ReferenceCheck:
    """Result of checking a single reference."""

    raw_text: str
    has_authors: bool = False
    has_year: bool = False
    has_title: bool = False
    has_journal: bool = False
    year_plausible: bool = False
    issues: list[str] = field(default_factory=list)

    @property
    def score(self) -> int:
        """Score out of 5 for reference quality."""
        s = 0
        if self.has_authors:
            s += 1
        if self.has_year:
            s += 1
        if self.has_title:
            s += 1
        if self.has_journal:
            s += 1
        if self.year_plausible:
            s += 1
        return s

    @property
    def is_valid(self) -> bool:
        return self.score >= 3


@dataclass
class ValidationResult:
    """Result of validating a full proposal."""

    total_references: int = 0
    valid_references: int = 0
    issues: list[str] = field(default_factory=list)
    reference_checks: list[ReferenceCheck] = field(default_factory=list)
    has_budget_section: bool = False
    has_methodology: bool = False
    has_timeline: bool = False
    has_risk_section: bool = False
    word_count: int = 0

    @property
    def reference_score(self) -> float:
        """Percentage of valid references."""
        if self.total_references == 0:
            return 0.0
        return (self.valid_references / self.total_references) * 100

    @property
    def completeness_score(self) -> float:
        """Score for proposal completeness (0-100)."""
        checks = [
            self.has_budget_section,
            self.has_methodology,
            self.has_timeline,
            self.has_risk_section,
            self.total_references >= 5,
            self.word_count >= 1500,
        ]
        return (sum(checks) / len(checks)) * 100


# Known real journals for validation
KNOWN_JOURNALS = {
    "nature", "science", "cell", "lancet", "bmj", "pnas",
    "nature biotechnology", "nature genetics", "nature medicine",
    "nature reviews genetics", "nature communications",
    "genome biology", "genome research",
    "bioinformatics", "nucleic acids research",
    "scientific data", "plos one", "plos biology",
    "journal of clinical investigation",
    "medical journal of australia",
    "australian journal",
    "briefings in bioinformatics",
}

# Known Australian government document patterns
AU_GOV_PATTERNS = [
    r"australian government",
    r"department of",
    r"commonwealth of australia",
    r"national health and medical research council",
    r"australian research council",
    r"nhmrc",
    r"arc",
    r"mrff",
]


def _extract_references_section(text: str) -> Optional[str]:
    """Extract the References section from proposal text."""
    # Look for "References" or "10. References" heading
    patterns = [
        r"(?:^|\n)#{1,3}\s*(?:\d+\.\s*)?References?\s*\n([\s\S]*?)(?:\n#{1,3}\s|\Z)",
        r"(?:^|\n)\*\*(?:\d+\.\s*)?References?\*\*\s*\n([\s\S]*?)(?:\n\*\*|\Z)",
        r"(?:^|\n)(?:\d+\.\s*)?References?\s*\n([\s\S]*?)(?:\n\d+\.\s|\Z)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    # Fallback: look for numbered list at the end starting with author-like patterns
    lines = text.strip().split("\n")
    ref_start = None
    for i in range(len(lines) - 1, max(0, len(lines) - 40), -1):
        line = lines[i].strip()
        if re.match(r"^\d+\.\s+[A-Z]", line):
            ref_start = i
        elif ref_start and not line:
            continue
        elif ref_start:
            break

    if ref_start:
        return "\n".join(lines[ref_start:])
    return None


def _parse_individual_references(refs_text: str) -> list[str]:
    """Split references section into individual reference strings."""
    refs = []
    # Try numbered references (1. Author... or 1.  Author...)
    numbered = re.split(r"\n\s*\d+\.\s+", "\n" + refs_text)
    for r in numbered:
        r = r.strip()
        if r and len(r) > 20:
            refs.append(r)

    if not refs:
        # Try bullet points
        for line in refs_text.split("\n"):
            line = line.strip().lstrip("*-•").strip()
            if line and len(line) > 20:
                refs.append(line)

    return refs


def _check_reference(ref_text: str) -> ReferenceCheck:
    """Validate a single reference for plausibility."""
    check = ReferenceCheck(raw_text=ref_text)

    # Check for author pattern (Surname, Initial. or Surname et al.)
    if re.search(r"[A-Z][a-z]+,?\s+[A-Z]\.", ref_text) or "et al" in ref_text:
        check.has_authors = True
    else:
        check.issues.append("No clear author names found")

    # Check for year
    year_match = re.search(r"\(?((?:19|20)\d{2})\)?", ref_text)
    if year_match:
        check.has_year = True
        year = int(year_match.group(1))
        # References should be between 1990 and current year + 1
        if 1990 <= year <= 2027:
            check.year_plausible = True
        else:
            check.issues.append(f"Year {year} seems implausible")
    else:
        check.issues.append("No publication year found")

    # Check for title-like content (italicized or quoted)
    if re.search(r"\*[^*]+\*", ref_text) or len(ref_text) > 50:
        check.has_title = True
    else:
        check.issues.append("No clear title found")

    # Check for journal/source
    ref_lower = ref_text.lower()
    has_journal = False

    # Check known journals
    for journal in KNOWN_JOURNALS:
        if journal in ref_lower:
            has_journal = True
            break

    # Check Australian government documents
    if not has_journal:
        for pattern in AU_GOV_PATTERNS:
            if re.search(pattern, ref_lower):
                has_journal = True
                break

    # Check for italicized journal name pattern
    if not has_journal and re.search(r"\*[A-Z][^*]{5,}\*", ref_text):
        has_journal = True

    # Check for volume/page patterns (common in real refs)
    if not has_journal and re.search(r"\d+\(\d+\)", ref_text):
        has_journal = True

    if has_journal:
        check.has_journal = True
    else:
        check.issues.append("No recognizable journal/source")

    return check


def validate_proposal(content: str) -> ValidationResult:
    """Validate a generated proposal for completeness and reference plausibility.

    Args:
        content: The full English proposal text.

    Returns:
        ValidationResult with scores and issues.
    """
    result = ValidationResult()
    content_lower = content.lower()

    # Word count
    result.word_count = len(content.split())

    # Check for key sections
    result.has_budget_section = any(
        kw in content_lower
        for kw in ["budget justification", "budget item", "total requested", "budget"]
    )
    result.has_methodology = any(
        kw in content_lower
        for kw in ["methodology", "research design", "project plan", "methods"]
    )
    result.has_timeline = any(
        kw in content_lower
        for kw in ["work plan", "milestones", "timeline", "gantt", "months 1"]
    )
    result.has_risk_section = any(
        kw in content_lower
        for kw in ["risk assessment", "risk mitigation", "mitigation strategy"]
    )

    # Extract and validate references
    refs_text = _extract_references_section(content)
    if refs_text:
        individual_refs = _parse_individual_references(refs_text)
        result.total_references = len(individual_refs)

        for ref in individual_refs:
            check = _check_reference(ref)
            result.reference_checks.append(check)
            if check.is_valid:
                result.valid_references += 1
    else:
        result.issues.append("No references section found")

    # Generate summary issues
    if result.word_count < 1000:
        result.issues.append(f"Proposal seems short ({result.word_count} words)")
    if not result.has_budget_section:
        result.issues.append("Missing budget section")
    if not result.has_methodology:
        result.issues.append("Missing methodology section")
    if not result.has_timeline:
        result.issues.append("Missing timeline/milestones")
    if not result.has_risk_section:
        result.issues.append("Missing risk assessment")
    if result.total_references < 5:
        result.issues.append(f"Too few references ({result.total_references})")
    if result.total_references > 0 and result.reference_score < 60:
        result.issues.append(
            f"Reference quality low ({result.reference_score:.0f}% valid)"
        )

    return result


def format_validation_report(result: ValidationResult) -> str:
    """Format a validation result as a readable report."""
    lines = [
        "## Proposal Validation Report",
        "",
        f"**Word Count:** {result.word_count:,}",
        f"**Completeness:** {result.completeness_score:.0f}%",
        f"**References:** {result.valid_references}/{result.total_references} valid ({result.reference_score:.0f}%)",
        "",
        "### Section Checklist",
        f"  {'[x]' if result.has_budget_section else '[ ]'} Budget Justification",
        f"  {'[x]' if result.has_methodology else '[ ]'} Methodology / Research Design",
        f"  {'[x]' if result.has_timeline else '[ ]'} Timeline / Milestones",
        f"  {'[x]' if result.has_risk_section else '[ ]'} Risk Assessment",
        f"  {'[x]' if result.total_references >= 5 else '[ ]'} References (5+)",
        "",
    ]

    if result.issues:
        lines.append("### Issues Found")
        for issue in result.issues:
            lines.append(f"  - {issue}")
        lines.append("")

    if result.reference_checks:
        lines.append("### Reference Details")
        for i, check in enumerate(result.reference_checks, 1):
            status = "PASS" if check.is_valid else "WARN"
            lines.append(f"  {i}. [{status}] (score {check.score}/5) {check.raw_text[:80]}...")
            if check.issues:
                for issue in check.issues:
                    lines.append(f"       - {issue}")

    return "\n".join(lines)
