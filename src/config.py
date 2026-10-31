"""Configuration module for the AI-Based Resume Screening System.

Defines default weights, classification thresholds, feature flags, and constraints.
All paths are resolved relative to the project root for cross-platform portability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
TAXONOMY_PATH: Path = DATA_DIR / "skills_taxonomy.json"
SAMPLE_JDS_DIR: Path = DATA_DIR / "sample_job_descriptions"
SAMPLE_RESUMES_DIR: Path = DATA_DIR / "sample_resumes"


@dataclass
class ScoringWeights:
    """Weights for the six scoring components. Must sum to 1.0 (or 100%)."""

    required_skills: float = 0.40
    preferred_skills: float = 0.10
    similarity: float = 0.20
    experience_fit: float = 0.15
    education_fit: float = 0.10
    evidence_quality: float = 0.05

    def normalized(self) -> ScoringWeights:
        """Return a copy where all weights strictly sum to 1.0."""
        total = (
            self.required_skills
            + self.preferred_skills
            + self.similarity
            + self.experience_fit
            + self.education_fit
            + self.evidence_quality
        )
        if total <= 0:
            return ScoringWeights()
        return ScoringWeights(
            required_skills=self.required_skills / total,
            preferred_skills=self.preferred_skills / total,
            similarity=self.similarity / total,
            experience_fit=self.experience_fit / total,
            education_fit=self.education_fit / total,
            evidence_quality=self.evidence_quality / total,
        )


@dataclass
class Thresholds:
    """Thresholds for candidate decision bands and knockout rules."""

    shortlist_min: float = 70.0
    review_min: float = 50.0
    knockout_required_coverage: float = 0.30  # Knockout if < 30% required skills
    knockout_score_cap: float = 49.0          # Cap to Rejected band when knocked out


@dataclass
class EvidenceWeights:
    """Multipliers for skill evidence depending on where the skill appears."""

    demonstrated_in_experience_or_projects: float = 1.0
    skills_section_only: float = 0.6
    internship_experience_factor: float = 0.5


@dataclass
class AntiGamingConfig:
    """Thresholds and penalties for detecting keyword stuffing and JD copying."""

    max_single_skill_frequency: int = 8       # Flag if single skill is repeated > 8 times
    max_skill_density_ratio: float = 0.35     # Skill tokens / total tokens threshold (> 35%)
    jd_verbatim_similarity_flag: float = 0.88 # Unnaturally high raw cosine with JD
    stuffing_penalty_points: float = 25.0     # Final score deduction points if flagged


@dataclass
class SystemConfig:
    """Overall system configuration combining scoring, limits, and feature flags."""

    weights: ScoringWeights = field(default_factory=ScoringWeights)
    thresholds: Thresholds = field(default_factory=Thresholds)
    evidence: EvidenceWeights = field(default_factory=EvidenceWeights)
    anti_gaming: AntiGamingConfig = field(default_factory=AntiGamingConfig)

    # File extraction limits
    max_file_size_bytes: int = 5 * 1024 * 1024  # 5 MB
    max_page_count: int = 10

    # Feature flags
    enable_semantic: bool = False
    enable_ocr: bool = False
    mask_pii: bool = True
    enable_fuzzy_matching: bool = True
    fuzzy_match_threshold: int = 92

    # Semantic similarity weight blend (TF-IDF vs Embeddings) when semantic is enabled
    semantic_blend_ratio: float = 0.50  # 50% TF-IDF + 50% Embeddings
