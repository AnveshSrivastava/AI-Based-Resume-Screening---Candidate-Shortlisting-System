"""Unit tests for Phase 5: Explainable scorer and ranking."""

from src.config import SystemConfig
from src.models import (
    CandidateProfile,
    DecisionBand,
    JobProfile,
    SkillMatch,
)
from src.ranker import rank_and_classify_candidates
from src.scorer import compute_candidate_score


def test_weights_normalization_and_component_bounds():
    config = SystemConfig()
    job = JobProfile(
        title="Backend Engineer",
        required_skills=["python", "fastapi", "docker", "postgresql"],
        preferred_skills=["aws", "kubernetes"],
        min_years_experience=3.0,
        required_education_level="Bachelor",
    )
    candidate = CandidateProfile(
        candidate_id="c1",
        filename="cand1.pdf",
        total_years_experience=4.0,
        highest_education_level="Master",
        extracted_skills={
            "python": SkillMatch("python", "languages", is_demonstrated=True),
            "fastapi": SkillMatch("fastapi", "backend", is_demonstrated=True),
            "docker": SkillMatch("docker", "cloud/devops", is_demonstrated=True),
            "postgresql": SkillMatch("postgresql", "databases", is_demonstrated=True),
            "aws": SkillMatch("aws", "cloud/devops", is_demonstrated=True),
        },
    )

    breakdown = compute_candidate_score(
        candidate=candidate,
        job=job,
        calibrated_similarity=85.0,
        config=config,
    )

    # Required: 4/4 = 100
    assert breakdown.required_skills_score == 100.0
    # Preferred: 1/2 = 50
    assert breakdown.preferred_skills_score == 50.0
    # Experience: 4 >= 3 -> 100
    assert breakdown.experience_score == 100.0
    # Education: Master >= Bachelor -> 100
    assert breakdown.education_score == 100.0
    # Bounds check
    assert 0.0 <= breakdown.final_score <= 100.0
    assert len(breakdown.explanations) >= 5


def test_knockout_rule():
    config = SystemConfig()
    job = JobProfile(
        title="ML Engineer",
        required_skills=["python", "pytorch", "scikit-learn", "docker", "sql"],
        min_years_experience=2.0,
    )
    # Candidate matches only 1 out of 5 required skills (20% < 30% knockout)
    candidate = CandidateProfile(
        candidate_id="c_low",
        filename="low.pdf",
        total_years_experience=5.0,
        highest_education_level="Master",
        extracted_skills={"sql": SkillMatch("sql", "languages")},
    )

    breakdown = compute_candidate_score(
        candidate=candidate,
        job=job,
        calibrated_similarity=50.0,
        config=config,
    )

    assert breakdown.is_knocked_out is True
    assert breakdown.final_score <= config.thresholds.knockout_score_cap
    assert breakdown.knockout_reason is not None
    assert "Knockout" in breakdown.knockout_reason


def test_monotonicity_adding_required_skill():
    config = SystemConfig()
    job = JobProfile(
        title="DevOps",
        required_skills=["docker", "kubernetes", "terraform"],
    )

    candidate_a = CandidateProfile(
        candidate_id="cA",
        filename="cA.pdf",
        extracted_skills={"docker": SkillMatch("docker", "cloud/devops")},
    )
    candidate_b = CandidateProfile(
        candidate_id="cB",
        filename="cB.pdf",
        extracted_skills={
            "docker": SkillMatch("docker", "cloud/devops"),
            "kubernetes": SkillMatch("kubernetes", "cloud/devops"),
        },
    )

    score_a = compute_candidate_score(candidate_a, job, calibrated_similarity=60.0, config=config)
    score_b = compute_candidate_score(candidate_b, job, calibrated_similarity=60.0, config=config)

    assert score_b.final_score > score_a.final_score


def test_tie_breaking_in_ranker():
    job = JobProfile(title="Developer", required_skills=["python", "docker"], min_years_experience=2.0)

    # Candidate 1: 5 yrs experience
    cand1 = CandidateProfile(
        candidate_id="c1",
        filename="c1.pdf",
        total_years_experience=5.0,
        extracted_skills={
            "python": SkillMatch("python", "languages"),
            "docker": SkillMatch("docker", "cloud/devops"),
        },
    )
    # Candidate 2: 2 yrs experience
    cand2 = CandidateProfile(
        candidate_id="c2",
        filename="c2.pdf",
        total_years_experience=2.0,
        extracted_skills={
            "python": SkillMatch("python", "languages"),
            "docker": SkillMatch("docker", "cloud/devops"),
        },
    )

    results = rank_and_classify_candidates(
        candidates=[cand2, cand1],
        job=job,
        similarities=[(80.0, 0.4, 0.0), (80.0, 0.4, 0.0)],
    )

    assert results[0].candidate.candidate_id == "c1"  # More experience breaks tie
    assert results[1].candidate.candidate_id == "c2"
    assert results[0].rank == 1
    assert results[1].rank == 2
