"""Unit tests for Phase 2: Skill taxonomy and extraction engine."""

from src.config import SystemConfig
from src.skills import (
    compute_skill_evidence_multiplier,
    extract_skills_from_text,
    get_taxonomy,
)


def test_taxonomy_loading():
    tax = get_taxonomy()
    assert len(tax.token_to_canonical) > 150
    assert "python" in tax.token_to_canonical
    assert "cpp" in tax.token_to_canonical
    assert tax.token_to_canonical["cpp"][0] == "c++"


def test_special_character_skills():
    text = (
        "Experienced software engineer with deep expertise in C++, C#, and .NET Core. "
        "Built microservices with Node.js and automated pipelines using CI/CD."
    )
    skills = extract_skills_from_text(text)
    assert "c++" in skills, "Failed to extract C++"
    assert "c#" in skills, "Failed to extract C#"
    assert ".net" in skills, "Failed to extract .NET"
    assert "node.js" in skills, "Failed to extract Node.js"
    assert "ci/cd" in skills, "Failed to extract CI/CD"


def test_java_not_matching_javascript():
    text = "Front-end developer specializing in JavaScript and React. No backend knowledge."
    skills = extract_skills_from_text(text)
    assert "javascript" in skills
    assert "java" not in skills, "CRITICAL: 'java' must never match inside 'javascript'"

    # Also test javadoc
    text2 = "Wrote comprehensive Javadoc documentation for the module."
    skills2 = extract_skills_from_text(text2)
    assert "java" not in skills2


def test_rest_api_and_aliases():
    text = (
        "Designed REST APIs and restful services for mobile apps. "
        "Also used Postgres, K8s, and PyTorch."
    )
    skills = extract_skills_from_text(text)
    assert "rest api" in skills
    assert "postgresql" in skills  # Aliased from Postgres
    assert "kubernetes" in skills  # Aliased from K8s
    assert "pytorch" in skills


def test_fuzzy_matching_typos():
    config = SystemConfig(enable_fuzzy_matching=True, fuzzy_match_threshold=90)
    text = "Deployed containers with dockr and managed clusters with kubernets."
    skills = extract_skills_from_text(text, config=config)
    assert "docker" in skills
    assert "kubernetes" in skills


def test_fuzzy_matching_never_corrupts_short_words():
    # 'java' must never turn into 'javascript' or vice versa
    text = "We write standard java code."
    skills = extract_skills_from_text(text)
    assert "java" in skills
    assert "javascript" not in skills


def test_evidence_weighting_sections():
    sections = {
        "skills": "Python, Docker, AWS, React",
        "experience": (
            "Senior Backend Developer: Architected distributed microservices in Python. "
            "Led AWS cloud migration with Docker containerization."
        ),
        "education": "B.Tech in Computer Science",
    }
    text = "\n".join(sections.values())
    skills = extract_skills_from_text(text, sections=sections)

    # Python, Docker, AWS appear in experience -> is_demonstrated True
    assert skills["python"].is_demonstrated is True
    assert compute_skill_evidence_multiplier(skills["python"]) == 1.0

    assert skills["aws"].is_demonstrated is True
    assert compute_skill_evidence_multiplier(skills["aws"]) == 1.0

    # React only appears in skills section -> is_demonstrated False
    assert skills["react"].is_demonstrated is False
    assert compute_skill_evidence_multiplier(skills["react"]) == 0.6
