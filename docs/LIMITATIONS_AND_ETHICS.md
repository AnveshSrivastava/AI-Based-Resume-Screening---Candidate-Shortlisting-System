# Ethical Considerations, Governance, and System Limitations

This document addresses the ethical obligations, demographic fairness safeguards, legal compliance frameworks, and operational limitations governing the **AI-Based Resume Screening and Candidate Shortlisting System**.

---

## 1. Bias Risks in Algorithmic Resume Screening

Algorithmic recruitment systems inherently run the risk of amplifying systemic societal biases if not carefully engineered and audited. Key risk vectors and our mitigations include:

### A. Keyword & Phrasing Bias
- **Risk:** Highly qualified candidates may describe their technical achievements using phrasing or regional terminology not explicitly captured in a naive dictionary.
- **Mitigation:**
  1. Multi-tiered skill taxonomy with extensive canonical alias resolution (`postgres` $\rightarrow$ `postgresql`, `k8s` $\rightarrow$ `kubernetes`, `restful services` $\rightarrow$ `rest api`).
  2. Guarded fuzzy matching (`rapidfuzz`) to absorb spelling variations and typographical errors.
  3. Continuous human oversight allowing recruiters to manually add or edit required skills in the UI.

### B. Gender & Demographic Profiling
- **Risk:** Training black-box models on historical recruitment data can inadvertently learn proxies for gender, ethnicity, or socioeconomic status (e.g., women's colleges, non-traditional career breaks).
- **Mitigation:**
  - This system uses **no historical training labels** and no deep learning models trained on biased corporate hiring logs.
  - Evaluation is derived solely from deterministic, transparent criteria (skill presence, verified experience durations, and degree credentials).

---

## 2. Privacy & Data Protection Safeguards

### In-Memory Non-Persistence Architecture
- **Zero Disk Footprint:** Uploaded documents (PDFs, DOCXs, TXTs) are processed strictly in RAM as `io.BytesIO` streams. Resumes are discarded once the user session closes.
- **No Third-Party Transmission:** Candidate resume data is processed locally within the application runtime. No candidate text or extracted data is transmitted to external cloud APIs or proprietary LLM providers.

### PII Masking by Default
- The system automatically redacts Personally Identifiable Information (PII), specifically email addresses and telephone numbers, in all displayed tables and exported ranking files.
- Recruiters can evaluate candidate qualifications based strictly on competence before uncovering identifying contact information.

---

## 3. Regulatory & Legal Frameworks

### India Digital Personal Data Protection (DPDP) Act 2023
The system is architected in accordance with key data protection principles outlined in India's DPDP Act:
- **Purpose Limitation:** Candidate resumes are processed strictly for the explicit purpose of job application matching.
- **Data Minimization:** Only fields directly relevant to role qualifications (skills, experience, degree) are parsed; sensitive demographic fields are ignored.
- **Storage Limitation:** In-memory execution ensures data is not retained beyond the immediate screening session.

### EU AI Act Categorization
Under the European Union Artificial Intelligence Act, AI systems utilized in **employment, workers management, and access to self-employment** are classified as **High-Risk AI Systems**. Such systems require:
1. High quality of datasets and risk management.
2. Complete technical documentation and logging.
3. Appropriate human-machine interface tools to enable **effective human oversight**.

Our system implements this through detailed score breakdowns, explainability logs, and explicit disclaimers designating all outputs as recruiter decision support.

---

## 4. Human-in-the-Loop Imperative

> [!IMPORTANT]
> **This system is strictly designed as an assistive decision-support tool for human recruiters.**
> It is **NOT** an autonomous hiring agent, and it must never be used to execute automated job rejections without human review.

- Candidates in the **Review** and **Rejected** bands should be periodically spot-checked to catch non-traditional resumes, portfolio-based candidates, or military/veteran transitions that traditional parsers might miss.
- Recruiters remain legally, ethically, and operationally accountable for all candidate shortlisting and interview decisions.

---

## 5. Prohibited Uses

The system **MUST NOT** be used for:
1. **Fully Automated Hiring or Termination:** Making unilateral employment decisions without human recruiter review.
2. **Demographic Filtering:** Attempting to infer or filter candidates based on age, gender, caste, race, nationality, religion, disability, or marital status.
3. **Unconsented Talent Scraping:** Ingesting candidate profiles scraped from personal websites or social networks without applicant knowledge and consent.
4. **Surveillance or Continuous Profiling:** Building persistent surveillance databases of candidate histories across external organizations.
