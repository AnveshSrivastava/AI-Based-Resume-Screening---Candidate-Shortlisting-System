"""Streamlit Web UI for AI-Based Resume Screening and Candidate Shortlisting System.

Provides an interactive recruiter dashboard with 5 tabs:
1. Job Description (upload/paste/select with interactive requirements editor)
2. Upload Resumes (in-memory processing of PDF/DOCX/TXT + bundled samples)
3. Results & Ranking (KPI cards, charts, colour-coded tables, candidate expanders, exports)
4. Compare (side-by-side metrics and 6-axis Plotly radar chart)
5. About & Methodology (scoring math, ethics, architecture overview)
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config import (
    DATA_DIR,
    SAMPLE_JDS_DIR,
    SAMPLE_RESUMES_DIR,
    ScoringWeights,
    SystemConfig,
    Thresholds,
)
from src.exporters import (
    export_to_csv,
    export_to_excel,
    generate_candidate_markdown_summary,
)
from src.job_parser import parse_job_description
from src.models import CandidateProfile, DecisionBand, JobProfile, ScreeningResult
from src.ranker import rank_and_classify_candidates
from src.resume_parser import parse_resume
from src.similarity import SimilarityEngine
from src.text_extraction import extract_text_from_file


# Page configuration
st.set_page_config(
    page_title="AI Resume Screening & Shortlisting System",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS styling
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 16px;
        border-left: 4px solid #1f77b4;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .badge-shortlist {
        background-color: #d4edda;
        color: #155724;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-review {
        background-color: #fff3cd;
        color: #856404;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-rejected {
        background-color: #f8d7da;
        color: #721c24;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .skill-chip {
        display: inline-block;
        padding: 2px 8px;
        margin: 2px;
        border-radius: 4px;
        font-size: 0.82rem;
        font-weight: 500;
    }
    .chip-req-match { background-color: #c3e6cb; color: #155724; border: 1px solid #8fd19e; }
    .chip-pref-match { background-color: #b8daff; color: #004085; border: 1px solid #7abaff; }
    .chip-missing { background-color: #f5c6cb; color: #721c24; border: 1px solid #f1b0b7; }
    .chip-other { background-color: #e2e3e5; color: #383d41; border: 1px solid #d6d8db; }
    </style>
    """,
    unsafe_allow_html=True,
)


def init_session_state() -> None:
    """Initialize Streamlit session state variables."""
    if "config" not in st.session_state:
        st.session_state.config = SystemConfig()
    if "job_profile" not in st.session_state:
        st.session_state.job_profile = None
    if "candidates" not in st.session_state:
        st.session_state.candidates = []
    if "similarities" not in st.session_state:
        st.session_state.similarities = []
    if "results" not in st.session_state:
        st.session_state.results = []
    if "jd_text" not in st.session_state:
        st.session_state.jd_text = ""


init_session_state()


