"""Download the Kaggle "Resume Dataset" (snehaanbhawal, CC0, 2,484 CVs scraped from livecareer.com)
from its Hugging Face mirror (opensporks/resumes), which needs no Kaggle account.

    python scripts/download_resumes.py                         # CSV + all INFORMATION-TECHNOLOGY PDFs
    python scripts/download_resumes.py --categories HR,FINANCE --max 30

Files land in data/resumes/: Resume.csv and pdf/<CATEGORY>/<ID>.pdf
"""
import argparse
import sys
from pathlib import Path

import httpx

REPO = "https://huggingface.co/datasets/opensporks/resumes"
API = "https://huggingface.co/api/datasets/opensporks/resumes/tree/main"
OUT = Path(__file__).resolve().parents[1] / "data" / "resumes"


def download(url: str, dst: Path):
    if dst.exists() and dst.stat().st_size > 0:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=True, timeout=300) as r:
        r.raise_for_status()
        with open(dst, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--categories", default="INFORMATION-TECHNOLOGY")
    ap.add_argument("--max", type=int, default=None, help="max PDFs per category")
    ap.add_argument("--no-csv", action="store_true")
    args = ap.parse_args()

    if not args.no_csv:
        print("Resume.csv (56 MB)...")
        download(f"{REPO}/resolve/main/Resume/Resume.csv", OUT / "Resume.csv")

    for cat in args.categories.split(","):
        files = httpx.get(f"{API}/data/data/{cat}", timeout=60).json()
        if not isinstance(files, list):
            sys.exit(f"Unknown category {cat}: {files}")
        files = [f["path"] for f in files if f["path"].endswith(".pdf")][:args.max]
        for i, path in enumerate(files, 1):
            download(f"{REPO}/resolve/main/{path}", OUT / "pdf" / cat / Path(path).name)
            print(f"\r{cat}: {i}/{len(files)}", end="")
        print()


if __name__ == "__main__":
    main()
