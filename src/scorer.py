"""Explainable candidate scoring module.

Evaluates candidates across six weighted dimensions:
1. Required skills coverage (40%)
2. Preferred skills coverage (10%)
3. Calibrated text/semantic similarity (20%)
4. Years of experience fit (15%)
5. Educational qualification fit (10%)
6. Skill evidence quality (5%)

Enforces configurable knockout thresholds and provides clear, human-readable explanations.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from src.config import SystemConfig
from src.models import CandidateProfile, JobProfile, ScoreBreakdown


logger = logging.getLogger(__name__)

EDU_LEVEL_RANKS = {
    "phd": 4,
    "master": 3,
    "bachelor": 2,
    "diploma": 1,
    "high school": 0,
    "unspecified": 0,
    "any": 0,
}


def compute_candidate_score(
    candidate: CandidateProfile,
    job: JobProfile,
    calibrated_similarity: float,
    anti_gaming_penalty: float = 0.0,
    config: Optional[SystemConfig] = None,
) -> ScoreBreakdown:
    """Compute an explainable, multi-factor ScoreBreakdown for a candidate.

    Args:
        candidate: Candidate profile with extracted skills and experience.
        job: Target job profile.
        calibrated_similarity: Precomputed 0-100 similarity score.
        anti_gaming_penalty: Score points deducted due to keyword stuffing.
        config: System configuration and weights.

    Returns:
        ScoreBreakdown containing component scores, contributions, and explanations.
    """
    cfg = config or SystemConfig()
    weights = cfg.weights.normalized()
    explanations: List[str] = []

    # 1. Required skills coverage
    cand_skills_set = set(candidate.extracted_skills.keys())
    req_skills_set = set(job.required_skills)
    matched_req = sorted(list(req_skills_set.intersection(cand_skills_set)))
    missing_req = sorted(list(req_skills_set.difference(cand_skills_set)))

    if req_skills_set:
        req_coverage = len(matched_req) / len(req_skills_set)
        req_score = req_coverage * 100.0
        missing_text = f"; missing: {', '.join(missing_req)}" if missing_req else ""
        explanations.append(
            f"Required Skills: Matches {len(matched_req)}/{len(req_skills_set)} "
            f"({req_coverage * 100:.0f}%){missing_text}."
        )
    else:
        req_coverage = 1.0
        req_score = 100.0
        explanations.append("Required Skills: No specific required skills specified in JD (100%).")

    # 2. Preferred skills coverage
    pref_skills_set = set(job.preferred_skills)
    matched_pref = sorted(list(pref_skills_set.intersection(cand_skills_set)))
    missing_pref = sorted(list(pref_skills_set.difference(cand_skills_set)))

    if pref_skills_set:
        pref_coverage = len(matched_pref) / len(pref_skills_set)
        pref_score = pref_coverage * 100.0
        missing_pref_text = f"; missing: {', '.join(missing_pref)}" if missing_pref else ""
        explanations.append(
            f"Preferred Skills: Matches {len(matched_pref)}/{len(pref_skills_set)} "
            f"({pref_coverage * 100:.0f}%){missing_pref_text}."
        )
    else:
        pref_score = 100.0
        explanations.append("Preferred Skills: None specified in JD (100%).")

    # 3. Similarity score
    sim_score = max(0.0, min(100.0, calibrated_similarity))
    explanations.append(f"Content Similarity: Calibrated relevance score of {sim_score:.1f}/100.")

    # 4. Experience fit
    cand_exp = candidate.total_years_experience
    req_exp = job.min_years_experience
    if req_exp <= 0.0:
        exp_score = 100.0
        explanations.append(f"Experience Fit: Candidate has {cand_exp:.1f} years (no minimum required).")
    elif cand_exp >= req_exp:
        exp_score = 100.0
        surplus = cand_exp - req_exp
        surplus_str = f" (+{surplus:.1f} yr surplus)" if surplus > 0 else ""
        explanations.append(f"Experience Fit: Has {cand_exp:.1f} yrs vs {req_exp:.1f} yrs required{surplus_str}.")
    else:
        exp_score = (cand_exp / req_exp) * 100.0
        shortfall = req_exp - cand_exp
        explanations.append(
            f"Experience Fit: Has {cand_exp:.1f} yrs vs {req_exp:.1f} yrs required "
            f"(-{shortfall:.1f} yr shortfall, {exp_score:.0f}%)."
        )

    # 5. Education fit
    cand_edu = candidate.highest_education_level.lower()
    req_edu = job.required_education_level.lower()
    cand_rank = EDU_LEVEL_RANKS.get(cand_edu, 0)
    req_rank = EDU_LEVEL_RANKS.get(req_edu, 0)

    if req_edu in ("any", "unspecified") or cand_rank >= req_rank:
        edu_score = 100.0
        explanations.append(f"Education: '{candidate.highest_education_level}' meets/exceeds requirement ('{job.required_education_level}').")
    elif cand_rank == req_rank - 1:
        edu_score = 70.0
        explanations.append(f"Education: '{candidate.highest_education_level}' is slightly below '{job.required_education_level}' (70%).")
    else:
        edu_score = 40.0
        explanations.append(f"Education: '{candidate.highest_education_level}' is below '{job.required_education_level}' (40%).")

    # 6. Evidence quality (demonstrated in experience/projects vs only listed)
    all_matched = matched_req + matched_pref
    if all_matched:
        demonstrated_count = sum(
            1 for s in all_matched if candidate.extracted_skills.get(s) and candidate.extracted_skills[s].is_demonstrated
        )
        evidence_score = (demonstrated_count / len(all_matched)) * 100.0
        explanations.append(
            f"Evidence Quality: {demonstrated_count}/{len(all_matched)} matched skills "
            f"({evidence_score:.0f}%) verified with work experience or project bullets."
        )
    else:
        evidence_score = 0.0
        explanations.append("Evidence Quality: No required or preferred skills matched (0%).")

    # Calculate weighted contributions
    req_contrib = req_score * weights.required_skills
    pref_contrib = pref_score * weights.preferred_skills
    sim_contrib = sim_score * weights.similarity
    exp_contrib = exp_score * weights.experience_fit
    edu_contrib = edu_score * weights.education_fit
    evid_contrib = evidence_score * weights.evidence_quality

    raw_total = req_contrib + pref_contrib + sim_contrib + exp_contrib + edu_contrib + evid_contrib
    final_score = raw_total - anti_gaming_penalty

    # Knockout evaluation
    is_knocked_out = False
    knockout_reason = None
    if req_skills_set and req_coverage < cfg.thresholds.knockout_required_coverage:
        is_knocked_out = True
        knockout_reason = (
            f"Knockout: Required skills coverage ({req_coverage * 100:.0f}%) is below the "
            f"minimum threshold of {cfg.thresholds.knockout_required_coverage * 100:.0f}%. "
            f"Final score capped at {cfg.thresholds.knockout_score_cap:.0f}."
        )
        explanations.insert(0, f"⚠️ {knockout_reason}")
        final_score = min(final_score, cfg.thresholds.knockout_score_cap)

    # Scanned/empty document penalty
    if candidate.is_scanned_or_empty:
        final_score = 0.0
        explanations.insert(0, "⚠️ Document is scanned or unreadable. Manual review required.")

    final_score = float(max(0.0, min(100.0, final_score)))

    return ScoreBreakdown(
        required_skills_score=round(req_score, 1),
        preferred_skills_score=round(pref_score, 1),
        similarity_score=round(sim_score, 1),
        experience_score=round(exp_score, 1),
        education_score=round(edu_score, 1),
        evidence_score=round(evidence_score, 1),
        required_skills_contribution=round(req_contrib, 2),
        preferred_skills_contribution=round(pref_contrib, 2),
        similarity_contribution=round(sim_contrib, 2),
        experience_contribution=round(exp_contrib, 2),
        education_contribution=round(edu_contrib, 2),
        evidence_contribution=round(evid_contrib, 2),
        raw_total=round(raw_total, 2),
        penalty=round(anti_gaming_penalty, 2),
        final_score=round(final_score, 1),
        is_knocked_out=is_knocked_out,
        knockout_reason=knockout_reason,
        explanations=explanations,
    )
