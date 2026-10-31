"""Job Description (JD) parser module.

Extracts job title, required vs preferred skills, minimum and maximum years
of experience, and education qualifications from raw JD text.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from src.config import SystemConfig
from src.models import JobProfile
from src.preprocessing import clean_text
from src.skills import extract_skills_from_text


logger = logging.getLogger(__name__)

# Section markers for required vs preferred qualifications
REQUIRED_HEADINGS = [
    r"required\s*(?:skills|qualifications|experience)?",
    r"must\s*have",
    r"minimum\s*(?:skills|qualifications|requirements)",
    r"basic\s*(?:skills|qualifications|requirements)",
    r"what\s*you(?:'ll)?\s*need",
    r"what\s*we(?:'re)?\s*looking\s*for",
    r"essential\s*(?:skills|qualifications)?",
    r"key\s*responsibilities\s*and\s*requirements",
    r"role\s*requirements",
    r"requirements",
]

PREFERRED_HEADINGS = [
    r"preferred\s*(?:skills|qualifications|experience)?",
    r"nice\s*to\s*have",
    r"good\s*to\s*have",
    r"bonus\s*(?:points|skills)?",
    r"desired\s*(?:skills|qualifications)?",
    r"plus(?:es)?",
    r"what\s*gives\s*you\s*an\s*edge",
]

EDUCATION_LEVEL_KEYWORDS = [
    ("PhD", [r"\bph\.?d\b", r"\bdoctorate\b", r"\bdoctoral\b"]),
    ("Master", [r"\bm\.?tech\b", r"\bm\.?s\b", r"\bmca\b", r"\bmba\b", r"\bmaster(?:'s)?\b"]),
    ("Bachelor", [r"\bb\.?tech\b", r"\bb\.?e\b", r"\bbca\b", r"\bb\.?s\b", r"\bbachelor(?:'s)?\b", r"\bundergraduate\b"]),
]


def parse_job_description(
    text: str,
    config: Optional[SystemConfig] = None,
) -> JobProfile:
    """Parse a job description into a structured JobProfile.

    Args:
        text: Raw job description text.
        config: System configuration and feature flags.

    Returns:
        Structured JobProfile with required/preferred skills, experience, and education.
    """
    cleaned = clean_text(text)
    if not cleaned:
        return JobProfile(title="Empty JD", raw_text="")

    cfg = config or SystemConfig()

    title = _extract_job_title(cleaned)
    min_exp, max_exp = _extract_experience_years(cleaned)
    edu_level = _extract_education_level(cleaned)
    req_skills, pref_skills, sections = _partition_skills_by_requirements(cleaned, cfg)

    return JobProfile(
        title=title,
        raw_text=cleaned,
        required_skills=req_skills,
        preferred_skills=pref_skills,
        min_years_experience=min_exp,
        max_years_experience=max_exp,
        required_education_level=edu_level,
        sections=sections,
    )


def _extract_job_title(text: str) -> str:
    """Extract job title from the beginning of the text or explicit label."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return "Unknown Role"

    # Check for explicit 'Job Title:', 'Position:', 'Role:'
    for line in lines[:10]:
        match = re.match(r"^(?:job\s*title|position|role|title)\s*[:\-]\s*(.+)$", line, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Heuristic: the first non-empty line if it is reasonably short (< 60 chars)
    first_line = lines[0]
    if len(first_line) < 60 and not re.search(r"\b(about us|company|overview|description)\b", first_line, re.IGNORECASE):
        return first_line

    return "Software Engineer"


def _extract_experience_years(text: str) -> Tuple[float, Optional[float]]:
    """Extract minimum and optional maximum years of required experience."""
    patterns = [
        # "3 - 5 years", "3 to 5 years"
        r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:\+)?\s*years?",
        # "3+ years", "3+ yrs"
        r"(\d+(?:\.\d+)?)\s*\+\s*years?",
        # "minimum 3 years", "at least 3 years", "min 3 years"
        r"(?:minimum|min|at\s*least)\s*(?:of)?\s*(\d+(?:\.\d+)?)\s*years?",
        # "3 years of experience", "3 years experience"
        r"(\d+(?:\.\d+)?)\s*years?\s*(?:of)?\s*(?:relevant|industry|work)?\s*experience",
    ]

    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            try:
                min_val = float(groups[0])
                max_val = float(groups[1]) if len(groups) > 1 and groups[1] is not None else None
                # Sanity check: years between 0 and 25
                if 0.0 <= min_val <= 25.0:
                    return min_val, max_val
            except (ValueError, TypeError):
                continue

    return 0.0, None


def _extract_education_level(text: str) -> str:
    """Detect required degree or educational qualification."""
    lower = text.lower()
    for level, patterns in EDUCATION_LEVEL_KEYWORDS:
        for pat in patterns:
            if re.search(pat, lower):
                return level
    return "Any"


def _partition_skills_by_requirements(
    text: str,
    cfg: SystemConfig,
) -> Tuple[List[str], List[str], Dict[str, str]]:
    """Divide text into required and preferred sections and extract skills."""
    lines = text.split("\n")
    required_lines: List[str] = []
    preferred_lines: List[str] = []
    other_lines: List[str] = []

    req_pattern = re.compile(rf"^({'|'.join(REQUIRED_HEADINGS)})[:\s\-_]*$", re.IGNORECASE)
    pref_pattern = re.compile(rf"^({'|'.join(PREFERRED_HEADINGS)})[:\s\-_]*$", re.IGNORECASE)

    current_mode: str = "other"  # 'required', 'preferred', or 'other'
    has_explicit_sections = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if req_pattern.match(stripped):
            current_mode = "required"
            has_explicit_sections = True
            continue
        elif pref_pattern.match(stripped):
            current_mode = "preferred"
            has_explicit_sections = True
            continue
        elif re.match(r"^[A-Z\s]{4,30}[:\-]?$", stripped):  # Other section heading
            current_mode = "other"

        if current_mode == "required":
            required_lines.append(stripped)
        elif current_mode == "preferred":
            preferred_lines.append(stripped)
        else:
            other_lines.append(stripped)

    # If no explicit required/preferred headings found, treat all extracted skills as required
    if not has_explicit_sections:
        all_skills_dict = extract_skills_from_text(text, config=cfg)
        return sorted(list(all_skills_dict.keys())), [], {"body": text}

    req_text = "\n".join(required_lines)
    pref_text = "\n".join(preferred_lines)

    req_skills_dict = extract_skills_from_text(req_text, config=cfg)
    pref_skills_dict = extract_skills_from_text(pref_text, config=cfg)

    # Any preferred skill that was already marked required should remain required
    req_skills = sorted(list(req_skills_dict.keys()))
    pref_skills = sorted([s for s in pref_skills_dict.keys() if s not in req_skills_dict])

    sections = {
        "required": req_text,
        "preferred": pref_text,
        "other": "\n".join(other_lines),
    }

    return req_skills, pref_skills, sections
