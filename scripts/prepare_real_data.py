"""Build the real demo set from the downloaded datasets.

Sources (run scripts/download_resumes.py and download job_postings.csv first, see README):
  - CVs: Kaggle "Resume Dataset" (snehaanbhawal, CC0), via the HF mirror opensporks/resumes
  - Job offers: LinkedIn job postings, HF xanderios/linkedin-job-postings (MIT, 33k postings)

Output:
  data/jobs/offers/<slug>.txt      the three real offers, cleaned (encoding, glued headings)
  data/jobs/offers/sources.json    job_id, title, LinkedIn URL
  data/demo/                        the demo CVs (real PDFs) + one print-and-scan copy (image-only PDF)

    python scripts/prepare_real_data.py
"""
import csv
import json
import random
import re
import shutil
from pathlib import Path

import pymupdf
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
csv.field_size_limit(10**9)

OFFERS = {
    "3754918008": "it_support_specialist",   # main demo offer
    "3757496271": "it_manager",
    "3699082310": "systems_administrator",
}
# picked by TF-IDF similarity to the IT Support Specialist offer: high, middle, low
DEMO_CVS = {"46260230": "strong match", "24038620": "different profile (IT director)", "39718499": "weak match (mislabelled CV)"}
SCAN = "24038620"  # this one is also turned into a scanned copy to exercise the vision path


def clean(text: str) -> str:
    text = text.replace("�", "'").replace("’", "'").replace("•", "-")
    # LinkedIn exports glue list items and headings: "...desired.Minimum of 1 year" / "RequirementsA degree"
    text = re.sub(r"([A-Za-z\)])\.([A-Z][a-z])", r"\1.\n\2", text)
    text = re.sub(r"(Requirements|Responsibilities|Qualifications|Experience|Benefits)([A-Z])", r"\1\n\2", text)
    text = re.sub(r"([a-z])(Compensation|Reports to|Department|Location):", r"\1\n\2:", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def scan_copy(src: Path, dst: Path, seed: int = 7):
    """Simulate print-and-scan: render each page, grayscale, slight rotation, noise, blur; keep only the image."""
    random.seed(seed)
    out = pymupdf.open()
    for page in pymupdf.open(src):
        pix = page.get_pixmap(dpi=150, colorspace=pymupdf.csGRAY)
        img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        px = img.load()
        for _ in range(pix.width * pix.height // 400):
            px[random.randrange(pix.width), random.randrange(pix.height)] = random.randint(110, 200)
        img = img.rotate(random.uniform(-0.9, 0.9), fillcolor=245, resample=Image.BICUBIC).filter(ImageFilter.GaussianBlur(0.5))
        tmp = dst.with_suffix(".png")
        img.save(tmp)
        p = out.new_page(width=page.rect.width, height=page.rect.height)
        p.insert_image(p.rect, filename=str(tmp))
        tmp.unlink()
    out.save(dst)


def main():
    offers_dir = ROOT / "data" / "jobs" / "offers"
    offers_dir.mkdir(parents=True, exist_ok=True)
    sources = []
    with open(ROOT / "data" / "jobs" / "job_postings.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["job_id"] in OFFERS:
                slug = OFFERS[r["job_id"]]
                (offers_dir / f"{slug}.txt").write_text(f"{r['title']}\n\n{clean(r['description'])}\n", encoding="utf-8")
                sources.append({"file": f"{slug}.txt", "job_id": r["job_id"], "title": r["title"],
                                "url": r["job_posting_url"], "dataset": "xanderios/linkedin-job-postings (MIT)"})
    (offers_dir / "sources.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")

    demo = ROOT / "data" / "demo"
    demo.mkdir(parents=True, exist_ok=True)
    pdf_dir = ROOT / "data" / "resumes" / "pdf" / "INFORMATION-TECHNOLOGY"
    for cv_id, why in DEMO_CVS.items():
        shutil.copy(pdf_dir / f"{cv_id}.pdf", demo / f"cv_{cv_id}.pdf")
    scan_copy(pdf_dir / f"{SCAN}.pdf", demo / f"cv_{SCAN}_scanned.pdf")
    shutil.copy(offers_dir / "it_support_specialist.txt", demo / "job_it_support_specialist.txt")
    (demo / "README.md").write_text(
        "# Demo set (real data)\n\nJob offer: `job_it_support_specialist.txt` (LinkedIn job "
        f"{[s for s in sources if s['file'].startswith('it_support')][0]['job_id']}).\n\nCVs (Kaggle Resume Dataset, category INFORMATION-TECHNOLOGY):\n\n"
        + "".join(f"- `cv_{i}.pdf`: {w}\n" for i, w in DEMO_CVS.items())
        + f"- `cv_{SCAN}_scanned.pdf`: the same CV as cv_{SCAN}.pdf, printed and scanned (image only) to test the vision path\n\n"
        "For the 3-CV demo upload: the offer + cv_46260230.pdf + cv_24038620_scanned.pdf + cv_39718499.pdf\n",
        encoding="utf-8")
    print("offers:", [s["file"] for s in sources])
    print("demo:", sorted(p.name for p in demo.iterdir()))


if __name__ == "__main__":
    main()