# ==============================================================================
# SIDEBAR CONTROLS
# ==============================================================================
with st.sidebar:
    st.title("⚙️ System Controls")
    st.caption("Adjustable weights, thresholds & feature flags")

    # Reset button
    if st.button("🔄 Reset to Defaults", use_container_width=True):
        st.session_state.config = SystemConfig()
        st.rerun()

    st.markdown("---")
    st.subheader("⚖️ Scoring Weights (Total: 100%)")
    w_req = st.slider("Required Skills", 0, 100, int(st.session_state.config.weights.required_skills * 100), 5)
    w_pref = st.slider("Preferred Skills", 0, 100, int(st.session_state.config.weights.preferred_skills * 100), 5)
    w_sim = st.slider("Text Similarity", 0, 100, int(st.session_state.config.weights.similarity * 100), 5)
    w_exp = st.slider("Experience Fit", 0, 100, int(st.session_state.config.weights.experience_fit * 100), 5)
    w_edu = st.slider("Education Fit", 0, 100, int(st.session_state.config.weights.education_fit * 100), 5)
    w_evid = st.slider("Evidence Quality", 0, 100, int(st.session_state.config.weights.evidence_quality * 100), 5)

    # Auto-normalize weights
    raw_weights = ScoringWeights(
        required_skills=w_req / 100.0,
        preferred_skills=w_pref / 100.0,
        similarity=w_sim / 100.0,
        experience_fit=w_exp / 100.0,
        education_fit=w_edu / 100.0,
        evidence_quality=w_evid / 100.0,
    )
    st.session_state.config.weights = raw_weights.normalized()

    st.markdown("---")
    st.subheader("🎯 Classification Thresholds")
    th_short = st.slider("Shortlist Min Score", 50, 95, int(st.session_state.config.thresholds.shortlist_min), 1)
    th_rev = st.slider("Review Min Score", 30, 80, int(st.session_state.config.thresholds.review_min), 1)
    th_ko = st.slider("Knockout Required %", 10, 60, int(st.session_state.config.thresholds.knockout_required_coverage * 100), 5)

    st.session_state.config.thresholds.shortlist_min = float(th_short)
    st.session_state.config.thresholds.review_min = float(th_rev)
    st.session_state.config.thresholds.knockout_required_coverage = th_ko / 100.0

    st.markdown("---")
    st.subheader("🛡️ Toggles & Privacy")
    mask_pii = st.toggle("Mask PII (Email & Phone)", value=st.session_state.config.mask_pii)
    fuzzy_match = st.toggle("Fuzzy Skill Matching", value=st.session_state.config.enable_fuzzy_matching)
    sem_flag = st.toggle("Semantic Embeddings Model", value=st.session_state.config.enable_semantic)
    ocr_flag = st.toggle("OCR Scanned PDF Fallback", value=st.session_state.config.enable_ocr)

    st.session_state.config.mask_pii = mask_pii
    st.session_state.config.enable_fuzzy_matching = fuzzy_match
    st.session_state.config.enable_semantic = sem_flag
    st.session_state.config.enable_ocr = ocr_flag


# Re-score immediately if candidates and job exist
def update_screening_results() -> None:
    """Re-compute scores and rankings with current weights and thresholds."""
    if st.session_state.candidates and st.session_state.job_profile:
        st.session_state.results = rank_and_classify_candidates(
            candidates=st.session_state.candidates,
            job=st.session_state.job_profile,
            similarities=st.session_state.similarities,
            config=st.session_state.config,
        )


update_screening_results()


# ==============================================================================
# MAIN TABS INTERFACE
# ==============================================================================
st.title("🎯 AI Resume Screening & Candidate Shortlisting")
st.markdown(
    "> **Human Recruiter Decision Support System**: Provides explainable, calibrated multi-factor scoring "
    "and ranking for recruitment teams. Final hiring decisions must always be made by a human reviewer."
)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1️⃣ Job Description",
    "2️⃣ Upload Resumes",
    "3️⃣ Results & Ranking",
    "4️⃣ Candidate Comparison",
    "5️⃣ About & Methodology",
])


