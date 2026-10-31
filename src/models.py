"""Data models and structures for the AI-Based Resume Screening System.

Defines dataclasses for parsed jobs, candidate profiles, skill matches,
detailed score breakdowns, and final screening results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class DecisionBand(str, Enum):
    """Classification bands for screened candidates."""

    SHORTLISTED = "Shortlisted"
    REVIEW = "Review"
    REJECTED = "Rejected"


@dataclass
class SkillMatch:
    """Represents an extracted skill with occurrence metadata and evidence."""

    canonical_name: str
    category: str
    count: int = 1
    locations: List[str] = field(default_factory=list)  # e.g., ["skills", "experience"]
    is_demonstrated: bool = False  # Appears in experience or projects
    matched_variant: str = ""      # The exact phrase found in text


@dataclass
class JobProfile:
    """Parsed representation of a Job Description."""

    title: str = "Unknown Role"
    raw_text: str = ""
    required_skills: List[str] = field(default_factory=list)
    preferred_skills: List[str] = field(default_factory=list)
    min_years_experience: float = 0.0
    max_years_experience: Optional[float] = None
    required_education_level: str = "Any"
    sections: Dict[str, str] = field(default_factory=dict)


@dataclass
class CandidateProfile:
    """Parsed and normalized candidate resume profile."""

    candidate_id: str
    filename: str
    raw_text: str = ""
    cleaned_text: str = ""
    sections: Dict[str, str] = field(default_factory=dict)
    extracted_skills: Dict[str, SkillMatch] = field(default_factory=dict)
    total_years_experience: float = 0.0
    experience_intervals: List[Tuple[str, str, float]] = field(default_factory=list)
    highest_education_level: str = "Unspecified"
    masked_email: str = ""
    masked_phone: str = ""
    is_scanned_or_empty: bool = False
    extraction_warning: Optional[str] = None


@dataclass
class ScoreBreakdown:
    """Explainable component breakdown of a candidate's screening score."""

    # Raw component scores (0 - 100)
    required_skills_score: float = 0.0
    preferred_skills_score: float = 0.0
    similarity_score: float = 0.0
    experience_score: float = 0.0
    education_score: float = 0.0
    evidence_score: float = 0.0

    # Effective weighted contributions (sum to final_score before penalties/caps)
    required_skills_contribution: float = 0.0
    preferred_skills_contribution: float = 0.0
    similarity_contribution: float = 0.0
    experience_contribution: float = 0.0
    education_contribution: float = 0.0
    evidence_contribution: float = 0.0

    raw_total: float = 0.0
    penalty: float = 0.0
    final_score: float = 0.0

    is_knocked_out: bool = False
    knockout_reason: Optional[str] = None
    explanations: List[str] = field(default_factory=list)


@dataclass
class ScreeningResult:
    """Final ranked output for an individual candidate."""

    candidate: CandidateProfile
    score: ScoreBreakdown
    rank: int = 1
    band: DecisionBand = DecisionBand.REVIEW
    anti_gaming_flags: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
