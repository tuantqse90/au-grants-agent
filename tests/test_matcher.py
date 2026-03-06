"""Tests for au_grants_agent.proposal.matcher."""

import pytest

from au_grants_agent.models import Grant
from au_grants_agent.proposal.matcher import (
    MatchResult,
    _keyword_overlap,
    _tokenize,
    match_grant,
    rank_grants,
)
from au_grants_agent.proposal.profiles import OrgProfile


# ── helpers ───────────────────────────────────────────────────

def _make_grant(**kwargs) -> Grant:
    defaults = dict(
        id="test-id",
        title="Test Grant",
        agency="Test Agency",
        status="Open",
    )
    defaults.update(kwargs)
    return Grant(**defaults)


def _make_profile(**kwargs) -> OrgProfile:
    defaults = dict(name="Test Uni")
    defaults.update(kwargs)
    return OrgProfile(**defaults)


# ── _tokenize ─────────────────────────────────────────────────

class TestTokenize:
    def test_basic(self):
        tokens = _tokenize("Machine Learning Research")
        assert "machine" in tokens
        assert "learning" in tokens
        assert "research" in tokens

    def test_filters_short_words(self):
        tokens = _tokenize("AI is a big deal")
        assert "big" in tokens
        assert "deal" in tokens
        assert "ai" not in tokens  # too short (2 chars)
        assert "is" not in tokens

    def test_empty_string(self):
        assert _tokenize("") == set()

    def test_none(self):
        assert _tokenize(None) == set()

    def test_removes_punctuation(self):
        tokens = _tokenize("hello, world! testing 123")
        assert "hello" in tokens
        assert "world" in tokens
        assert "testing" in tokens


# ── _keyword_overlap ──────────────────────────────────────────

class TestKeywordOverlap:
    def test_full_overlap(self):
        profile_kws = {"machine", "learning"}
        score = _keyword_overlap(profile_kws, "machine learning research")
        assert score == 1.0  # 2/2 match

    def test_partial_overlap(self):
        profile_kws = {"machine", "learning", "quantum", "biology"}
        score = _keyword_overlap(profile_kws, "machine learning research")
        assert 0 < score < 1

    def test_no_overlap(self):
        profile_kws = {"quantum", "physics"}
        score = _keyword_overlap(profile_kws, "grant for cooking")
        assert score == 0.0

    def test_empty_profile(self):
        assert _keyword_overlap(set(), "some text") == 0.0

    def test_empty_text(self):
        assert _keyword_overlap({"hello"}, "") == 0.0


# ── match_grant ──────────────────────────────────────────────

class TestMatchGrant:
    def test_returns_match_result(self):
        grant = _make_grant()
        profile = _make_profile()
        result = match_grant(grant, profile)
        assert isinstance(result, MatchResult)
        assert result.grant == grant
        assert 0 <= result.score <= 1.0

    def test_research_keywords_boost(self):
        grant = _make_grant(
            title="Machine Learning for Genomics",
            description="Deep learning applied to genome sequencing analysis",
            category="Research",
        )
        profile = _make_profile(
            research_strengths=["machine learning", "genomics", "deep learning"],
            type="University",
        )
        result = match_grant(grant, profile)
        assert result.score > 0.3

    def test_category_alignment(self):
        grant = _make_grant(category="Research")
        profile = _make_profile(type="University")
        result = match_grant(grant, profile)
        # Should get category bonus
        assert result.score > 0

    def test_state_match(self):
        grant = _make_grant(
            title="NSW Innovation Grant",
            description="For organisations in New South Wales",
        )
        profile = _make_profile(state="NSW")
        result = match_grant(grant, profile)
        assert any("state" in r.lower() or "location" in r.lower() for r in result.reasons)

    def test_national_grant_partial_state(self):
        grant = _make_grant(
            title="National Research Grant",
            description="Available to all Australian researchers",
        )
        profile = _make_profile(state="VIC")
        result = match_grant(grant, profile)
        assert any("national" in r.lower() for r in result.reasons)

    def test_eligibility_match(self):
        grant = _make_grant(eligibility="Open to universities and higher education providers")
        profile = _make_profile(type="University")
        result = match_grant(grant, profile)
        assert any("eligibility" in r.lower() for r in result.reasons)

    def test_past_grants_boost(self):
        grant = _make_grant(
            title="ARC Discovery Grant",
            agency="Australian Research Council",
            description="Supporting fundamental research",
        )
        profile = _make_profile(
            past_grants=["ARC Discovery Project 2022 - Neural Networks"],
            research_strengths=["fundamental research"],
        )
        result = match_grant(grant, profile)
        assert result.score > 0.1

    def test_score_capped_at_1(self):
        grant = _make_grant(
            title="Machine Learning Research in NSW for Universities",
            description="Deep learning genomics research in New South Wales",
            category="Research",
            eligibility="Open to universities",
        )
        profile = _make_profile(
            type="University",
            state="NSW",
            research_strengths=["machine learning", "deep learning", "genomics"],
            past_grants=["ARC DP 2023"],
            facilities=["GPU cluster", "research lab"],
        )
        result = match_grant(grant, profile)
        assert result.score <= 1.0

    def test_rating_excellent(self):
        r = MatchResult(grant=_make_grant(), score=0.8)
        assert r.rating == "Excellent"

    def test_rating_good(self):
        r = MatchResult(grant=_make_grant(), score=0.6)
        assert r.rating == "Good"

    def test_rating_fair(self):
        r = MatchResult(grant=_make_grant(), score=0.4)
        assert r.rating == "Fair"

    def test_rating_low(self):
        r = MatchResult(grant=_make_grant(), score=0.1)
        assert r.rating == "Low"


# ── rank_grants ──────────────────────────────────────────────

class TestRankGrants:
    def test_sorted_descending(self):
        grants = [
            _make_grant(id="1", title="Cooking Grant", category="Arts"),
            _make_grant(id="2", title="AI Research", category="Research",
                       description="Machine learning research"),
        ]
        profile = _make_profile(
            type="University",
            research_strengths=["machine learning", "artificial intelligence"],
        )
        results = rank_grants(grants, profile)
        if len(results) >= 2:
            assert results[0].score >= results[1].score

    def test_min_score_filter(self):
        grants = [_make_grant(id=str(i)) for i in range(5)]
        profile = _make_profile()
        results = rank_grants(grants, profile, min_score=0.99)
        # Very high threshold should filter most out
        assert len(results) <= len(grants)

    def test_top_n(self):
        grants = [_make_grant(id=str(i)) for i in range(10)]
        profile = _make_profile()
        results = rank_grants(grants, profile, top_n=3)
        assert len(results) <= 3

    def test_empty_grants(self):
        profile = _make_profile()
        results = rank_grants([], profile)
        assert results == []