# ------------------------------------------------------------------------------
# TAB 1: JOB DESCRIPTION
# ------------------------------------------------------------------------------
with tab1:
    st.header("Step 1: Define Job Requirements")

    col_select, col_upload = st.columns([1, 1])

    with col_select:
        sample_jd_options = ["None (Custom / Paste below)"]
        if SAMPLE_JDS_DIR.exists():
            sample_jd_options.extend([p.name for p in sorted(SAMPLE_JDS_DIR.glob("*.txt"))])

        selected_sample = st.selectbox("📂 Load Sample Job Description", sample_jd_options)
        if selected_sample != "None (Custom / Paste below)":
            with open(SAMPLE_JDS_DIR / selected_sample, "r", encoding="utf-8") as f:
                st.session_state.jd_text = f.read()

    with col_upload:
        jd_file = st.file_uploader("📤 Or Upload JD File (TXT, PDF, DOCX)", type=["txt", "pdf", "docx"])
        if jd_file is not None:
            ext_res = extract_text_from_file(jd_file.read(), jd_file.name, st.session_state.config)
            if ext_res.text:
                st.session_state.jd_text = ext_res.text
                st.success(f"Loaded JD from {jd_file.name}")

    jd_input_text = st.text_area(
        "Job Description Text",
        value=st.session_state.jd_text,
        height=260,
        placeholder="Paste full job description including requirements, qualifications, and experience...",
    )

    if st.button("🔍 Parse & Analyze Job Requirements", type="primary", use_container_width=True):
        if not jd_input_text.strip():
            st.error("Please enter or select a job description.")
        else:
            st.session_state.jd_text = jd_input_text
            parsed_job = parse_job_description(jd_input_text, st.session_state.config)
            st.session_state.job_profile = parsed_job
            st.success(f"Successfully parsed job: '{parsed_job.title}'")

    # Editable requirements section
    if st.session_state.job_profile:
        job: JobProfile = st.session_state.job_profile
        st.markdown("---")
        st.subheader("✏️ Review & Edit Parsed Requirements")
        st.caption("You can refine required/preferred skills and experience constraints before screening resumes.")

        col_title, col_exp, col_edu = st.columns([2, 1, 1])
        with col_title:
            job.title = st.text_input("Job Title", value=job.title)
        with col_exp:
            job.min_years_experience = st.number_input(
                "Min Experience (Years)",
                min_value=0.0,
                max_value=25.0,
                value=float(job.min_years_experience),
                step=0.5,
            )
        with col_edu:
            edu_options = ["Any", "Bachelor", "Master", "PhD", "Diploma"]
            idx = edu_options.index(job.required_education_level) if job.required_education_level in edu_options else 0
            job.required_education_level = st.selectbox("Required Education", edu_options, index=idx)

        col_req_skills, col_pref_skills = st.columns(2)
        with col_req_skills:
            req_str = ", ".join(job.required_skills)
            new_req_str = st.text_area("Required Skills (comma-separated)", value=req_str, height=100)
            job.required_skills = [s.strip().lower() for s in new_req_str.split(",") if s.strip()]

        with col_pref_skills:
            pref_str = ", ".join(job.preferred_skills)
            new_pref_str = st.text_area("Preferred Skills (comma-separated)", value=pref_str, height=100)
            job.preferred_skills = [s.strip().lower() for s in new_pref_str.split(",") if s.strip()]

        st.session_state.job_profile = job


