"""Organisation profile management for tailored proposal generation."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

from au_grants_agent.config import settings
from au_grants_agent.utils.logger import get_logger

logger = get_logger()

PROFILES_DIR = Path("profiles")

EXAMPLE_PROFILE = {
    "name": "University of Melbourne",
    "type": "University",
    "abn": "84 002 705 224",
    "state": "VIC",
    "description": "A leading research-intensive university in Australia, ranked in the top 50 globally.",
    "research_strengths": [
        "Biomedical sciences and health",
        "Engineering and technology",
        "Environmental science and sustainability",
        "Data science and artificial intelligence",
    ],
    "key_personnel": [
        {
            "name": "Prof. Jane Smith",
            "role": "Chief Investigator",
            "qualifications": "PhD (Cambridge), FAHA",
            "expertise": "Functional genomics, CRISPR screening",
        },
        {
            "name": "Dr. Alan Chen",
            "role": "Co-Investigator",
            "qualifications": "PhD (MIT)",
            "expertise": "Bioinformatics, machine learning",
        },
    ],
    "past_grants": [
        "ARC Discovery Project DP210100123 ($450,000) — Genomic approaches to antibiotic resistance",
        "NHMRC Ideas Grant APP2001234 ($650,000) — Single-cell analysis of immune responses",
    ],
    "facilities": [
        "BSL-2/3 laboratories",
        "High-performance computing cluster (2000+ cores)",
        "Advanced microscopy suite",
    ],
    "partnerships": [
        "CSIRO",
        "Walter and Eliza Hall Institute",
        "Peter Doherty Institute",
    ],
}


class PersonnelEntry(BaseModel):
    """A key team member in the organisation profile."""

    name: str
    role: str
    qualifications: Optional[str] = None
    expertise: Optional[str] = None


class OrgProfile(BaseModel):
    """Organisation profile for tailored proposal generation."""

    name: str
    type: Optional[str] = Field(default=None, description="e.g. University, Research Institute, SME")
    abn: Optional[str] = None
    state: Optional[str] = None
    description: Optional[str] = None
    research_strengths: list[str] = Field(default_factory=list)
    key_personnel: list[PersonnelEntry] = Field(default_factory=list)
    past_grants: list[str] = Field(default_factory=list)
    facilities: list[str] = Field(default_factory=list)
    partnerships: list[str] = Field(default_factory=list)

    def to_prompt_section(self) -> str:
        """Build a structured prompt section from this profile."""
        parts = [f"**Applicant Organisation:** {self.name}"]

        if self.type:
            parts.append(f"**Organisation Type:** {self.type}")
        if self.abn:
            parts.append(f"**ABN:** {self.abn}")
        if self.state:
            parts.append(f"**State:** {self.state}")
        if self.description:
            parts.append(f"**About:** {self.description}")

        if self.research_strengths:
            parts.append("**Research Strengths:**")
            for s in self.research_strengths:
                parts.append(f"  - {s}")

        if self.key_personnel:
            parts.append("**Key Personnel:**")
            for p in self.key_personnel:
                line = f"  - {p.name} ({p.role})"
                if p.qualifications:
                    line += f" — {p.qualifications}"
                if p.expertise:
                    line += f". Expertise: {p.expertise}"
                parts.append(line)

        if self.past_grants:
            parts.append("**Track Record (Recent Grants):**")
            for g in self.past_grants:
                parts.append(f"  - {g}")

        if self.facilities:
            parts.append("**Available Facilities:**")
            for f in self.facilities:
                parts.append(f"  - {f}")

        if self.partnerships:
            parts.append("**Key Partnerships:**")
            for p in self.partnerships:
                parts.append(f"  - {p}")

        parts.append(
            "\nTailor the proposal to this organisation's demonstrated capabilities, "
            "personnel, and research strengths. Reference their track record and facilities where relevant."
        )

        return "\n".join(parts)


def get_profiles_dir() -> Path:
    """Get the profiles directory, creating if needed."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return PROFILES_DIR


def save_profile(profile: OrgProfile, filename: Optional[str] = None) -> Path:
    """Save an org profile to YAML."""
    profiles_dir = get_profiles_dir()
    if not filename:
        # Sanitize name for filename
        safe_name = profile.name.lower().replace(" ", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == "_")
        filename = f"{safe_name}.yaml"

    filepath = profiles_dir / filename
    data = profile.model_dump(exclude_none=True)
    filepath.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")
    logger.info("Saved profile: %s", filepath)
    return filepath


def load_profile(name_or_path: str) -> OrgProfile:
    """Load an org profile from YAML file.

    Args:
        name_or_path: Either a profile name (looked up in profiles dir) or a direct file path.
    """
    path = Path(name_or_path)

    # If it's not an existing file, look in profiles dir
    if not path.exists():
        profiles_dir = get_profiles_dir()
        # Try exact filename
        path = profiles_dir / name_or_path
        if not path.exists():
            # Try with .yaml extension
            path = profiles_dir / f"{name_or_path}.yaml"
        if not path.exists():
            # Try with .yml extension
            path = profiles_dir / f"{name_or_path}.yml"

    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {name_or_path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return OrgProfile(**data)


def list_profiles() -> list[tuple[str, str]]:
    """List available profiles. Returns list of (filename, org_name)."""
    profiles_dir = get_profiles_dir()
    results = []
    for f in sorted(profiles_dir.glob("*.y*ml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            results.append((f.name, data.get("name", "Unknown")))
        except Exception:
            results.append((f.name, "(invalid)"))
    return results


def create_example_profile() -> Path:
    """Create an example profile YAML file."""
    profiles_dir = get_profiles_dir()
    filepath = profiles_dir / "example_university.yaml"
    filepath.write_text(
        yaml.dump(EXAMPLE_PROFILE, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    return filepath
