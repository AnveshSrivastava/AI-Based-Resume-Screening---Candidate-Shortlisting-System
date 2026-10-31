"""Unit tests for Phase 6: CSV, Excel, and Markdown exporters."""

import io
import pandas as pd

from src.exporters import (
    export_results_to_dataframe,
    export_to_csv,
    export_to_excel,
    generate_candidate_markdown_summary,
)
from src.models import (
    CandidateProfile,
    DecisionBand,
    ScoreBreakdown,
    ScreeningResult,
    SkillMatch,
)


def _make_dummy_result() -> ScreeningResult:
    cand = CandidateProfile(
        candidate_id="cand_exp_1",
        filename="cand1.pdf",
        total_years_experience=4.0,
        highest_education_level="Master",
        masked_email="[EMAIL PROTECTED]",
        masked_phone="[PHONE PROTECTED]",
        extracted_skills={
            "python": SkillMatch("python", "languages", count=3, is_demonstrated=True),
            "fastapi": SkillMatch("fastapi", "backend", count=2, is_demonstrated=True),
        },
    )
    score = ScoreBreakdown(
        required_skills_score=100.0,
        preferred_skills_score=50.0,
        similarity_score=80.0,
        experience_score=100.0,
        education_score=100.0,
        evidence_score=100.0,
        required_skills_contribution=40.0,
        preferred_skills_contribution=5.0,
        similarity_contribution=16.0,
        experience_contribution=15.0,
        education_contribution=10.0,
        evidence_contribution=5.0,
        raw_total=91.0,
        final_score=91.0,
        explanations=["Matches all required skills.", "4 years experience meets 3 years required."],
    )
    return ScreeningResult(
        candidate=cand,
        score=score,
        rank=1,
        band=DecisionBand.SHORTLISTED,
    )


def test_dataframe_and_csv_export():
    res = _make_dummy_result()
    df = export_results_to_dataframe([res])
    assert len(df) == 1
    assert "Rank" in df.columns
    assert "Final Score" in df.columns
    assert df.iloc[0]["Rank"] == 1
    assert df.iloc[0]["Decision Band"] == "Shortlisted"

    csv_bytes = export_to_csv([res])
    assert len(csv_bytes) > 50
    csv_text = csv_bytes.decode("utf-8")
    assert "cand_exp_1" in csv_text
    assert "Shortlisted" in csv_text


def test_excel_export():
    res = _make_dummy_result()
    excel_bytes = export_to_excel([res])
    assert len(excel_bytes) > 200

    # Verify that openpyxl / pandas can load it back
    loaded_df = pd.read_excel(io.BytesIO(excel_bytes))
    assert len(loaded_df) == 1
    assert loaded_df.iloc[0]["Candidate ID"] == "cand_exp_1"


def test_markdown_summary_generation():
    res = _make_dummy_result()
    md = generate_candidate_markdown_summary(res)
    assert "# Candidate Screening Report: cand_exp_1" in md
    assert "**[SHORTLISTED]**" in md
    assert "91.0 / 100" in md
    assert "Component Score Breakdown" in md
    assert "Matches all required skills." in md
