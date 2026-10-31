"""Script to programmatically generate 13 synthetic sample resumes (PDF and DOCX).

Covers diverse qualification tiers across Python Backend, MERN Full-stack, Data Analyst,
keyword-stuffed attempts, non-technical backgrounds, and scanned image documents.
All personal data is completely fictional.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import docx
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from src.config import SAMPLE_RESUMES_DIR


def create_pdf_resume(filepath: Path, lines: list[str]) -> None:
    """Generate a clean single/multi-page PDF resume using ReportLab."""
    c = canvas.Canvas(str(filepath), pagesize=letter)
    width, height = letter
    y = height - 50
    line_height = 14

    for line in lines:
        if y < 50:
            c.showPage()
            y = height - 50

        if line.startswith("==="):
            # Section header separator
            c.setStrokeColorRGB(0.7, 0.7, 0.7)
            c.line(50, y + 5, width - 50, y + 5)
            y -= 10
            continue

        if line.isupper() and len(line) < 40 and not line.startswith(" "):
            c.setFont("Helvetica-Bold", 12)
            c.setFillColorRGB(0.1, 0.2, 0.4)
            c.drawString(50, y, line)
            y -= line_height + 4
        elif line.startswith("# "):
            c.setFont("Helvetica-Bold", 16)
            c.setFillColorRGB(0.05, 0.1, 0.25)
            c.drawString(50, y, line[2:])
            y -= line_height + 8
        elif line.startswith("## "):
            c.setFont("Helvetica-Bold", 11)
            c.setFillColorRGB(0.2, 0.2, 0.2)
            c.drawString(50, y, line[3:])
            y -= line_height + 2
        elif line.startswith("- "):
            c.setFont("Helvetica", 9.5)
            c.setFillColorRGB(0.15, 0.15, 0.15)
            c.drawString(65, y, "•  " + line[2:])
            y -= line_height
        else:
            c.setFont("Helvetica", 9.5)
            c.setFillColorRGB(0.15, 0.15, 0.15)
            c.drawString(50, y, line)
            y -= line_height

    c.save()


def create_docx_resume(filepath: Path, lines: list[str]) -> None:
    """Generate a valid DOCX resume using python-docx."""
    doc = docx.Document()

    for line in lines:
        if line.startswith("# "):
            p = doc.add_heading(line[2:], level=1)
        elif line.isupper() and len(line) < 40 and not line.startswith(" "):
            p = doc.add_heading(line, level=2)
        elif line.startswith("## "):
            p = doc.add_heading(line[3:], level=3)
        elif line.startswith("- "):
            p = doc.add_paragraph(line[2:], style="List Bullet")
        elif line.startswith("==="):
            continue
        else:
            doc.add_paragraph(line)

    doc.save(str(filepath))


def create_blank_scanned_pdf(filepath: Path) -> None:
    """Generate an unreadable / image-only blank PDF page."""
    c = canvas.Canvas(str(filepath), pagesize=letter)
    # Simulate a scanned page by drawing non-text vectors
    c.setStrokeColorRGB(0.9, 0.9, 0.9)
    c.rect(50, 50, 500, 700, fill=0)
    c.showPage()
    c.save()


def generate_all_sample_resumes(output_dir: Path = SAMPLE_RESUMES_DIR) -> None:
    """Generate the full set of 13 synthetic candidate resumes."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Strong Python Backend (PDF)
    r1_lines = [
        "# Aarav Sharma",
        "aarav.sharma@gmail.com | +91 9876543210 | Bangalore, India",
        "===",
        "PROFESSIONAL SUMMARY",
        "High-performing Senior Backend Engineer with 4.5 years of experience architecting distributed cloud systems.",
        "Specialized in Python, FastAPI, Docker, and PostgreSQL with proven expertise in AWS and microservices.",
        "===",
        "TECHNICAL SKILLS",
        "Languages: Python, SQL, Bash, C++",
        "Backend: FastAPI, Django, REST APIs, Microservices, Celery, Redis",
        "Databases: PostgreSQL, MySQL, Redis",
        "Cloud & DevOps: Docker, Kubernetes, AWS, CI/CD, GitHub Actions",
        "Tools & Testing: Git, PyTest, Postman, Linux",
        "===",
        "WORK EXPERIENCE",
        "## Senior Backend Developer | InnoCloud Systems (Jan 2022 - Present)",
        "- Architected 12+ microservices using Python and FastAPI handling 50k requests per second.",
        "- Tuned complex PostgreSQL queries and indexing, reducing p95 database latency by 45%.",
        "- Containerized all application services with Docker and orchestrated deployments on AWS ECS.",
        "- Implemented automated CI/CD pipelines with GitHub Actions and PyTest unit test coverage.",
        "## Software Engineer | DataPulse Technologies (Jun 2020 - Dec 2021)",
        "- Developed REST APIs and asynchronous background task workers using Python, Django, and Celery.",
        "- Integrated Redis caching layer to lower read load on PostgreSQL by 60%.",
        "===",
        "EDUCATION",
        "## Master of Technology (M.Tech) in Computer Science",
        "National Institute of Technology (2018 - 2020) | CGPA: 8.9/10",
        "## Bachelor of Technology (B.Tech) in Computer Science",
        "State University (2014 - 2018)",
    ]
    create_pdf_resume(output_dir / "resume_01_strong_python_backend.pdf", r1_lines)

    # 2. Medium Python Backend (DOCX)
    r2_lines = [
        "# Rohan Mehta",
        "rohan.mehta@yahoo.com | +91 9823456789 | Pune, India",
        "===",
        "SUMMARY",
        "Software Engineer with 2 years of backend experience working with Python, FastAPI, and PostgreSQL.",
        "===",
        "TECHNICAL SKILLS",
        "Python, FastAPI, PostgreSQL, Docker, Git, REST APIs, Linux",
        "===",
        "WORK EXPERIENCE",
        "## Backend Developer | WebSolutions LLP (Oct 2023 - Present)",
        "- Built RESTful endpoints using FastAPI and connected with PostgreSQL database.",
        "- Created Docker containers for local development and staging environments.",
        "## Junior Developer | TechCraft Pvt Ltd (Sep 2022 - Aug 2023)",
        "- Wrote Python automation scripts and assisted in backend API development.",
        "===",
        "EDUCATION",
        "## B.Tech in Information Technology",
        "Pune University (2018 - 2022)",
    ]
    create_docx_resume(output_dir / "resume_02_medium_python_backend.docx", r2_lines)

    # 3. Weak Python Backend (PDF)
    r3_lines = [
        "# Priya Nair",
        "priya.nair@outlook.com | +91 9712345678 | Kochi, India",
        "===",
        "OBJECTIVE",
        "Motivated computer science graduate looking for an entry-level Python developer role.",
        "===",
        "TECHNICAL SKILLS",
        "Python, HTML, CSS, SQLite",
        "===",
        "EXPERIENCE",
        "## Python Trainee | CodeAcademy (Jan 2024 - Jun 2024)",
        "- Learned core Python syntax and built basic command line games.",
        "- Created simple SQLite database queries.",
        "===",
        "EDUCATION",
        "## BCA (Bachelor of Computer Applications)",
        "MG University (2020 - 2023)",
    ]
    create_pdf_resume(output_dir / "resume_03_weak_python_backend.pdf", r3_lines)

    # 4. Keyword Stuffed Python (PDF)
    r4_lines = [
        "# Vicky Kumar",
        "vicky.k@mail.com | +91 9900112233 | Delhi, India",
        "===",
        "SUMMARY",
        "Python Python Python developer with FastAPI FastAPI FastAPI and Docker Docker Docker.",
        "===",
        "TECHNICAL SKILLS",
        "Python, Python, Python, FastAPI, FastAPI, FastAPI, Docker, Docker, PostgreSQL, PostgreSQL, REST API, REST APIs, Microservices, Python, FastAPI, Docker, PostgreSQL, AWS, AWS, Kubernetes, Python",
        "===",
        "WORK EXPERIENCE",
        "## Developer | QuickHire (Jan 2024 - Present)",
        "- Python FastAPI Docker PostgreSQL Python FastAPI Docker PostgreSQL Python FastAPI Docker.",
        "===",
        "EDUCATION",
        "## Bachelor of Science",
        "Delhi University (2020 - 2023)",
    ]
    create_pdf_resume(output_dir / "resume_04_stuffed_python_backend.pdf", r4_lines)

    # 5. Strong MERN Developer (PDF)
    r5_lines = [
        "# Vikram Singhania",
        "vikram.s@gmail.com | +91 9811223344 | Hyderabad, India",
        "===",
        "PROFESSIONAL SUMMARY",
        "Senior Full-Stack MERN Developer with 3.5 years experience engineering scalable responsive web applications.",
        "Extensive production track record with React, Node.js, Express, MongoDB, and TypeScript.",
        "===",
        "TECHNICAL SKILLS",
        "Frontend: React, JavaScript, TypeScript, Next.js, Redux, Tailwind CSS, HTML5, CSS3",
        "Backend: Node.js, Express, REST APIs, GraphQL, Microservices",
        "Databases: MongoDB, Redis, PostgreSQL",
        "DevOps & Tools: Docker, AWS, Git, Jest, Postman",
        "===",
        "WORK EXPERIENCE",
        "## Full-Stack Engineer | AppVentures (Feb 2022 - Present)",
        "- Led front-end architecture using React, Next.js, and Redux Toolkit for SaaS platform with 200k active users.",
        "- Engineered Node.js and Express REST APIs with MongoDB aggregation pipelines.",
        "- Styled responsive UI components using Tailwind CSS and implemented TypeScript type safety.",
        "## Junior Web Developer | DigitalSol (Aug 2021 - Jan 2022)",
        "- Developed responsive user interfaces in React and integrated Express backend APIs.",
        "===",
        "EDUCATION",
        "## B.Tech in Computer Science and Engineering",
        "JNTU Hyderabad (2017 - 2021)",
    ]
    create_pdf_resume(output_dir / "resume_05_strong_mern_developer.pdf", r5_lines)

    # 6. Medium MERN Developer (DOCX)
    r6_lines = [
        "# Sneha Patel",
        "sneha.patel@gmail.com | +91 9723456789 | Ahmedabad, India",
        "===",
        "SUMMARY",
        "Full-stack JavaScript developer with 1.8 years experience building web apps with React and Node.js.",
        "===",
        "SKILLS",
        "JavaScript, React, Node.js, MongoDB, Express, HTML, CSS, Git",
        "===",
        "EXPERIENCE",
        "## Web Developer | ByteWave Systems (Mar 2023 - Present)",
        "- Created web dashboards in React and Node.js backend using Express.",
        "- Wrote MongoDB CRUD operations and managed REST API integrations.",
        "===",
        "EDUCATION",
        "## B.E. in Information Technology",
        "Gujarat Technological University (2018 - 2022)",
    ]
    create_docx_resume(output_dir / "resume_06_medium_mern_developer.docx", r6_lines)

    # 7. Weak MERN Developer (PDF)
    r7_lines = [
        "# Amit Verma",
        "amit.v@gmail.com | +91 9611223344 | Lucknow, India",
        "===",
        "SUMMARY",
        "Front-end enthusiast skilled in HTML, CSS, and basic JavaScript.",
        "===",
        "SKILLS",
        "HTML, CSS, JavaScript, Bootstrap",
        "===",
        "EXPERIENCE",
        "## Web Design Intern | LocalAgency (Jul 2024 - Sep 2024)",
        "- Created static landing pages with HTML and CSS.",
        "===",
        "EDUCATION",
        "## BCA",
        "Lucknow University (2021 - 2024)",
    ]
    create_pdf_resume(output_dir / "resume_07_weak_mern_developer.pdf", r7_lines)

    # 8. Strong Data Analyst (PDF)
    r8_lines = [
        "# Ananya Sen",
        "ananya.sen@gmail.com | +91 9830112233 | Kolkata, India",
        "===",
        "SUMMARY",
        "Lead Data Analyst with 3 years experience delivering business intelligence, automated ETL pipelines, and statistical models.",
        "Expert in SQL, Python, Pandas, NumPy, Tableau, Power BI, and Google BigQuery.",
        "===",
        "TECHNICAL SKILLS",
        "Analytics & BI: Tableau, Power BI, Data Analysis, Statistics, Feature Engineering",
        "Data & Programming: SQL, Python, Pandas, NumPy, BigQuery, Snowflake",
        "Databases & Tools: PostgreSQL, Git, Excel, Jupyter Notebook",
        "===",
        "WORK EXPERIENCE",
        "## Senior Data Analyst | RetailInsights Inc (Jan 2022 - Present)",
        "- Built executive Tableau dashboards tracking 40+ business KPIs across 15 retail territories.",
        "- Developed automated data analysis pipelines in Python with Pandas, NumPy, and BigQuery.",
        "- Executed complex SQL queries and window functions for customer retention analysis.",
        "## Data Analyst | FinTech Corp (Jul 2021 - Dec 2021)",
        "- Designed Power BI reports and performed statistical analysis on payment transactions.",
        "===",
        "EDUCATION",
        "## Bachelor of Science (B.Sc) in Statistics & Data Science",
        "Calcutta University (2017 - 2020)",
    ]
    create_pdf_resume(output_dir / "resume_08_strong_data_analyst.pdf", r8_lines)

    # 9. Medium Data Analyst (DOCX)
    r9_lines = [
        "# Devendra Rao",
        "dev.rao@gmail.com | +91 9845112233 | Bengaluru, India",
        "===",
        "SUMMARY",
        "Data Analyst with 1.5 years experience querying databases with SQL and building Tableau visual reports.",
        "===",
        "SKILLS",
        "SQL, Tableau, Python, Pandas, Excel, Data Analysis",
        "===",
        "EXPERIENCE",
        "## Junior Data Analyst | InfoMetrics (Jul 2023 - Present)",
        "- Wrote SQL queries on PostgreSQL to generate monthly sales summaries.",
        "- Created interactive charts in Tableau for product managers.",
        "===",
        "EDUCATION",
        "## B.Tech in Electronics",
        "VTU (2019 - 2023)",
    ]
    create_docx_resume(output_dir / "resume_09_medium_data_analyst.docx", r9_lines)

    # 10. Weak Data Analyst (PDF)
    r10_lines = [
        "# Kavita Joshi",
        "kavita.j@gmail.com | +91 9867112233 | Jaipur, India",
        "===",
        "SUMMARY",
        "Junior associate seeking analyst roles. Proficient in MS Office.",
        "===",
        "SKILLS",
        "Microsoft Excel, PowerPoint, Word, Basic Data Entry",
        "===",
        "EXPERIENCE",
        "## Office Assistant | Jaipur Traders (Jan 2024 - Jul 2024)",
        "- Maintained spreadsheets and organized financial documents.",
        "===",
        "EDUCATION",
        "## B.Com (Bachelor of Commerce)",
        "Rajasthan University (2020 - 2023)",
    ]
    create_pdf_resume(output_dir / "resume_10_weak_data_analyst.pdf", r10_lines)

    # 11. Non-Technical Resume (Retail Store Manager) (PDF)
    r11_lines = [
        "# Rajesh Kulkarni",
        "rajesh.k@gmail.com | +91 9822112233 | Mumbai, India",
        "===",
        "SUMMARY",
        "Seasoned Retail Store Operations Manager with 7 years managing staff, visual merchandising, and inventory.",
        "===",
        "CORE COMPETENCIES",
        "Store Management, Inventory Control, Customer Service, Retail Sales, Staff Supervision",
        "===",
        "WORK EXPERIENCE",
        "## Store Manager | Fashion Apparel Hub (2018 - Present)",
        "- Supervised 25 floor staff, managed cash registers, and achieved monthly sales targets.",
        "- Handled vendor negotiations and store opening procedures.",
        "===",
        "EDUCATION",
        "## High School Diploma",
        "Mumbai State Board (2014)",
    ]
    create_pdf_resume(output_dir / "resume_11_non_technical_retail.pdf", r11_lines)

    # 12. Scanned / Unreadable Resume (PDF)
    create_blank_scanned_pdf(output_dir / "resume_12_scanned_unreadable.pdf")

    # 13. Strong Polyglot Architect (PDF)
    r13_lines = [
        "# Siddharth Roy",
        "siddharth.roy@gmail.com | +91 9899112233 | Gurgaon, India",
        "===",
        "SUMMARY",
        "Principal Systems Architect with 8 years experience building high-scale distributed infrastructures.",
        "Deep expertise in Python, C++, FastAPI, Docker, Kubernetes, AWS, PostgreSQL, and microservices.",
        "===",
        "TECHNICAL SKILLS",
        "Python, C++, FastAPI, Docker, Kubernetes, AWS, PostgreSQL, Redis, Kafka, CI/CD, Linux, Git",
        "===",
        "WORK EXPERIENCE",
        "## Principal Architect | CloudScale Global (Jan 2020 - Present)",
        "- Architected high performance backend systems using Python and C++ for sub-millisecond trading services.",
        "- Engineered distributed microservices with FastAPI, Docker, and Kubernetes on AWS.",
        "- Implemented relational persistence with PostgreSQL and Redis caching.",
        "## Senior Engineer | TechCore Systems (Jan 2017 - Dec 2019)",
        "- Built backend services in Python and automated CI/CD deployment pipelines.",
        "===",
        "EDUCATION",
        "## B.Tech in Computer Science",
        "IIT Delhi (2012 - 2016)",
    ]
    create_pdf_resume(output_dir / "resume_13_strong_polyglot_long.pdf", r13_lines)

    print(f"Successfully generated {len(os.listdir(output_dir))} sample resumes in {output_dir}")


if __name__ == "__main__":
    generate_all_sample_resumes()
