# System Evaluation & Benchmark Report

This report presents quantitative evaluation results for the **AI-Based Resume Screening and Candidate Shortlisting System** benchmarked against a curated, multi-tier evaluation set.

---

## Evaluation Dataset Characteristics
- **Total Test Cases:** 39 (13 candidate profiles evaluated across 3 distinct job domains).
- **Domains Tested:** Python Backend Engineering, Full-Stack MERN Development, Business Data Analysis.
- **Candidate Profiles:** Strong, Medium, Weak, Keyword-Stuffed, Non-Technical (Retail), and Scanned Image files.
- **Ground Truth:** Multi-level human relevance ratings (0 = Irrelevant, 1 = Weak, 2 = Medium/Consider, 3 = Highly Qualified/Shortlist).

---

## Quantitative Performance Summary

| Job Description                | Job ID         |   Total Resumes |   P@1 |   P@3 |   P@5 |   Shortlist Precision |   Shortlist Recall |   Shortlist F1 |   Spearman Rho |
|:-------------------------------|:---------------|----------------:|------:|------:|------:|----------------------:|-------------------:|---------------:|---------------:|
| Senior Python Backend Engineer | python_backend |              13 |     1 | 1     |   0.6 |                     1 |              0.667 |          0.8   |          0.671 |
| Full-Stack MERN Developer      | mern_developer |              13 |     1 | 0.667 |   0.4 |                     1 |              1     |          1     |          0.496 |
| Business Data Analyst          | data_analyst   |              13 |     1 | 0.667 |   0.4 |                     1 |              0.5   |          0.667 |          0.683 |

---

## Metric Definitions
1. **Precision@k (P@k):** Proportion of the top-k ranked candidates who are genuinely relevant according to human ground truth.
2. **Shortlist Precision:** Proportion of candidates classified as **Shortlisted** who truly meet hiring standards.
3. **Shortlist Recall:** Proportion of truly qualified candidates successfully classified as **Shortlisted**.
4. **Shortlist F1-Score:** Harmonic mean of Shortlist Precision and Shortlist Recall.
5. **Spearman Rank Correlation (\(\rho\)):** Monotonic correlation between the system's final calibrated scores and human relevance ratings (where +1.0 represents perfect rank alignment).

---

## Key Findings & Verification Highlights
- **Ranking Accuracy:** Top-ranked candidates across all three technical roles (P@1 = 1.0) strictly match domain requirements.
- **Robustness Against Adversarial Gaming:** The keyword-stuffed profile (`resume_04_stuffed_python_backend.pdf`) triggered anti-gaming penalties, preventing it from topping the honest candidates.
- **Length Fairness:** Detailed, multi-page resumes covering extensive enterprise architectures (`resume_13_strong_polyglot_long.pdf`) ranked at the top of the shortlist without suffering length suppression.
- **Handling of Unreadable Media:** Corrupt/scanned resumes (`resume_12_scanned_unreadable.pdf`) were immediately identified, routed with warnings, and excluded from accidental hiring decisions.
