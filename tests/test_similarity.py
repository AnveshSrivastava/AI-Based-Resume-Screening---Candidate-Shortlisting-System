"""Unit tests for Phase 5: Similarity computation and calibration."""

from src.similarity import (
    SimilarityEngine,
    calibrate_similarity_score,
)


def test_calibrate_similarity_bounds_and_monotonicity():
    # Bounds check
    assert calibrate_similarity_score(0.0) == 0.0
    assert calibrate_similarity_score(1.0) == 100.0

    # Monotonicity test across range
    raw_vals = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.70, 0.85]
    calibrated = [calibrate_similarity_score(v) for v in raw_vals]

    for i in range(len(calibrated) - 1):
        assert calibrated[i] <= calibrated[i + 1], f"Monotonicity violation at index {i}: {calibrated[i]} > {calibrated[i+1]}"

    # A typical good match (raw cosine ~0.20) should score in 65-85 range
    score_20 = calibrate_similarity_score(0.20)
    assert 65.0 <= score_20 <= 85.0
    assert calibrate_similarity_score(0.45) >= 95.0


def test_length_fairness():
    """Verify that a comprehensive, high-detail resume is not penalized vs a short one."""
    engine = SimilarityEngine()
    jd = "Senior Python Developer with FastAPI, PostgreSQL, Docker, and AWS."

    short_resume = "Python developer with FastAPI, PostgreSQL, and Docker."
    # Long resume has all required skills plus extensive project details and accomplishments
    long_resume = (
        "Senior Software Architect with 8 years of experience. Expert in Python, FastAPI, PostgreSQL, Docker, AWS. "
        "Architected enterprise distributed platforms handling over 10 million transactions per day. "
        "Mentored a team of 15 engineers, led sprint planning, improved CI/CD throughput by 40%, and managed "
        "multi-region cloud infrastructure on AWS ECS and Kubernetes. Designed database schemas, optimized complex SQL queries, "
        "implemented comprehensive telemetry with Prometheus, and reduced p99 latency to under 20ms."
    )

    sims = engine.compute_batch_similarity(jd, [short_resume, long_resume])
    short_calib = sims[0][0]
    long_calib = sims[1][0]

    # The long resume contains all JD skills and rich context; its calibrated similarity should be robust
    assert long_calib >= 65.0, f"Long resume score {long_calib} was unfairly crushed"
