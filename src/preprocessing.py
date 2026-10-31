"""Text preprocessing and section segmentation module.

Normalizes whitespace, Unicode bullets, and special punctuation,
and partitions raw resume or JD text into canonical sections (Summary, Skills,
Experience, Projects, Education, Certifications).
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple


SECTION_SYNONYMS: Dict[str, List[str]] = {
    "summary": [
        "professional summary",
        "career summary",
        "executive summary",
        "summary of qualifications",
        "summary",
        "profile",
        "about me",
        "objective",
        "career objective",
        "overview",
    ],
    "skills": [
        "technical skills",
        "core skills",
        "key skills",
        "skills & competencies",
        "skills & abilities",
        "skills & tools",
        "skills and tools",
        "technical expertise",
        "technical proficiencies",
        "technical proficiency",
        "technologies",
        "tech stack",
        "core competencies",
        "competencies",
        "skills",
    ],
    "experience": [
        "work experience",
        "professional experience",
        "employment history",
        "work history",
        "experience",
        "industry experience",
        "relevant experience",
        "internship experience",
        "internships",
    ],
    "projects": [
        "academic projects",
        "personal projects",
        "key projects",
        "technical projects",
        "selected projects",
        "notable projects",
        "projects",
    ],
    "education": [
        "education",
        "educational background",
        "academic background",
        "educational qualifications",
        "academic qualifications",
        "qualifications",
        "academics",
    ],
    "certifications": [
        "certifications",
        "licenses & certifications",
        "certifications & licenses",
        "certifications & courses",
        "certificates",
        "achievements",
        "awards & achievements",
    ],
}


def clean_text(raw_text: str) -> str:
    """Normalize whitespace, unicode bullets, tabs, and line endings.

    Args:
        raw_text: The uncleaned text extracted from a document.

    Returns:
        Cleaned, normalized text.
    """
    if not raw_text:
        return ""

    # Replace special bullet points with standard hyphens or spaces
    cleaned = re.sub(r"[\u2022\u2023\u2043\u2219\u25cf\u25cb\u25aa\u25ab\u25fe\u25fd·▪■◆]", " - ", raw_text)

    # Normalize non-breaking spaces and irregular unicode whitespace
    cleaned = re.sub(r"[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]", " ", cleaned)

    # Convert Windows CRLF and carriage returns to standard LF
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse horizontal whitespace
    cleaned = re.sub(r"[ \t]+", " ", cleaned)

    # Collapse 3+ consecutive newlines into two
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def split_into_sections(text: str) -> Dict[str, str]:
    """Segment a resume or job description into canonical sections.

    Uses line-boundary heading heuristics and keyword matching against
    known section synonyms. Text preceding the first detected heading is
    stored under 'summary' or 'header'.

    Args:
        text: Normalized or raw document text.

    Returns:
        Dictionary mapping canonical section names to the text of each section.
    """
    if not text:
        return {}

    lines = text.split("\n")
    sections: Dict[str, List[str]] = {}
    current_section = "header"
    sections[current_section] = []

    # Compile heading lookup mapping (lowercased pattern -> canonical section name)
    heading_lookup: List[Tuple[str, str]] = []
    for canonical, synonyms in SECTION_SYNONYMS.items():
        for syn in synonyms:
            heading_lookup.append((syn, canonical))
    # Sort by phrase length descending
    heading_lookup.sort(key=lambda x: len(x[0]), reverse=True)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if sections[current_section]:
                sections[current_section].append("")
            continue

        # Check if line looks like a section header
        detected_section = _detect_heading(stripped, heading_lookup)
        if detected_section:
            current_section = detected_section
            if current_section not in sections:
                sections[current_section] = []
        else:
            sections[current_section].append(stripped)

    # Clean up and join lines
    result: Dict[str, str] = {}
    for sec_name, sec_lines in sections.items():
        sec_content = "\n".join(sec_lines).strip()
        if sec_content:
            result[sec_name] = sec_content

    return result


def _detect_heading(line: str, heading_lookup: List[Tuple[str, str]]) -> str | None:
    """Determine if a line is a section heading."""
    # Headings are typically short (< 60 chars) and do not end in periods or commas
    if len(line) > 60:
        return None

    cleaned_line = re.sub(r"[:\-_#=*~]+$", "", line).strip().lower()
    cleaned_line = re.sub(r"^[:\-_#=*~]+", "", cleaned_line).strip()

    if not cleaned_line:
        return None

    for syn, canonical in heading_lookup:
        # Match exact line or "syn: ..."
        if cleaned_line == syn or cleaned_line.startswith(f"{syn}:") or cleaned_line.startswith(f"{syn} -"):
            return canonical

    return None
