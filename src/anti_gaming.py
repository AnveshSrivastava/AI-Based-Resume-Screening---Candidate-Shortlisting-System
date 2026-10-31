"""Anti-gaming and keyword stuffing detection module.

Identifies manipulative resume tactics including:
- Excessive single-skill repetition.
- Abnormal skill keyword density.
- Verbatim or near-duplicate copying of the job description text.
Applies configurable penalties and transparent warning flags.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

from src.config import AntiGamingConfig, SystemConfig
from src.models import CandidateProfile, JobProfile, SkillMatch


logger = logging.getLogger(__name__)


def detect_anti_gaming(
    candidate: CandidateProfile,
    job: JobProfile,
    raw_similarity: float = 0.0,
    config: Optional[SystemConfig] = None,
) -> Tuple[bool, List[str], float]:
    """Analyze a candidate's resume for keyword stuffing and gaming patterns.

    Args:
        candidate: Parsed candidate profile with extracted skills.
        job: Parsed job profile.
        raw_similarity: Raw TF-IDF / semantic cosine similarity against the JD.
        config: System configuration for anti-gaming thresholds.

    Returns:
        Tuple of (is_flagged, warning_flags, penalty_points).
    """
    cfg = (config or SystemConfig()).anti_gaming
    flags: List[str] = []
    penalty: float = 0.0

    # 1. Check excessive repetition of any single skill
    for skill_name, match in candidate.extracted_skills.items():
        if match.count > cfg.max_single_skill_frequency:
            flags.append(
                f"Excessive keyword repetition: '{skill_name}' appears {match.count} times "
                f"(threshold: {cfg.max_single_skill_frequency})."
            )

    # 2. Check skill density anomaly (skill words vs total words in resume)
    total_words = max(1, len(re.findall(r"\b\w+\b", candidate.cleaned_text)))
    total_skill_mentions = sum(m.count for m in candidate.extracted_skills.values())
    density_ratio = total_skill_mentions / total_words

    if density_ratio > cfg.max_skill_density_ratio and total_words > 40:
        flags.append(
            f"Abnormal skill density: {density_ratio * 100:.1f}% of words are skill keywords "
            f"(threshold: {cfg.max_skill_density_ratio * 100:.0f}%)."
        )

    # 3. Check for verbatim or near-verbatim copying of the JD
    if raw_similarity >= cfg.jd_verbatim_similarity_flag:
        flags.append(
            f"Suspiciously high JD overlap: raw similarity {raw_similarity:.2f} >= "
            f"{cfg.jd_verbatim_similarity_flag:.2f} indicates potential verbatim copying."
        )

    # Calculate penalty if any red flags triggered
    is_flagged = len(flags) > 0
    if is_flagged:
        # Penalize proportionally to the number of triggered flags
        penalty = min(cfg.stuffing_penalty_points * len(flags), 50.0)
        logger.info("Anti-gaming triggered for candidate %s: %s (penalty: %.1f)", candidate.candidate_id, flags, penalty)

    return is_flagged, flags, penalty
