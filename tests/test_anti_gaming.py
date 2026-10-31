"""Unit tests for Phase 5: Anti-gaming and keyword stuffing detection."""

from src.anti_gaming import detect_anti_gaming
from src.config import SystemConfig
from src.models import CandidateProfile, JobProfile, SkillMatch
from src.ranker import rank_and_classify_candidates


def test_keyword_repetition_detection():
    job = JobProfile(title="Backend Engineer", required_skills=["python", "docker"])
    candidate = CandidateProfile(
        candidate_id="c_stuffed",
        filename="stuffed.pdf",
        cleaned_text="Python " * 15 + "Docker",
        extracted_skills={
            "python": SkillMatch(canonical_name="python", category="languages", count=15),
            "docker": SkillMatch(canonical_name="docker", category="cloud/devops", count=1),
        },
    )

    is_flagged, flags, penalty = detect_anti_gaming(candidate, job, raw_similarity=0.4)
    assert is_flagged is True
    assert penalty > 0.0
    assert any("Excessive keyword repetition" in f for f in flags)


def test_verbatim_jd_copy_flag():
    job = JobProfile(title="Data Scientist", raw_text="We require Python, SQL, and Machine Learning.")
    candidate = CandidateProfile(
        candidate_id="c_copy",
        filename="copy.pdf",
        cleaned_text="We require Python, SQL, and Machine Learning.",
    )

    # Raw similarity >= 0.88 triggers verbatim copy warning
    is_flagged, flags, penalty = detect_anti_gaming(candidate, job, raw_similarity=0.92)
    assert is_flagged is True
    assert any("Suspiciously high JD overlap" in f for f in flags)


def test_stuffed_candidate_ranks_below_honest_candidate():
    job = JobProfile(
        title="Python Engineer",
        required_skills=["python", "fastapi", "docker"],
        min_years_experience=3.0,
    )

    honest_candidate = CandidateProfile(
        candidate_id="c_honest",
        filename="honest.pdf",
        cleaned_text="Backend engineer with 4 years experience in Python, FastAPI, and Docker.",
        total_years_experience=4.0,
        highest_education_level="Bachelor",
        extracted_skills={
            "python": SkillMatch("python", "languages", count=2, is_demonstrated=True),
            "fastapi": SkillMatch("fastapi", "backend", count=2, is_demonstrated=True),
            "docker": SkillMatch("docker", "cloud/devops", count=1, is_demonstrated=True),
        },
    )

    # Stuffed candidate repeats keywords 20 times to artificially game similarity
    stuffed_candidate = CandidateProfile(
        candidate_id="c_stuffed",
        filename="stuffed.pdf",
        cleaned_text="python " * 20 + "fastapi " * 15 + "docker " * 10,
        total_years_experience=1.0,
        highest_education_level="Bachelor",
        extracted_skills={
            "python": SkillMatch("python", "languages", count=20, is_demonstrated=False),
            "fastapi": SkillMatch("fastapi", "backend", count=15, is_demonstrated=False),
            "docker": SkillMatch("docker", "cloud/devops", count=10, is_demonstrated=False),
        },
    )

    sims = [(85.0, 0.45, 0.0), (90.0, 0.55, 0.0)]
    results = rank_and_classify_candidates(
        candidates=[honest_candidate, stuffed_candidate],
        job=job,
        similarities=sims,
    )

    # Honest candidate should rank 1st, stuffed candidate must be penalized and rank 2nd
    assert results[0].candidate.candidate_id == "c_honest"
    assert results[1].candidate.candidate_id == "c_stuffed"
    assert len(results[1].anti_gaming_flags) > 0
    assert results[1].score.penalty > 0
