"""Grant-to-organisation matching engine.

Scores grants against an org profile based on keyword overlap,
category alignment, and eligibility compatibility.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from au_grants_agent.models import Grant
from au_grants_agent.proposal.profiles import OrgProfile
from au_grants_agent.utils.logger import get_logger

logger = get_logger()


@dataclass
class MatchResult:
    """Result of matching a grant to an org profile."""

    grant: Grant
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    @property
    def rating(self) -> str:
        if self.score >= 0.7:
            return "Excellent"
        elif self.score >= 0.5:
            return "Good"
        elif self.score >= 0.3:
            return "Fair"
        return "Low"


# Category alignment map — which org types align with which grant categories
CATEGORY_TYPE_AFFINITY = {
    "research": {"university", "research institute", "medical research"},
    "business": {"sme", "startup", "enterprise", "company", "industry"},
    "community": {"ngo", "charity", "community organisation", "not-for-profit", "local government"},
    "health": {"university", "research institute", "medical research", "hospital"},
    "education": {"university", "school", "tafe", "education provider"},
    "infrastructure": {"university", "research institute", "company", "government"},
    "environment": {"university", "research institute", "ngo", "community organisation"},
    "defence": {"company", "enterprise", "university", "research institute"},
    "arts": {"ngo", "community organisation", "university", "charity"},
}

# State-based grants that prefer local applicants
STATE_KEYWORDS = {
    "nsw": ["new south wales", "nsw", "sydney"],
    "vic": ["victoria", "vic", "melbourne"],
    "qld": ["queensland", "qld", "brisbane"],
    "wa": ["western australia", "wa", "perth"],
    "sa": ["south australia", "sa", "adelaide"],
    "tas": ["tasmania", "tas", "hobart"],
    "act": ["australian capital territory", "act", "canberra"],
    "nt": ["northern territory", "nt", "darwin"],
}


def _tokenize(text: str) -> set[str]:
    """Extract lowercase keyword tokens from text."""
    if not text:
        return set()
    # Remove punctuation, split into words, filter short ones
    words = re.findall(r"[a-z]{3,}", text.lower())
    return set(words)


def _keyword_overlap(profile_keywords: set[str], grant_text: str) -> float:
    """Calculate keyword overlap between profile and grant text."""
    if not profile_keywords or not grant_text:
        return 0.0
    grant_tokens = _tokenize(grant_text)
    if not grant_tokens:
        return 0.0
    overlap = profile_keywords & grant_tokens
    # Normalize by profile keywords (what fraction of our strengths match)
    return len(overlap) / len(profile_keywords) if profile_keywords else 0.0


def match_grant(grant: Grant, profile: OrgProfile) -> MatchResult:
    """Score how well a grant matches an organisation profile.

    Scoring breakdown (max 1.0):
    - Research strength keyword match: 0-0.35
    - Category-type alignment: 0-0.20
    - State/location alignment: 0-0.10
    - Eligibility compatibility: 0-0.15
    - Past grants relevance: 0-0.10
    - Facilities/partnerships relevance: 0-0.10
    """
    result = MatchResult(grant=grant)
    score = 0.0

    # Build profile keyword set from research strengths + description
    profile_text = " ".join(profile.research_strengths)
    if profile.description:
        profile_text += " " + profile.description
    profile_keywords = _tokenize(profile_text)

    # Build grant text for matching
    grant_text = " ".join(filter(None, [
        grant.title,
        grant.description,
        grant.category,
        grant.eligibility,
        grant.agency,
    ]))

    # 1. Research strength keyword overlap (max 0.35)
    kw_score = _keyword_overlap(profile_keywords, grant_text)
    strength_score = min(kw_score * 2.0, 1.0) * 0.35  # Scale up, cap at 0.35
    score += strength_score
    if strength_score > 0.1:
        matching_kws = profile_keywords & _tokenize(grant_text)
        top_kws = sorted(matching_kws)[:5]
        result.reasons.append(f"Keywords match: {', '.join(top_kws)}")

    # 2. Category-type alignment (max 0.20)
    if grant.category and profile.type:
        cat_lower = grant.category.lower()
        org_type_lower = profile.type.lower()
        for cat_key, compatible_types in CATEGORY_TYPE_AFFINITY.items():
            if cat_key in cat_lower:
                if any(t in org_type_lower for t in compatible_types):
                    score += 0.20
                    result.reasons.append(f"Category '{grant.category}' aligns with org type '{profile.type}'")
                else:
                    score += 0.05  # Partial credit
                break

    # 3. State/location match (max 0.10)
    if profile.state:
        state_lower = profile.state.lower()
        grant_text_lower = grant_text.lower()
        state_kws = STATE_KEYWORDS.get(state_lower, [state_lower])
        if any(kw in grant_text_lower for kw in state_kws):
            score += 0.10
            result.reasons.append(f"Location matches state: {profile.state}")
        elif "national" in grant_text_lower or "australia" in grant_text_lower:
            score += 0.07  # National grants are available to all states
            result.reasons.append("National grant (available to all states)")

    # 4. Eligibility compatibility (max 0.15)
    if grant.eligibility and profile.type:
        elig_lower = grant.eligibility.lower()
        org_type_lower = profile.type.lower()

        # Check if org type matches eligibility
        elig_matches = {
            "university": ["university", "higher education", "research organisation", "eligible entity"],
            "research institute": ["research organisation", "research body", "eligible entity"],
            "sme": ["small business", "sme", "enterprise", "business", "company", "abn"],
            "company": ["business", "company", "enterprise", "corporation", "abn"],
            "ngo": ["not-for-profit", "ngo", "charity", "community", "incorporated"],
        }

        for org_key, elig_keywords in elig_matches.items():
            if org_key in org_type_lower:
                if any(kw in elig_lower for kw in elig_keywords):
                    score += 0.15
                    result.reasons.append("Eligibility criteria match org type")
                break
    elif not grant.eligibility:
        score += 0.08  # No eligibility info = assume broadly eligible

    # 5. Past grants relevance (max 0.10)
    if profile.past_grants:
        past_text = " ".join(profile.past_grants).lower()
        grant_agency = (grant.agency or "").lower()
        past_keywords = _tokenize(past_text)
        grant_keywords = _tokenize(grant_text)
        past_overlap = past_keywords & grant_keywords
        if len(past_overlap) > 3:
            score += 0.10
            result.reasons.append("Past grants in related area")
        elif grant_agency and any(a in past_text for a in [grant_agency[:15], "arc", "nhmrc", "mrff"]):
            score += 0.07
            result.reasons.append(f"Has past grants from related agency")

    # 6. Facilities/partnerships relevance (max 0.10)
    if profile.facilities or profile.partnerships:
        extras_text = " ".join(profile.facilities + profile.partnerships).lower()
        extras_kws = _tokenize(extras_text)
        extras_overlap = extras_kws & _tokenize(grant_text)
        if len(extras_overlap) > 2:
            score += 0.10
            result.reasons.append("Facilities/partnerships align with grant")
        elif len(extras_overlap) > 0:
            score += 0.04

    result.score = round(min(score, 1.0), 3)
    return result


def rank_grants(
    grants: list[Grant],
    profile: OrgProfile,
    min_score: float = 0.0,
    top_n: int | None = None,
) -> list[MatchResult]:
    """Rank a list of grants by match score against an org profile.

    Args:
        grants: List of grants to rank.
        profile: Organisation profile to match against.
        min_score: Minimum score threshold (0.0-1.0).
        top_n: Return only top N results (None for all).

    Returns:
        List of MatchResults sorted by score descending.
    """
    results = []
    for grant in grants:
        match = match_grant(grant, profile)
        if match.score >= min_score:
            results.append(match)

    results.sort(key=lambda m: m.score, reverse=True)

    if top_n:
        results = results[:top_n]

    return results
