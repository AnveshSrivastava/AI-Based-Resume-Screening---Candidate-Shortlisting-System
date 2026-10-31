"""Resume parser module for extracting skills, work experience, education, and masking PII.

Parses text into sections, calculates total experience by merging overlapping
date intervals, scales internship experience, identifies highest education,
and ensures privacy by masking sensitive personally identifiable information (PII).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.config import SystemConfig
from src.models import CandidateProfile, SkillMatch
from src.preprocessing import clean_text, split_into_sections
from src.skills import extract_skills_from_text


logger = logging.getLogger(__name__)

CURRENT_YEAR = 2026
CURRENT_MONTH = 10

MONTHS_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

MONTH_REGEX_PART = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|\d{1,2})"

EDUCATION_HIERARCHY = [
    ("PhD", [r"\bph\.?d\b", r"\bdoctorate\b", r"\bdoctoral\b"]),
    ("Master", [r"\bm\.?tech\b", r"\bm\.?s\b", r"\bmca\b", r"\bmba\b", r"\bm\.?sc\b", r"\bmaster(?:'s)?\b"]),
    ("Bachelor", [r"\bb\.?tech\b", r"\bb\.?e\b", r"\bbca\b", r"\bb\.?s\b", r"\bb\.?sc\b", r"\bbachelor(?:'s)?\b"]),
    ("Diploma", [r"\bdiploma\b", r"\bpolytechnic\b", r"\bassociate(?:'s)?\b"]),
    ("High School", [r"\bhigh\s*school\b", r"\b12th\b", r"\bsenior\s*secondary\b"]),
]


def mask_pii_in_text(text: str) -> str:
    """Mask email addresses and phone numbers in raw text for privacy."""
    if not text:
        return ""

    # Mask email addresses
    masked = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[EMAIL PROTECTED]",
        text,
    )

    # Mask phone numbers (international, US, and 10-digit formats)
    masked = re.sub(
        r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "[PHONE PROTECTED]",
        masked,
    )
    masked = re.sub(
        r"(?:\+91[\-\s]?)?[6789]\d{9}\b",
        "[PHONE PROTECTED]",
        masked,
    )

    return masked


def extract_pii(text: str) -> Tuple[str, str]:
    """Extract raw email and phone number before masking."""
    email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
    phone_match = re.search(r"((?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\b(?:\+91[\-\s]?)?[6789]\d{9}\b)", text)

    email = email_match.group(0) if email_match else ""
    phone = phone_match.group(0) if phone_match else ""
    return email, phone


def parse_resume(
    raw_text: str,
    filename: str = "resume.pdf",
    candidate_id: str = "cand_01",
    config: Optional[SystemConfig] = None,
    is_scanned_or_empty: bool = False,
    extraction_warning: Optional[str] = None,
) -> CandidateProfile:
    """Parse resume text into a structured CandidateProfile.

    Args:
        raw_text: Full raw text extracted from file.
        filename: Source filename.
        candidate_id: Unique candidate identifier.
        config: System configuration and feature flags.
        is_scanned_or_empty: Flag indicating unreadable document.
        extraction_warning: Extraction warning message if any.

    Returns:
        Structured CandidateProfile.
    """
    cfg = config or SystemConfig()
    cleaned = clean_text(raw_text)

    email, phone = extract_pii(cleaned)
    masked_email = "[EMAIL PROTECTED]" if email else "N/A"
    masked_phone = "[PHONE PROTECTED]" if phone else "N/A"

    if is_scanned_or_empty or not cleaned:
        return CandidateProfile(
            candidate_id=candidate_id,
            filename=filename,
            raw_text=raw_text,
            cleaned_text="",
            is_scanned_or_empty=True,
            extraction_warning=extraction_warning or "File contains no readable text.",
            masked_email=masked_email,
            masked_phone=masked_phone,
        )

    sections = split_into_sections(cleaned)
    skills = extract_skills_from_text(cleaned, sections=sections, config=cfg)
    total_exp, intervals = estimate_years_of_experience(cleaned, sections, cfg)
    highest_edu = detect_highest_education(cleaned, sections)

    return CandidateProfile(
        candidate_id=candidate_id,
        filename=filename,
        raw_text=raw_text,
        cleaned_text=cleaned,
        sections=sections,
        extracted_skills=skills,
        total_years_experience=total_exp,
        experience_intervals=intervals,
        highest_education_level=highest_edu,
        masked_email=masked_email,
        masked_phone=masked_phone,
        is_scanned_or_empty=False,
        extraction_warning=extraction_warning,
    )


def estimate_years_of_experience(
    full_text: str,
    sections: Dict[str, str],
    config: SystemConfig,
) -> Tuple[float, List[Tuple[str, str, float]]]:
    """Estimate total years of experience by extracting and merging date ranges.

    Merges overlapping intervals so concurrent roles do not artificially inflate
    experience. Internships are discounted by the configurable factor (default 50%).
    """
    # Prefer searching the experience section if available, else full text
    target_text = sections.get("experience", full_text)

    # Date range pattern: e.g. "Jan 2020 - Dec 2022", "2019 - Present", "06/2021 – 08/2023"
    date_range_pattern = re.compile(
        rf"(?:({MONTH_REGEX_PART})[\s/,\.-]+)?(20\d{{2}}|19\d{{2}})\s*(?:-|–|—|to)\s*(?:({MONTH_REGEX_PART})[\s/,\.-]+)?(20\d{{2}}|19\d{{2}}|present|current|now)",
        re.IGNORECASE,
    )

    intervals: List[Tuple[float, float, bool, str, str]] = []

    lines = target_text.split("\n")
    for idx, line in enumerate(lines):
        # Look around surrounding lines (window of +/- 1 line) for internship markers
        context_window = " ".join(lines[max(0, idx - 1) : min(len(lines), idx + 2)])
        is_internship = bool(re.search(r"\b(?:intern|internship|trainee|apprentice)\b", context_window, re.IGNORECASE))
        for match in date_range_pattern.finditer(line):
            sm_str, sy_str, em_str, ey_str = match.groups()
            try:
                start_year = float(sy_str)
                start_month = _parse_month(sm_str)

                ey_lower = ey_str.lower().strip()
                if ey_lower in ("present", "current", "now"):
                    end_year = float(CURRENT_YEAR)
                    end_month = float(CURRENT_MONTH)
                else:
                    end_year = float(ey_lower)
                    end_month = _parse_month(em_str)

                # Validation bounds
                if not (1975 <= start_year <= CURRENT_YEAR + 1):
                    continue
                if not (1975 <= end_year <= CURRENT_YEAR + 1):
                    continue

                start_val = start_year + (start_month - 1) / 12.0
                end_val = end_year + (end_month - 1) / 12.0

                if end_val >= start_val:
                    intervals.append((
                        start_val,
                        end_val,
                        is_internship,
                        f"{sm_str or ''} {sy_str}".strip(),
                        ey_str.strip(),
                    ))
            except (ValueError, TypeError):
                continue

    if not intervals:
        return 0.0, []

    # Sort intervals by start time
    intervals.sort(key=lambda x: x[0])

    # Merge overlapping intervals
    merged_intervals: List[Tuple[float, float, bool]] = []
    for start, end, is_intern, _, _ in intervals:
        if not merged_intervals:
            merged_intervals.append((start, end, is_intern))
        else:
            prev_start, prev_end, prev_intern = merged_intervals[-1]
            if start <= prev_end:  # Overlap or continuous
                new_end = max(prev_end, end)
                # If either role is full-time, the merged interval counts as full-time
                combined_intern = prev_intern and is_intern
                merged_intervals[-1] = (prev_start, new_end, combined_intern)
            else:
                merged_intervals.append((start, end, is_intern))

    total_years = 0.0
    display_intervals: List[Tuple[str, str, float]] = []

    for start, end, is_intern in merged_intervals:
        dur = end - start
        multiplier = config.evidence.internship_experience_factor if is_intern else 1.0
        eff_dur = dur * multiplier
        total_years += eff_dur
        display_intervals.append((f"{start:.1f}", f"{end:.1f}", round(eff_dur, 2)))

    # Cap to realistic career bound (e.g. 40 years)
    final_years = round(min(total_years, 40.0), 1)
    return final_years, display_intervals


def _parse_month(month_str: Optional[str]) -> int:
    """Parse month name or number to 1-12 integer."""
    if not month_str:
        return 1
    m_clean = month_str.strip().lower()
    if m_clean.isdigit():
        val = int(m_clean)
        return val if 1 <= val <= 12 else 1
    return MONTHS_MAP.get(m_clean, 1)


def detect_highest_education(full_text: str, sections: Dict[str, str]) -> str:
    """Detect highest educational qualification using domain hierarchy."""
    edu_text = sections.get("education", full_text).lower()

    for degree, patterns in EDUCATION_HIERARCHY:
        for pat in patterns:
            if re.search(pat, edu_text):
                return degree

    return "Unspecified"
