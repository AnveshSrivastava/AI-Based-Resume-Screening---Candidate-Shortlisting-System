"""Unit tests for Phase 4: Job description and resume parsers."""

from src.config import SystemConfig
from src.job_parser import parse_job_description
from src.resume_parser import (
    estimate_years_of_experience,
    mask_pii_in_text,
    parse_resume,
)


def test_job_parser_with_headings():
    jd_text = """
Job Title: Senior Backend Engineer

REQUIRED QUALIFICATIONS:
- 3+ years of software development experience.
- Strong proficiency in Python, FastAPI, and Docker.
- Experience with PostgreSQL and REST APIs.
- Bachelor's degree in Computer Science or equivalent.

PREFERRED QUALIFICATIONS:
- Hands-on experience with Kubernetes and AWS.
- Familiarity with CI/CD pipelines.
"""
    job = parse_job_description(jd_text)

    assert "Senior Backend Engineer" in job.title
    assert job.min_years_experience == 3.0
    assert job.required_education_level == "Bachelor"

    # Check required skills
    assert "python" in job.required_skills
    assert "fastapi" in job.required_skills
    assert "docker" in job.required_skills
    assert "postgresql" in job.required_skills
    assert "rest api" in job.required_skills

    # Check preferred skills
    assert "kubernetes" in job.preferred_skills
    assert "aws" in job.preferred_skills
    assert "ci/cd" in job.preferred_skills

    # Ensure required and preferred sets are disjoint
    assert set(job.required_skills).isdisjoint(set(job.preferred_skills))


def test_job_parser_no_headings():
    jd_text = """
Full Stack Developer
We are looking for an engineer proficient in React, Node.js, and MongoDB.
Minimum 2 years of industry experience required. B.Tech degree required.
"""
    job = parse_job_description(jd_text)
    assert job.min_years_experience == 2.0
    assert job.required_education_level == "Bachelor"
    assert "react" in job.required_skills
    assert "node.js" in job.required_skills
    assert "mongodb" in job.required_skills
    assert len(job.preferred_skills) == 0  # No headings -> all required


def test_experience_estimation_overlapping_dates():
    config = SystemConfig()
    text = """
WORK EXPERIENCE
Software Engineer at Acme Corp
Jan 2020 - Dec 2021
- Developed backend microservices.

Consultant at GlobalTech
Jun 2021 - Dec 2022
- Cloud deployment and architecture.
"""
    # Acme: 2020.0 to 2021.92 (~2.0 yrs)
    # Global: 2021.42 to 2022.92 (~1.5 yrs)
    # Merged interval: 2020.0 to 2022.92 (~2.9 - 3.0 years, not 3.5 years!)
    total_exp, intervals = estimate_years_of_experience(text, {"experience": text}, config)
    assert 2.8 <= total_exp <= 3.1
    assert len(intervals) == 1  # Successfully merged into 1 continuous interval


def test_experience_internship_discount():
    config = SystemConfig()
    text = """
WORK EXPERIENCE
Software Engineering Intern at StartupInc
Jan 2022 - Dec 2022
- Built automated tests.
"""
    # 1 full year intern -> 0.5 years at 50% discount
    total_exp, intervals = estimate_years_of_experience(text, {"experience": text}, config)
    assert abs(total_exp - 0.5) < 0.15


def test_pii_masking():
    raw_text = "Contact Alice at alice.smith@example.com or +1-555-123-4567. Alternate: 9876543210."
    masked = mask_pii_in_text(raw_text)

    assert "alice.smith@example.com" not in masked
    assert "[EMAIL PROTECTED]" in masked
    assert "555-123-4567" not in masked
    assert "[PHONE PROTECTED]" in masked


def test_resume_parser_integration():
    resume_text = """
Alice Walker
alice.w@domain.com | (555) 019-2834

SUMMARY
Backend engineer with 4 years building scalable services.

TECHNICAL SKILLS
Python, FastAPI, Docker, PostgreSQL, Redis, Git

WORK EXPERIENCE
Backend Engineer | CloudTech
Jan 2022 - Present
- Designed high volume APIs using FastAPI and PostgreSQL.
- Deployed microservices to Docker.

EDUCATION
Master of Science in Computer Science | State University (2020 - 2022)
"""
    cand = parse_resume(resume_text, filename="alice.pdf", candidate_id="cand_101")

    assert cand.candidate_id == "cand_101"
    assert cand.filename == "alice.pdf"
    assert cand.highest_education_level == "Master"
    assert cand.masked_email == "[EMAIL PROTECTED]"
    assert cand.masked_phone == "[PHONE PROTECTED]"
    assert "python" in cand.extracted_skills
    assert "fastapi" in cand.extracted_skills
    assert cand.extracted_skills["fastapi"].is_demonstrated is True
    assert cand.total_years_experience >= 3.5
