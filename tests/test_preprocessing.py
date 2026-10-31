"""Unit tests for Phase 3: Text preprocessing and section segmentation."""

from src.preprocessing import clean_text, split_into_sections


def test_clean_text_bullets_and_whitespace():
    raw = "• Python programming\n▪ Machine learning\n\n\n\t\xa0AWS cloud   engineering\n\r\nEnd"
    cleaned = clean_text(raw)
    assert "•" not in cleaned
    assert "▪" not in cleaned
    assert "\xa0" not in cleaned
    assert "\r" not in cleaned
    assert "Python programming" in cleaned
    assert "AWS cloud engineering" in cleaned


def test_split_into_sections():
    sample_resume = """
John Doe
Software Engineer | john@example.com

SUMMARY
Passionate engineer with 4 years building scalable services.

TECHNICAL SKILLS
Python, FastAPI, Docker, Kubernetes, PostgreSQL

WORK EXPERIENCE
Senior Backend Engineer at TechCorp (2021 - Present)
- Built high throughput APIs with FastAPI.
- Deployed services to AWS.

EDUCATION
B.Tech in Computer Science from XYZ University (2017 - 2021)

PROJECTS
E-Commerce API: Built distributed order system with Kafka.
"""
    sections = split_into_sections(sample_resume)

    assert "summary" in sections
    assert "skills" in sections
    assert "experience" in sections
    assert "education" in sections
    assert "projects" in sections

    assert "FastAPI" in sections["skills"]
    assert "TechCorp" in sections["experience"]
    assert "XYZ University" in sections["education"]
    assert "Kafka" in sections["projects"]