# ------------------------------------------------------------------------------
# TAB 2: UPLOAD RESUMES
# ------------------------------------------------------------------------------
with tab2:
    st.header("Step 2: Upload Candidate Resumes")

    col_upload_box, col_bundled_box = st.columns([3, 2])

    with col_upload_box:
        uploaded_files = st.file_uploader(
            "Upload Resumes (PDF, DOCX, TXT) - In-Memory Only",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True,
        )

    with col_bundled_box:
        st.markdown("**Quick Start: Bundled Test Dataset**")
        st.caption("Load 13 pre-generated synthetic resumes spanning strong, medium, weak, keyword-stuffed, and scanned cases.")
        if st.button("📁 Load 13 Sample Resumes", use_container_width=True):
            if not st.session_state.job_profile:
                st.warning("Please parse or select a Job Description in Tab 1 first.")
            else:
                with st.spinner("Extracting and parsing bundled resumes in memory..."):
                    resume_paths = sorted(list(SAMPLE_RESUMES_DIR.glob("*.*")))
                    candidates = []
                    resume_texts = []
                    for idx, rpath in enumerate(resume_paths):
                        with open(rpath, "rb") as f:
                            b = f.read()
                        ext_res = extract_text_from_file(b, rpath.name, st.session_state.config)
                        cand = parse_resume(
                            raw_text=ext_res.text,
                            filename=rpath.name,
                            candidate_id=f"CAND_{idx+1:02d}",
                            config=st.session_state.config,
                            is_scanned_or_empty=ext_res.is_scanned_or_unreadable,
                            extraction_warning=ext_res.warning,
                        )
                        candidates.append(cand)
                        resume_texts.append(cand.cleaned_text)

                    st.session_state.candidates = candidates
                    sim_engine = SimilarityEngine(st.session_state.config)
                    st.session_state.similarities = sim_engine.compute_batch_similarity(
                        st.session_state.job_profile.raw_text,
                        resume_texts,
                    )
                    update_screening_results()
                    st.success(f"Loaded and screened {len(candidates)} resumes!")

    if uploaded_files:
        if st.button(f"🚀 Process & Screen {len(uploaded_files)} Uploaded Resumes", type="primary", use_container_width=True):
            if not st.session_state.job_profile:
                st.error("Please parse a Job Description in Tab 1 before processing resumes.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()

                candidates = []
                resume_texts = []
                errors = []

                for idx, file_obj in enumerate(uploaded_files):
                    status_text.text(f"Extracting {file_obj.name} ({idx+1}/{len(uploaded_files)})...")
                    file_bytes = file_obj.read()
                    ext_res = extract_text_from_file(file_bytes, file_obj.name, st.session_state.config)

                    if ext_res.error:
                        errors.append(f"❌ {file_obj.name}: {ext_res.error}")

                    cand = parse_resume(
                        raw_text=ext_res.text,
                        filename=file_obj.name,
                        candidate_id=f"CAND_{idx+1:02d}",
                        config=st.session_state.config,
                        is_scanned_or_empty=ext_res.is_scanned_or_unreadable,
                        extraction_warning=ext_res.warning or ext_res.error,
                    )
                    candidates.append(cand)
                    resume_texts.append(cand.cleaned_text)
                    progress_bar.progress((idx + 1) / len(uploaded_files))

                status_text.text("Computing similarity matrices and ranking candidates...")
                st.session_state.candidates = candidates
                sim_engine = SimilarityEngine(st.session_state.config)
                st.session_state.similarities = sim_engine.compute_batch_similarity(
                    st.session_state.job_profile.raw_text,
                    resume_texts,
                )
                update_screening_results()
                progress_bar.empty()
                status_text.empty()

                st.success(f"Successfully processed {len(candidates)} candidate resumes!")
                if errors:
                    with st.expander("⚠️ View Extraction Errors"):
                        for err in errors:
                            st.write(err)

    if st.session_state.candidates:
        st.markdown(f"**Current Batch:** `{len(st.session_state.candidates)} resumes loaded in memory`.")


# ------------------------------------------------------------------------------
# TAB 3: RESULTS & RANKING
# ------------------------------------------------------------------------------
with tab3:
    st.header("Step 3: Screening Results & Candidate Rankings")

    if not st.session_state.results:
        st.info("No candidates screened yet. Please parse a JD in Tab 1 and upload/load resumes in Tab 2.")
    else:
        results: List[ScreeningResult] = st.session_state.results

        # KPI Summary Cards
        shortlisted_cnt = sum(1 for r in results if r.band == DecisionBand.SHORTLISTED)
        review_cnt = sum(1 for r in results if r.band == DecisionBand.REVIEW)
        rejected_cnt = sum(1 for r in results if r.band == DecisionBand.REJECTED)
        avg_score = sum(r.score.final_score for r in results) / len(results)

        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        kpi1.metric("Total Resumes", len(results))
        kpi2.metric("✅ Shortlisted", shortlisted_cnt)
        kpi3.metric("🔍 Under Review", review_cnt)
        kpi4.metric("⛔ Rejected", rejected_cnt)
        kpi5.metric("Average Score", f"{avg_score:.1f} / 100")

        # Export Buttons
        col_csv, col_excel = st.columns(2)
        with col_csv:
            csv_data = export_to_csv(results, include_pii=not st.session_state.config.mask_pii)
            st.download_button(
                label="📥 Download Rankings as CSV",
                data=csv_data,
                file_name="candidate_screening_rankings.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_excel:
            excel_data = export_to_excel(results, include_pii=not st.session_state.config.mask_pii)
            st.download_button(
                label="📥 Download Rankings as Excel (.xlsx)",
                data=excel_data,
                file_name="candidate_screening_rankings.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        st.markdown("---")
        # Visual Analytics Charts
        st.subheader("📊 Score Distribution & Component Breakdown")
        col_bar, col_stacked = st.columns([1, 1])

        with col_bar:
            # Score distribution bar chart
            chart_df = pd.DataFrame([
                {
                    "Candidate": r.candidate.filename[:20],
                    "Score": r.score.final_score,
                    "Band": r.band.value,
                }
                for r in results
            ])
            color_map = {"Shortlisted": "#28a745", "Review": "#ffc107", "Rejected": "#dc3545"}
            fig_bar = px.bar(
                chart_df,
                x="Candidate",
                y="Score",
                color="Band",
                color_discrete_map=color_map,
                title="Overall Candidate Scores & Bands",
            )
            fig_bar.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_stacked:
            # Stacked contribution chart
            contrib_records = []
            for r in results:
                c_name = r.candidate.filename[:18]
                sc = r.score
                contrib_records.extend([
                    {"Candidate": c_name, "Component": "Required Skills", "Points": sc.required_skills_contribution},
                    {"Candidate": c_name, "Component": "Preferred Skills", "Points": sc.preferred_skills_contribution},
                    {"Candidate": c_name, "Component": "Similarity", "Points": sc.similarity_contribution},
                    {"Candidate": c_name, "Component": "Experience", "Points": sc.experience_contribution},
                    {"Candidate": c_name, "Component": "Education", "Points": sc.education_contribution},
                    {"Candidate": c_name, "Component": "Evidence", "Points": sc.evidence_contribution},
                ])
            contrib_df = pd.DataFrame(contrib_records)
            fig_stack = px.bar(
                contrib_df,
                x="Candidate",
                y="Points",
                color="Component",
                title="Weighted Component Contributions",
            )
            fig_stack.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20), barmode="stack")
            st.plotly_chart(fig_stack, use_container_width=True)

        st.markdown("---")
        # Ranking Table
        st.subheader("📋 Ranked Candidates Overview")
        overview_df = pd.DataFrame([
            {
                "Rank": f"#{r.rank}",
                "Candidate ID": r.candidate.candidate_id,
                "Filename": r.candidate.filename,
                "Decision Band": r.band.value,
                "Final Score": f"{r.score.final_score:.1f}",
                "Req Skills": f"{r.score.required_skills_score:.0f}%",
                "Similarity": f"{r.score.similarity_score:.0f}%",
                "Experience": f"{r.candidate.total_years_experience:.1f} yrs",
                "Education": r.candidate.highest_education_level,
                "Warnings": len(r.warnings),
            }
            for r in results
        ])
        st.dataframe(overview_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        # Detailed Candidate Deep-Dive Expanders
        st.subheader("🔍 Individual Candidate Analysis & Explainability")

        for res in results:
            cand = res.candidate
            score = res.score

            band_color = {
                DecisionBand.SHORTLISTED: "badge-shortlist",
                DecisionBand.REVIEW: "badge-review",
                DecisionBand.REJECTED: "badge-rejected",
            }[res.band]

            expander_title = (
                f"Rank #{res.rank}: {cand.filename}  |  "
                f"Score: {score.final_score:.1f}/100  |  [{res.band.value}]"
            )

            with st.expander(expander_title, expanded=(res.rank == 1)):
                c_head1, c_head2 = st.columns([3, 1])
                with c_head1:
                    st.markdown(
                        f"<span class='{band_color}'>{res.band.value.upper()}</span> &nbsp; "
                        f"**Candidate ID:** `{cand.candidate_id}` &nbsp; | &nbsp; "
                        f"**Experience:** `{cand.total_years_experience:.1f} years` &nbsp; | &nbsp; "
                        f"**Education:** `{cand.highest_education_level}`",
                        unsafe_allow_html=True,
                    )
                    email_show = cand.masked_email if st.session_state.config.mask_pii else cand.masked_email
                    st.caption(f"Contact: {email_show} | {cand.masked_phone}")
                with c_head2:
                    report_md = generate_candidate_markdown_summary(res)
                    st.download_button(
                        label="📄 Download Report",
                        data=report_md.encode("utf-8"),
                        file_name=f"{cand.candidate_id}_report.md",
                        mime="text/markdown",
                        key=f"dl_{cand.candidate_id}",
                    )

                if res.warnings:
                    for warn in res.warnings:
                        st.warning(f"⚠️ {warn}")

                # Skill Chips Visualizer
                st.markdown("**Skill Match Breakdown:**")
                req_set = set(st.session_state.job_profile.required_skills)
                pref_set = set(st.session_state.job_profile.preferred_skills)
                cand_skills = cand.extracted_skills

                matched_req = [s for s in req_set if s in cand_skills]
                missing_req = [s for s in req_set if s not in cand_skills]
                matched_pref = [s for s in pref_set if s in cand_skills]
                missing_pref = [s for s in pref_set if s not in cand_skills]

                chips_html = []
                for s in matched_req:
                    chips_html.append(f"<span class='skill-chip chip-req-match'>✓ {s} (Req)</span>")
                for s in matched_pref:
                    chips_html.append(f"<span class='skill-chip chip-pref-match'>✓ {s} (Pref)</span>")
                for s in missing_req:
                    chips_html.append(f"<span class='skill-chip chip-missing'>✗ {s} (Req)</span>")
                for s in missing_pref:
                    chips_html.append(f"<span class='skill-chip chip-missing'>✗ {s} (Pref)</span>")

                st.markdown(" ".join(chips_html), unsafe_allow_html=True)

                # Component contribution table
                st.markdown("**Score Component Breakdown:**")
                bd_df = pd.DataFrame([
                    {"Dimension": "Required Skills Coverage", "Score": f"{score.required_skills_score:.1f}%", "Weight": "40%", "Contribution": f"+{score.required_skills_contribution:.2f} pts"},
                    {"Dimension": "Preferred Skills Coverage", "Score": f"{score.preferred_skills_score:.1f}%", "Weight": "10%", "Contribution": f"+{score.preferred_skills_contribution:.2f} pts"},
                    {"Dimension": "Text Content Similarity", "Score": f"{score.similarity_score:.1f}%", "Weight": "20%", "Contribution": f"+{score.similarity_contribution:.2f} pts"},
                    {"Dimension": "Experience Fit", "Score": f"{score.experience_score:.1f}%", "Weight": "15%", "Contribution": f"+{score.experience_contribution:.2f} pts"},
                    {"Dimension": "Education Fit", "Score": f"{score.education_score:.1f}%", "Weight": "10%", "Contribution": f"+{score.education_contribution:.2f} pts"},
                    {"Dimension": "Evidence Quality", "Score": f"{score.evidence_score:.1f}%", "Weight": "5%", "Contribution": f"+{score.evidence_contribution:.2f} pts"},
                    {"Dimension": "Penalties Deducted", "Score": f"-{score.penalty:.1f} pts", "Weight": "-", "Contribution": f"-{score.penalty:.2f} pts"},
                    {"Dimension": "FINAL SCORE", "Score": f"{score.final_score:.1f}/100", "Weight": "100%", "Contribution": f"{score.final_score:.1f} pts"},
                ])
                st.dataframe(bd_df, use_container_width=True, hide_index=True)

                st.markdown("**Evaluator Explanations & Evidence:**")
                for exp in score.explanations:
                    st.write(f"- {exp}")

                with st.expander("📄 View Extracted Text Preview"):
                    st.text(cand.cleaned_text[:1200] + ("..." if len(cand.cleaned_text) > 1200 else ""))


# ------------------------------------------------------------------------------
# TAB 4: CANDIDATE COMPARISON
# ------------------------------------------------------------------------------
with tab4:
    st.header("Step 4: Side-by-Side Candidate Comparison")

    if not st.session_state.results or len(st.session_state.results) < 2:
        st.info("Please screen at least two candidates to compare them side by side.")
    else:
        results = st.session_state.results
        candidate_options = [f"#{r.rank} - {r.candidate.filename} ({r.score.final_score:.1f} pts)" for r in results]

        default_selection = candidate_options[:min(3, len(candidate_options))]
        selected_cand_strings = st.multiselect(
            "Select 2 or 3 candidates to compare:",
            options=candidate_options,
            default=default_selection,
            max_selections=3,
        )

        if len(selected_cand_strings) >= 2:
            selected_results: List[ScreeningResult] = []
            for s in selected_cand_strings:
                rank_num = int(s.split(" - ")[0].replace("#", ""))
                res = [r for r in results if r.rank == rank_num][0]
                selected_results.append(res)

            # Radar Chart of 6 components
            categories = [
                "Required Skills",
                "Preferred Skills",
                "Similarity",
                "Experience",
                "Education",
                "Evidence",
            ]

            fig_radar = go.Figure()
            for res in selected_results:
                sc = res.score
                values = [
                    sc.required_skills_score,
                    sc.preferred_skills_score,
                    sc.similarity_score,
                    sc.experience_score,
                    sc.education_score,
                    sc.evidence_score,
                ]
                # Close the loop
                values.append(values[0])
                radar_cats = categories + [categories[0]]

                fig_radar.add_trace(go.Scatterpolar(
                    r=values,
                    theta=radar_cats,
                    fill="toself",
                    name=f"#{res.rank} {res.candidate.filename[:16]}",
                ))

            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                showlegend=True,
                title="6-Axis Competency Comparison Radar",
                height=450,
            )
            st.plotly_chart(fig_radar, use_container_width=True)

            # Side-by-side metric columns
            comp_cols = st.columns(len(selected_results))
            for i, res in enumerate(selected_results):
                with comp_cols[i]:
                    st.markdown(f"### #{res.rank}: {res.candidate.filename}")
                    st.metric("Final Score", f"{res.score.final_score:.1f} / 100", res.band.value)
                    st.write(f"**Experience:** {res.candidate.total_years_experience:.1f} years")
                    st.write(f"**Education:** {res.candidate.highest_education_level}")
                    st.write(f"**Skills Count:** {len(res.candidate.extracted_skills)}")
                    if res.warnings:
                        st.warning(f"⚠️ {len(res.warnings)} warnings")


# ------------------------------------------------------------------------------
# TAB 5: ABOUT & METHODOLOGY
# ------------------------------------------------------------------------------
with tab5:
    st.header("Step 5: System Architecture & Methodology")

    st.markdown("""
### Academic Project Overview (B.Tech Final Year)
The **AI-Based Resume Screening and Candidate Shortlisting System** addresses high-volume recruitment challenges by pairing deterministic, transparent feature engineering with statistical NLP retrieval models.

Unlike black-box neural networks, this architecture provides **explainability by design**:
every candidate receives an exact numeric contribution breakdown and natural-language justifications for recruiter auditability.

---

### Scoring Formula
$$\\text{Final Score} = \\sum_{i=1}^{6} (w_i \\times S_i) - P_{\\text{anti-gaming}}$$

Where:
- $S_1$: Required Skills Coverage (40%)
- $S_2$: Preferred Skills Coverage (10%)
- $S_3$: Calibrated TF-IDF & Semantic Similarity (20%)
- $S_4$: Years of Experience Fit (15%)
- $S_5$: Educational Qualification Fit (10%)
- $S_6$: Evidence Quality (Demonstrated vs Listed) (5%)
- $P_{\\text{anti-gaming}}$: Deductions for keyword repetition or excessive skill density.

**Knockout Rule:** If a candidate achieves $< 30\\%$ coverage on mandatory required skills, their score is strictly capped at $49.0$ and classified as Rejected.

---

### Anti-Gaming Protection
Keyword stuffing and adversarial attempts to manipulate similarity metrics are counteracted via:
1. **Single-Skill Frequency Capping:** Flags skills repeated $> 8$ times.
2. **Skill Density Anomaly Detection:** Flags documents where $> 35\\%$ of tokens are skill keywords.
3. **Pivoted Length Calibration:** Prevents verbose resumes from dominating concise, high-density resumes.
4. **Verbatim JD Copy Detection:** Identifies unnatural copy-paste text chunks.

---

### Privacy & Ethical Governance
- **In-Memory Processing:** Resumes are never stored on persistent disk or transmitted to external third-party APIs.
- **PII Masking:** Direct identifiers (email, telephone) are automatically redacted in table views and export sheets.
- **Compliance Awareness:** Aligns with principles of the Indian Digital Personal Data Protection (DPDP) Act 2023.
- **Human Oversight:** Designed strictly as decision support; algorithmic shortlists are not autonomous employment decisions.
""")
