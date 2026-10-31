# Scoring System Specification & Calibration Guide

This document details the mathematical formulations, calibration curves, knockout rules, and anti-gaming penalties implemented in the **AI-Based Resume Screening and Candidate Shortlisting System**.

---

## 1. Overall Scoring Formula

The candidate's final evaluation score ($F \in [0.0, 100.0]$) is computed as a deterministic weighted combination of six distinct qualification components, minus any anti-gaming penalties, subject to mandatory knockout caps:

$$F = \max\left(0.0, \min\left(100.0, \sum_{i=1}^{6} (w_i \cdot S_i) - P_{\text{gaming}}\right)\right)$$

Where:
- $S_i \in [0.0, 100.0]$ is the raw component score.
- $w_i \in [0.0, 1.0]$ is the normalized component weight ($\sum_{i=1}^{6} w_i = 1.0$).
- $P_{\text{gaming}} \ge 0$ is the keyword stuffing penalty.

---

## 2. Component Breakdown & Weight Rationale

| Component | Default Weight | Dimension | Calculation Method | Rationale |
| :--- | :---: | :--- | :--- | :--- |
| **Required Skills** ($S_1$) | **40%** | Technical Core | $\frac{\lvert K_{\text{cand}} \cap K_{\text{req}} \rvert}{\lvert K_{\text{req}} \rvert} \times 100$ | Baseline prerequisite. Missing core stack skills invalidates candidacy. |
| **Preferred Skills** ($S_2$) | **10%** | Bonus Competencies | $\frac{\lvert K_{\text{cand}} \cap K_{\text{pref}} \rvert}{\lvert K_{\text{pref}} \rvert} \times 100$ | Differentiates strong candidates from baseline candidates. |
| **Text Similarity** ($S_3$) | **20%** | Holistic Fit | Calibrated TF-IDF & query coverage ($0 - 100$) | Evaluates domain breadth, tooling, and contextual alignment. |
| **Experience Fit** ($S_4$) | **15%** | Career Seniority | $\min\left(100.0, \frac{\text{Years}_{\text{cand}}}{\text{Years}_{\text{req}}} \times 100\right)$ | Ensures sufficient industry maturity without over-penalizing junior surplus. |
| **Education Fit** ($S_5$) | **10%** | Academic Qualification | Tiered degree hierarchy ($100\%, 70\%, 40\%, 20\%$) | Assesses foundational academic credentialing. |
| **Evidence Quality** ($S_6$) | **5%** | Practical Application | $\frac{\text{Skills in Experience/Projects}}{\text{Total Matched Skills}} \times 100$ | Rewards hands-on demonstrated work vs buzzwords in a skills list. |

---

## 3. Similarity Calibration & Length-Fairness

### The Problem with Naive Cosine Similarity
In standard Vector Space Models:
$$\text{Cosine}(q, d) = \frac{\vec{q} \cdot \vec{d}}{\lVert\vec{q}\rVert_2 \cdot \lVert\vec{d}\rVert_2}$$

In resume screening, the job description ($q$) is short and focused, while a comprehensive candidate resume ($d$) may span 2–3 pages detailing multiple past projects, architectures, and leadership achievements. Because $\lVert\vec{d}\rVert_2$ resides in the denominator, adding relevant experience artificially inflates the denominator, depressing raw cosine similarity down to $0.15 - 0.25$.

### Length-Fair Blending
To eliminate length penalty, the system blends normalized cosine similarity with query coverage:
$$\text{Query Coverage}(q, d) = \min\left(1.0, \frac{\vec{d}_{\text{unnorm}} \cdot \vec{q}_{\text{unnorm}}}{\lVert\vec{q}_{\text{unnorm}}\rVert_2^2}\right)$$
$$\text{Blended Similarity} = 0.45 \cdot \text{Cosine}(q, d) + 0.55 \cdot \text{Query Coverage}(q, d)$$

### Monotonic Sigmoid Calibration
Raw blended scores typically span from $0.02$ (unrelated) to $0.30+$ (ideal match). We map this distribution onto an explainable $0 - 100$ scale using a smooth logistic transform:

