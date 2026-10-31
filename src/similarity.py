"""Similarity calculation and calibration engine.

Computes TF-IDF cosine similarity fitted on a robust batch corpus
(JD + all candidate resumes + reference corpus) using sublinear TF and n-grams.
Applies monotonic calibration to prevent resume length bias and map raw cosine
to an explainable 0-100 scale. Supports optional sentence-transformers semantic embeddings.
"""

from __future__ import annotations

import logging
import math
from typing import List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.config import SystemConfig


logger = logging.getLogger(__name__)

# Reference background corpus documents used to stabilize IDF when the user batch is small
REFERENCE_BACKGROUND_CORPUS: List[str] = [
    "Software engineer developing backend web applications using Python, Django, REST APIs, and PostgreSQL database.",
    "Full stack developer building responsive web interfaces with React, JavaScript, TypeScript, HTML5, CSS3, and Node.js.",
    "Data scientist analyzing large datasets using Python, Pandas, NumPy, Scikit-learn, SQL, and machine learning models.",
    "Cloud DevOps engineer automating infrastructure deployment using Docker, Kubernetes, Terraform, AWS, and CI/CD pipelines.",
    "Mobile application developer creating iOS and Android apps using Swift, Kotlin, Flutter, and Firebase backend services.",
    "System administrator managing Linux servers, network security, bash scripting, Nginx reverse proxy, and monitoring.",
]


def calibrate_similarity_score(raw_cosine: float) -> float:
    """Monotonically map raw cosine similarity into an explainable 0 - 100 score.

    In text matching against multi-paragraph job descriptions, raw cosine similarities
    typically range from 0.02 (irrelevant) to 0.30+ (highly qualified) due to vocabulary
    sparsity in high-dimensional n-gram representations.

    This function uses a calibrated smooth sigmoid (logistic) transform with parameters:
      - Midpoint x0 = 0.15
      - Steepness k = 22.0
    Guarantees:
      - Monotonicity: if raw_a > raw_b, then score_a >= score_b.
      - Fair to long resumes: resume length normalization is built into cosine and sublinear TF.
      - Output strictly bounded between 0.0 and 100.0.
    """
    if raw_cosine <= 0.0:
        return 0.0
    if raw_cosine >= 1.0:
        return 100.0

    x0 = 0.15
    k = 22.0
    sig = 1.0 / (1.0 + math.exp(-k * (raw_cosine - x0)))

    sig_min = 1.0 / (1.0 + math.exp(-k * (0.02 - x0)))
    sig_max = 1.0 / (1.0 + math.exp(-k * (0.35 - x0)))

    calibrated = ((sig - sig_min) / (sig_max - sig_min)) * 100.0
    return float(np.clip(calibrated, 0.0, 100.0))


class SimilarityEngine:
    """Manages batch TF-IDF vectorization and optional semantic embeddings."""

    def __init__(self, config: Optional[SystemConfig] = None) -> None:
        self.config = config or SystemConfig()
        self._sentence_model = None
        self._semantic_available = False

        if self.config.enable_semantic:
            self._init_semantic_model()

    def _init_semantic_model(self) -> None:
        """Attempt to load sentence-transformers model if enabled."""
        try:
            from sentence_transformers import SentenceTransformer
            self._sentence_model = SentenceTransformer("all-MiniLM-L6-v2")
            self._semantic_available = True
            logger.info("Loaded sentence-transformers model all-MiniLM-L6-v2.")
        except ImportError:
            logger.info("sentence-transformers is not installed. Falling back to TF-IDF.")
            self._semantic_available = False
        except Exception as err:
            logger.warning("Failed to initialize sentence-transformers: %s", err)
            self._semantic_available = False

    def compute_batch_similarity(
        self,
        jd_text: str,
        resume_texts: List[str],
    ) -> List[Tuple[float, float, float]]:
        """Compute similarity for all resumes against the JD.

        Vectorizes JD + all candidate resumes + reference background documents together,
        ensuring meaningful inverse document frequencies (IDF).

        Args:
            jd_text: Cleaned text of the job description.
            resume_texts: Cleaned text of each candidate's resume.

        Returns:
            List of tuples: (calibrated_combined_score, raw_tfidf_cosine, raw_semantic_cosine)
        """
        if not resume_texts:
            return []

        # 1. Build the full corpus for fitting the TF-IDF vectorizer
        # JD + resumes + background reference texts
        fit_corpus = [jd_text] + resume_texts + REFERENCE_BACKGROUND_CORPUS

        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            max_df=0.90,
            min_df=1,
            stop_words="english",
            norm=None,  # Keep unnormalized vectors to compute query coverage alongside cosine
        )

        try:
            vectorizer.fit(fit_corpus)
            jd_vec_unnorm = vectorizer.transform([jd_text])
            resume_vecs_unnorm = vectorizer.transform(resume_texts)

            # Standard cosine similarity with normalized vectors
            from sklearn.preprocessing import normalize
            jd_vec_norm = normalize(jd_vec_unnorm)
            resume_vecs_norm = normalize(resume_vecs_unnorm)
            tfidf_cosines = cosine_similarity(resume_vecs_norm, jd_vec_norm).flatten()

            # Query coverage fraction (neutralizes length penalty for rich/long resumes)
            jd_sq_norm = np.dot(jd_vec_unnorm.data, jd_vec_unnorm.data)
            query_coverages = (
                (resume_vecs_unnorm @ jd_vec_unnorm.T).toarray().flatten() / (jd_sq_norm + 1e-9)
            )
        except Exception as err:
            logger.error("TF-IDF vectorization error: %s", err)
            tfidf_cosines = np.zeros(len(resume_texts))
            query_coverages = np.zeros(len(resume_texts))

        # 2. Optional semantic embeddings
        semantic_cosines = np.zeros(len(resume_texts))
        if self._semantic_available and self._sentence_model is not None:
            try:
                jd_emb = self._sentence_model.encode([jd_text])
                resume_embs = self._sentence_model.encode(resume_texts)
                semantic_cosines = cosine_similarity(resume_embs, jd_emb).flatten()
            except Exception as err:
                logger.warning("Semantic embeddings computation error: %s", err)
                semantic_cosines = np.zeros(len(resume_texts))

        results: List[Tuple[float, float, float]] = []
        for i in range(len(resume_texts)):
            raw_tfidf = float(tfidf_cosines[i]) if i < len(tfidf_cosines) else 0.0
            raw_q_cov = float(np.clip(query_coverages[i], 0.0, 1.0)) if i < len(query_coverages) else 0.0
            raw_sem = float(semantic_cosines[i]) if i < len(semantic_cosines) else 0.0

            # Length-fair blended TF-IDF (45% cosine + 55% query coverage)
            blended_tfidf = 0.45 * raw_tfidf + 0.55 * raw_q_cov

            if self._semantic_available and raw_sem > 0.0:
                blend_ratio = self.config.semantic_blend_ratio
                blended_raw = (1.0 - blend_ratio) * blended_tfidf + blend_ratio * raw_sem
            else:
                blended_raw = blended_tfidf

            calibrated = calibrate_similarity_score(blended_raw)
            results.append((round(calibrated, 2), round(raw_tfidf, 4), round(raw_sem, 4)))

        return results
