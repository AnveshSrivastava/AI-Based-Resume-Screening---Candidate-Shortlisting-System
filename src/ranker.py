"""Candidate ranking and classification engine.

Sorts candidates deterministically by final score with secondary tie-breakers
(required skills coverage, followed by years of experience).
Assigns decision bands (Shortlisted, Review, Rejected) based on configurable thresholds.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from src.anti_gaming import detect_anti_gaming
from src.config import SystemConfig
from src.models import (
    CandidateProfile,
    DecisionBand,
    JobProfile,
    ScoreBreakdown,
    ScreeningResult,
)
from src.scorer import compute_candidate_score


logger = logging.getLogger(__name__)


def rank_and_classify_candidates(
    candidates: List[CandidateProfile],
    job: JobProfile,
    similarities: List[tuple[float, float, float]],
    config: Optional[SystemConfig] = None,
) -> List[ScreeningResult]:
    """Score, rank, and classify a batch of candidate profiles against a job.

    Args:
        candidates: List of parsed CandidateProfile objects.
        job: Parsed JobProfile object.
        similarities: List of tuples (calibrated_sim, raw_tfidf, raw_semantic) aligned with candidates.
        config: System configuration and thresholds.

    Returns:
        Sorted list of ScreeningResult objects with assigned ranks and bands.
    """
    if not candidates:
        return []

    cfg = config or SystemConfig()
    scored_results: List[ScreeningResult] = []

    for idx, cand in enumerate(candidates):
        calib_sim, raw_sim, _ = similarities[idx] if idx < len(similarities) else (0.0, 0.0, 0.0)

        # 1. Anti-gaming analysis
        is_stuffed, anti_gaming_flags, penalty = detect_anti_gaming(
            candidate=cand,
            job=job,
            raw_similarity=raw_sim,
            config=cfg,
        )

        # 2. Score calculation
        score_breakdown = compute_candidate_score(
            candidate=cand,
            job=job,
            calibrated_similarity=calib_sim,
            anti_gaming_penalty=penalty,
            config=cfg,
        )

        # 3. Decision band assignment
        final_score = score_breakdown.final_score
        if final_score >= cfg.thresholds.shortlist_min:
            band = DecisionBand.SHORTLISTED
        elif final_score >= cfg.thresholds.review_min:
            band = DecisionBand.REVIEW
        else:
            band = DecisionBand.REJECTED

        # Compile warnings
        warnings: List[str] = []
        if cand.is_scanned_or_empty:
            warnings.append(cand.extraction_warning or "Scanned or unreadable document.")
        if score_breakdown.is_knocked_out and score_breakdown.knockout_reason:
            warnings.append(score_breakdown.knockout_reason)
        warnings.extend(anti_gaming_flags)

        result = ScreeningResult(
            candidate=cand,
            score=score_breakdown,
            rank=1,  # Will be assigned after sorting
            band=band,
            anti_gaming_flags=anti_gaming_flags,
            warnings=warnings,
        )
        scored_results.append(result)

    # 4. Deterministic sorting: final_score DESC -> required_skills_score DESC -> total_exp DESC
    scored_results.sort(
        key=lambda r: (
            r.score.final_score,
            r.score.required_skills_score,
            r.candidate.total_years_experience,
        ),
        reverse=True,
    )

    # 5. Assign ranks
    for rank_idx, res in enumerate(scored_results, start=1):
        res.rank = rank_idx

    return scored_results
