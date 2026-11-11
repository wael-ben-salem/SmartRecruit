"""Generate the demo data: one job offer and three fictional CVs with different layouts.

  cv_A_single_column.pdf : classic text PDF, 2 pages          -> text path
  cv_B_two_columns.pdf   : sidebar + main column             -> vision path (layout)
  cv_C_scanned.pdf       : page image only, slightly rotated -> vision path (scan)

All people and companies are fictional. Ground-truth text for each CV is written to
data/samples/ground_truth/ and used by the retrieval evaluation.

    python scripts/make_samples.py
"""
import io
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parents[1] / "data" / "samples"
GT = OUT / "ground_truth"

JOB_OFFER = """Data Engineer (junior to mid-level) - NovaTech Consulting, Tunis / hybrid

About the role
You will design and run the data pipelines of our clients in banking and retail.

Requirements
- At least 2 years of professional experience with Python.
- Strong SQL skills (PostgreSQL or equivalent).
- Experience with Apache Spark or another distributed processing framework.
- Hands-on experience with Docker.
- Engineering degree or Master's degree in computer science, data science or a related field.
- Professional English (written and spoken).

Nice to have
- Kubernetes.
- Workflow orchestration with Airflow.
- Experience with a cloud platform (Azure or AWS).
- CI/CD practices.
- French is a plus.
- Candidates aged 25 to 30 preferred.
"""

CV_A = {
    "name": "Sarah Martin",
    "contact": "sarah.martin@example.com | +216 22 345 678 | linkedin.com/in/sarah-martin-data | Date of birth: 14/03/1999",
    "sections": [
        ("PROFILE", ["Data engineer with 3 years of experience building batch and streaming pipelines for finance clients."]),
        ("EXPERIENCE", [
            "Data Engineer - Nordlake Analytics (09/2023 - present)",
            "Built batch and streaming pipelines in Python and Apache Spark processing 2 TB of transactions per day.",
            "Orchestrated 40+ daily jobs with Airflow and reduced pipeline failures by 30%.",
            "Packaged every service with Docker and deployed them on Kubernetes (AKS).",
            "Set up CI/CD with GitHub Actions for the data platform.",
            "Data Engineering Intern - Banque Atlas (02/2023 - 08/2023)",
            "Wrote SQL reporting queries on PostgreSQL for the risk team.",
            "Built Power BI dashboards used by 50 analysts.",
        ]),
        ("EDUCATION", [
            "Engineering degree in Data Science - Esprit School of Engineering (2023)",
            "Preparatory classes in mathematics and physics (2018)",
        ]),
        ("SKILLS", ["Python, SQL, Apache Spark, Airflow, Docker, Kubernetes, Microsoft Azure, Git, Power BI"]),
        ("LANGUAGES", ["French: native", "English: C1 (TOEIC 945)", "Arabic: native"]),
        ("CERTIFICATIONS", ["Microsoft Certified: Azure Data Engineer Associate (DP-203), 2024"]),
    ],
}

CV_B = {
    "name": "Youssef Haddad",
    "sidebar": [
        ("CONTACT", ["y.haddad@example.org", "+216 98 765 432", "github.com/yhaddad"]),
        ("SKILLS", ["JS / TypeScript", "Node.js", "Python", "k8s", "Docker", "MongoDB", "Git"]),
        ("LANGUAGES", ["Arabic: native", "French: C1", "English: B2"]),
    ],
    "main": [
        ("PROFILE", ["Full-stack developer moving towards data engineering, with 4 years of experience shipping web platforms."]),
        ("EXPERIENCE", [
            "Full-stack Developer - Webify (01/2022 - present)",
            "Developed REST APIs in Node.js and TypeScript for 200k users.",
            "Containerised the services with Docker and deployed them on k8s.",
            "Wrote Python scripts to clean CSV exports and load them into MongoDB.",
            "Junior Web Developer - PixelHouse (07/2021 - 12/2021)",
            "Built front-end features in JavaScript and React.",
        ]),
        ("PROJECTS", ["Real-time dashboard with Kafka and Spark Streaming (school project, 2021)"]),
        ("EDUCATION", ["Master's degree in Software Engineering - ISI Tunis (2021)"]),
    ],
}

CV_C = {
    "name": "Amira Ben Salah",
    "lines": [
        "amira.bensalah@example.net - +216 55 111 222",
        "",
        "PROFILE",
        "Junior data analyst, curious and rigorous, looking for a first job in data.",
        "",
        "EXPERIENCE",
        "Data Analyst Intern - RetailOne (03/2025 - 08/2025)",
        "Cleaned sales data with Python (pandas) and built weekly reports.",
        "Wrote SQL queries on MySQL to analyse customer churn.",
        "",
        "EDUCATION",
        "Bachelor's degree in Business Computing - ISG Tunis (2025)",
        "",
        "SKILLS",
        "Python (pandas), SQL, MySQL, Excel, Tableau",
        "",
        "LANGUAGES",
        "French: fluent - English: B1",
    ],
}