$$\sigma(x) = \frac{1}{1 + e^{-k(x - x_0)}}$$
$$\text{Score}_{\text{calibrated}} = \left(\frac{\sigma(x) - \sigma(x_{\min})}{\sigma(x_{\max}) - \sigma(x_{\min})}\right) \times 100$$

Parameters:
- Midpoint $x_0 = 0.15$
- Steepness $k = 22.0$
- Anchor bounds: $x_{\min} = 0.02$, $x_{\max} = 0.35$

**Resulting Mapping:**
- Unrelated resume ($x \le 0.02$): $\approx 0.0$ pts
- Weak match ($x \approx 0.06$): $\approx 7.2$ pts
- Moderate match ($x \approx 0.13$): $\approx 36.2$ pts
- Strong match ($x \approx 0.20$): $\approx 74.6$ pts
- Exceptional match ($x \ge 0.28$): $\ge 95.0$ pts

---

## 4. Hard Knockout Rules

To ensure human recruiters are not presented with candidates who lack critical requirements, the system enforces a mandatory knockout policy:

1. **Trigger Condition:**
   $$\text{Coverage}_{\text{req}} = \frac{\lvert K_{\text{cand}} \cap K_{\text{req}} \rvert}{\lvert K_{\text{req}} \rvert} < 30\%$$
2. **Action:**
   - The candidate's final score is capped at `49.0` (placing them strictly into the `Rejected` band).
   - An explicit alert is logged: `⚠️ Knockout: Required skills coverage (<30%) is below minimum threshold.`

---

## 5. Anti-Gaming Detection & Penalties

To prevent candidates from exploiting algorithmic screening through keyword stuffing or copy-pasting the job description, three heuristics run during evaluation:

1. **Single-Skill Frequency Capping:**
   - If any individual skill appears $> 8$ times in the document, a warning is raised.
2. **Skill Density Ratio:**
   $$\text{Density} = \frac{\text{Total Skill Mentions}}{\text{Total Document Words}}$$
   - If $\text{Density} > 35\%$ (and word count $> 40$), the candidate is flagged for keyword stuffing.
3. **Verbatim JD Overlap:**
   - If raw cosine similarity $\ge 0.88$, the candidate is flagged for verbatim copy-paste.

**Penalty Calculation:**
$$P_{\text{gaming}} = \min(50.0, 25.0 \times \text{Flag Count})$$
Penalties are deducted directly from the final score and prominently highlighted in the UI.

---

## 6. Worked Example

Consider a candidate applying for **Senior Python Backend Engineer**:
- **Requirements:** 6 required skills (`python`, `fastapi`, `postgresql`, `docker`, `rest api`, `microservices`), 3.0 years min exp, Bachelor's degree.
- **Candidate Profile:**
  - Matches 5/6 required skills (missing `microservices`): $S_1 = \frac{5}{6} \times 100 = 83.3$
  - Matches 2/4 preferred skills (`aws`, `ci/cd`): $S_2 = 50.0$
  - Blended similarity yields calibrated score: $S_3 = 78.5$
  - Has 4.0 years experience ($\ge 3.0$ required): $S_4 = 100.0$
  - Holds Master's degree ($\ge \text{Bachelor}$): $S_5 = 100.0$
  - 6 of 7 matched skills verified in work history bullets: $S_6 = \frac{6}{7} \times 100 = 85.7$
  - Anti-gaming flags: 0 ($P_{\text{gaming}} = 0$)

$$\text{Contribution} = (0.40 \times 83.3) + (0.10 \times 50.0) + (0.20 \times 78.5) + (0.15 \times 100.0) + (0.10 \times 100.0) + (0.05 \times 85.7)$$
$$\text{Contribution} = 33.32 + 5.00 + 15.70 + 15.00 + 10.00 + 4.29 = \mathbf{83.31}$$

**Final Score:** `83.3 / 100` $\rightarrow$ Classified as **`Shortlisted`** (Rank #1).
