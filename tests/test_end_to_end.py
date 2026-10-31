"""End-to-end integration tests for candidate screening pipeline."""

from pathlib import Path

from src.config import DATA_DIR, SAMPLE_JDS_DIR, SAMPLE_RESUMES_DIR, SystemConfig
from src.job_parser import parse_job_description
from src.models import DecisionBand
from src.ranker import rank_and_classify_candidates
from src.resume_parser import parse_resume
from src.similarity import SimilarityEngine
from src.text_extraction import extract_text_from_file


def _load_sample_candidates(config: SystemConfig):
    resume_files = sorted(list(SAMPLE_RESUMES_DIR.glob("*.*")))
    candidates = []
    texts = []
    for idx, path in enumerate(resume_files):
        with open(path, "rb") as f:
            b = f.read()
        res = extract_text_from_file(b, path.name, config)
        cand = parse_resume(
            raw_text=res.text,
            filename=path.name,
            candidate_id=f"c_{idx+1:02d}",
            config=config,
            is_scanned_or_empty=res.is_scanned_or_unreadable,
            extraction_warning=res.warning,
        )
        candidates.append(cand)
        texts.append(cand.cleaned_text)
    return candidates, texts


def test_end_to_end_python_backend():
    config = SystemConfig()
    candidates, resume_texts = _load_sample_candidates(config)

    jd_path = SAMPLE_JDS_DIR / "python_backend_engineer.txt"
    with open(jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()
    job = parse_job_description(jd_text, config)

    sim_engine = SimilarityEngine(config)
    sims = sim_engine.compute_batch_similarity(job.raw_text, resume_texts)
    results = rank_and_classify_candidates(candidates, job, sims, config)

    score_map = {r.candidate.filename: r.score.final_score for r in results}
    band_map = {r.candidate.filename: r.band for r in results}

    # 1. Strong > Medium > Weak > Non-Technical
    assert score_map["resume_01_strong_python_backend.pdf"] > score_map["resume_02_medium_python_backend.docx"]
    assert score_map["resume_02_medium_python_backend.docx"] > score_map["resume_03_weak_python_backend.pdf"]
    assert score_map["resume_03_weak_python_backend.pdf"] > score_map["resume_11_non_technical_retail.pdf"]

    # 2. Honest strong > Stuffed
    assert score_map["resume_01_strong_python_backend.pdf"] > score_map["resume_04_stuffed_python_backend.pdf"]
    stuffed_res = [r for r in results if r.candidate.filename == "resume_04_stuffed_python_backend.pdf"][0]
    assert len(stuffed_res.anti_gaming_flags) > 0

    # 3. At least one Shortlisted
    shortlisted = [r for r in results if r.band == DecisionBand.SHORTLISTED]
    assert len(shortlisted) >= 1
    assert any("python_backend" in r.candidate.filename or "polyglot" in r.candidate.filename for r in shortlisted)

    # 4. Non-technical and unreadable are Rejected
    assert band_map["resume_11_non_technical_retail.pdf"] == DecisionBand.REJECTED
    assert band_map["resume_12_scanned_unreadable.pdf"] == DecisionBand.REJECTED


def test_end_to_end_mern_developer():
    config = SystemConfig()
    candidates, resume_texts = _load_sample_candidates(config)

    jd_path = SAMPLE_JDS_DIR / "fullstack_mern_developer.txt"
    with open(jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()
    job = parse_job_description(jd_text, config)

    sim_engine = SimilarityEngine(config)
    sims = sim_engine.compute_batch_similarity(job.raw_text, resume_texts)
    results = rank_and_classify_candidates(candidates, job, sims, config)

    score_map = {r.candidate.filename: r.score.final_score for r in results}
    band_map = {r.candidate.filename: r.band for r in results}

    # Strong MERN > Medium MERN > Weak MERN
    assert score_map["resume_05_strong_mern_developer.pdf"] > score_map["resume_06_medium_mern_developer.docx"]
    assert score_map["resume_06_medium_mern_developer.docx"] > score_map["resume_07_weak_mern_developer.pdf"]

    # Strong MERN must be Shortlisted
    assert band_map["resume_05_strong_mern_developer.pdf"] == DecisionBand.SHORTLISTED


def test_end_to_end_data_analyst():
    config = SystemConfig()
    candidates, resume_texts = _load_sample_candidates(config)

    jd_path = SAMPLE_JDS_DIR / "data_analyst.txt"
    with open(jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()
    job = parse_job_description(jd_text, config)

    sim_engine = SimilarityEngine(config)
    sims = sim_engine.compute_batch_similarity(job.raw_text, resume_texts)
    results = rank_and_classify_candidates(candidates, job, sims, config)

    score_map = {r.candidate.filename: r.score.final_score for r in results}
    band_map = {r.candidate.filename: r.band for r in results}

    # Strong Data Analyst > Medium Data Analyst > Weak Data Analyst
    assert score_map["resume_08_strong_data_analyst.pdf"] > score_map["resume_09_medium_data_analyst.docx"]
    assert score_map["resume_09_medium_data_analyst.docx"] > score_map["resume_10_weak_data_analyst.pdf"]

    # Strong Data Analyst must be Shortlisted
    assert band_map["resume_08_strong_data_analyst.pdf"] == DecisionBand.SHORTLISTED
