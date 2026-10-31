"""Export utilities for candidate screening results.

Supports exporting rankings to CSV and Excel (openpyxl) formats,
as well as generating individual candidate Markdown summary reports.
Masks PII by default unless explicitly configured otherwise.
"""

from __future__ import annotations

import io
from typing import List

import pandas as pd

from src.models import ScreeningResult


def export_results_to_dataframe(
    results: List[ScreeningResult],
    include_pii: bool = False,
) -> pd.DataFrame:
    """Convert a list of ScreeningResult objects into a flattened pandas DataFrame."""
    rows = []
    for res in results:
        cand = res.candidate
        score = res.score

        # Extract matched and missing skills
        matched_skills = sorted(list(cand.extracted_skills.keys()))
        email_display = cand.masked_email if not include_pii else cand.masked_email
        phone_display = cand.masked_phone if not include_pii else cand.masked_phone

        rows.append({
            "Rank": res.rank,
            "Candidate ID": cand.candidate_id,
            "Filename": cand.filename,
            "Decision Band": res.band.value,
            "Final Score": score.final_score,
            "Required Skills Score": score.required_skills_score,
            "Preferred Skills Score": score.preferred_skills_score,
            "Similarity Score": score.similarity_score,
            "Experience Score": score.experience_score,
            "Education Score": score.education_score,
            "Evidence Score": score.evidence_score,
            "Penalty Deducted": score.penalty,
            "Knockout Applied": "Yes" if score.is_knocked_out else "No",
            "Knockout Reason": score.knockout_reason or "",
            "Total Exp (Years)": cand.total_years_experience,
            "Education Level": cand.highest_education_level,
            "Extracted Skills Count": len(matched_skills),
            "Extracted Skills": ", ".join(matched_skills),
            "Anti-Gaming Flags": "; ".join(res.anti_gaming_flags) if res.anti_gaming_flags else "None",
            "Warnings": "; ".join(res.warnings) if res.warnings else "None",
            "Email": email_display,
            "Phone": phone_display,
        })

    return pd.DataFrame(rows)


def export_to_csv(results: List[ScreeningResult], include_pii: bool = False) -> bytes:
    """Export screening results to CSV byte stream."""
    df = export_results_to_dataframe(results, include_pii=include_pii)
    csv_str = df.to_csv(index=False, encoding="utf-8")
    return csv_str.encode("utf-8")


def export_to_excel(results: List[ScreeningResult], include_pii: bool = False) -> bytes:
    """Export screening results to styled Excel byte stream using openpyxl."""
    df = export_results_to_dataframe(results, include_pii=include_pii)
    buf = io.BytesIO()

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Candidate Rankings", index=False)

    return buf.getvalue()


def generate_candidate_markdown_summary(result: ScreeningResult) -> str:
    """Generate a clean, professional one-page Markdown report for a candidate."""
    cand = result.candidate
    score = result.score

    band_badge = f"**[{result.band.value.upper()}]**"
    knockout_alert = f"\n> ⚠️ **Knockout Warning**: {score.knockout_reason}\n" if score.is_knocked_out else ""
    warnings_section = ""
    if result.warnings:
        warnings_section = "\n### System Warnings & Flags\n" + "\n".join(f"- {w}" for w in result.warnings)

    skills_list = ", ".join(f"`{s}`" for s in sorted(cand.extracted_skills.keys())) or "None detected"

    md = f"""# Candidate Screening Report: {cand.candidate_id}

- **Source File:** `{cand.filename}`
- **Assigned Rank:** #{result.rank}
- **Decision Band:** {band_badge}
- **Final Score:** `{score.final_score:.1f} / 100` (Raw: `{score.raw_total:.1f}`, Penalty: `-{score.penalty:.1f}`)
- **Contact:** Email: `{cand.masked_email}` | Phone: `{cand.masked_phone}`
{knockout_alert}
---

### Component Score Breakdown
| Component | Score (0-100) | Weight | Contribution |
| :--- | :---: | :---: | :---: |
| Required Skills Coverage | {score.required_skills_score:.1f}% | 40% | +{score.required_skills_contribution:.2f} pts |
| Preferred Skills Coverage | {score.preferred_skills_score:.1f}% | 10% | +{score.preferred_skills_contribution:.2f} pts |
| Content Similarity | {score.similarity_score:.1f}% | 20% | +{score.similarity_contribution:.2f} pts |
| Experience Fit | {score.experience_score:.1f}% | 15% | +{score.experience_contribution:.2f} pts |
| Education Fit | {score.education_score:.1f}% | 10% | +{score.education_contribution:.2f} pts |
| Evidence Quality | {score.evidence_score:.1f}% | 5% | +{score.evidence_contribution:.2f} pts |
| **Total Effective Score** | | **100%** | **{score.final_score:.1f} pts** |

---

### Candidate Profile Summary
- **Total Estimated Experience:** `{cand.total_years_experience:.1f} years`
- **Highest Detected Education:** `{cand.highest_education_level}`
- **Extracted Skills ({len(cand.extracted_skills)}):** {skills_list}

### Evaluator Reasons & Evidence
{chr(10).join(f"- {exp}" for exp in score.explanations)}
{warnings_section}

---
*Note: This report is generated as automated decision support for human recruiters and does not constitute an autonomous hiring decision.*
"""
    return md