def _text_cv_a(path: Path) -> str:
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    lines_out, page = ["[page 1]"], 1
    y = h - 60
    c.setFont("Helvetica-Bold", 20); c.drawString(50, y, CV_A["name"]); lines_out.append(CV_A["name"]); y -= 20
    c.setFont("Helvetica", 9); c.drawString(50, y, CV_A["contact"]); lines_out.append(CV_A["contact"]); y -= 30
    for title, items in CV_A["sections"]:
        if title == "EDUCATION":  # force a second page to test page numbers
            c.showPage(); page += 1; y = h - 60; lines_out.append(f"[page {page}]")
        c.setFont("Helvetica-Bold", 12); c.drawString(50, y, title); lines_out.append(title); y -= 18
        c.setFont("Helvetica", 10)
        for it in items:
            c.drawString(60, y, it); lines_out.append(it); y -= 15
        y -= 12
    c.save()
    return "\n".join(lines_out)


def _two_columns_cv_b(path: Path) -> str:
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    c.setFillColorRGB(0.09, 0.14, 0.23); c.rect(0, 0, 180, h, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 16); c.drawString(20, h - 60, "Youssef"); c.drawString(20, h - 80, "Haddad")
    y = h - 120
    for title, items in CV_B["sidebar"]:
        c.setFont("Helvetica-Bold", 11); c.drawString(20, y, title); y -= 16
        c.setFont("Helvetica", 9)
        for it in items:
            c.drawString(24, y, it); y -= 13
        y -= 14
    c.setFillColorRGB(0.1, 0.1, 0.1)
    y = h - 60
    for title, items in CV_B["main"]:
        c.setFont("Helvetica-Bold", 12); c.drawString(200, y, title); y -= 18
        c.setFont("Helvetica", 9.5)
        for it in items:
            c.drawString(208, y, it); y -= 14
        y -= 12
    c.save()
    main = [l for t, items in CV_B["main"] for l in [t, *items]]
    side = [l for t, items in CV_B["sidebar"] for l in [t, *items]]
    return "\n".join(["[page 1]", CV_B["name"], *main, *side])


def _scanned_cv_c(path: Path) -> str:
    W, H = 1240, 1754  # A4 at 150 dpi
    img = Image.new("L", (W, H), 250)
    d = ImageDraw.Draw(img)
    try:
        big, font = ImageFont.truetype("arial.ttf", 44), ImageFont.truetype("arial.ttf", 24)
        bold = ImageFont.truetype("arialbd.ttf", 26)
    except OSError:
        big = font = bold = ImageFont.load_default()
    y = 110
    d.text((110, y), CV_C["name"], font=big, fill=20); y += 80
    for line in CV_C["lines"]:
        f = bold if line.isupper() else font
        d.text((110, y), line, font=f, fill=35); y += 40 if line else 18
    random.seed(7)
    for _ in range(2500):  # scanner noise
        d.point((random.randint(0, W - 1), random.randint(0, H - 1)), fill=random.randint(120, 200))
    img = img.rotate(0.8, fillcolor=250, resample=Image.BICUBIC).filter(ImageFilter.GaussianBlur(0.6))
    buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawImage(ImageReader(buf), 0, 0, width=A4[0], height=A4[1])
    c.save()
    return "\n".join(["[page 1]", CV_C["name"], *[l for l in CV_C["lines"] if l]])


def main():
    GT.mkdir(parents=True, exist_ok=True)
    (OUT / "job_offer_data_engineer.txt").write_text(JOB_OFFER, encoding="utf-8")
    jc = canvas.Canvas(str(OUT / "job_offer_data_engineer.pdf"), pagesize=A4)
    y = A4[1] - 60
    for line in JOB_OFFER.splitlines():
        jc.setFont("Helvetica-Bold" if line and not line.startswith("-") and len(line) < 40 else "Helvetica", 10)
        jc.drawString(50, y, line); y -= 15
    jc.save()
    for name, fn in [("cv_A_single_column", _text_cv_a), ("cv_B_two_columns", _two_columns_cv_b), ("cv_C_scanned", _scanned_cv_c)]:
        truth = fn(OUT / f"{name}.pdf")
        (GT / f"{name}.txt").write_text(truth, encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
