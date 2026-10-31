"""Tests for Phase 1: Configuration and data models."""

from src.config import ScoringWeights, SystemConfig
from src.models import (
    CandidateProfile,
    DecisionBand,
    JobProfile,
    ScoreBreakdown,
    ScreeningResult,
    SkillMatch,
)


def test_scoring_weights_normalization():
    weights = ScoringWeights(
        required_skills=0.8,
        preferred_skills=0.2,
        similarity=0.4,
        experience_fit=0.3,
        education_fit=0.2,
        evidence_quality=0.1,
    )
    norm = weights.normalized()
    total = (
        norm.required_skills
        + norm.preferred_skills
        + norm.similarity
        + norm.experience_fit
        + norm.education_fit
        + norm.evidence_quality
    )
    assert abs(total - 1.0) < 1e-6


def test_models_instantiation():
    job = JobProfile(title="Backend Engineer", required_skills=["python", "fastapi"])
    assert job.title == "Backend Engineer"
    assert len(job.required_skills) == 2

    match = SkillMatch(
        canonical_name="python",
        category="languages",
        count=3,
        locations=["skills", "experience"],
        is_demonstrated=True,
    )
    candidate = CandidateProfile(
        candidate_id="c1",
        filename="resume1.pdf",
        extracted_skills={"python": match},
    )
    assert "python" in candidate.extracted_skills
    assert candidate.extracted_skills["python"].is_demonstrated is True

    breakdown = ScoreBreakdown(
        final_score=85.0,
        explanations=["Matches all required skills."],
    )
    result = ScreeningResult(
        candidate=candidate,
        score=breakdown,
        band=DecisionBand.SHORTLISTED,
    )
    assert result.band == DecisionBand.SHORTLISTED
    assert result.score.final_score == 85.0
