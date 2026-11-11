"""End-to-end evaluation, step 1: export a run's conclusions to a review sheet for two human reviewers.

One row per (candidate, requirement): what the system concluded, its reasoning, its quotes and the audit
verdict. Each reviewer reads the CV and fills, independently:
  reviewer_N_status        : met | partial | missing   (what the CV really shows)
  reviewer_N_evidence_ok   : 1 if the quotes really support the system's status, 0 if not, empty if no quote

    python scripts/export_review.py 20261028-160545-a88e88
    -> eval/annotation/review_<run_id>.csv   (open with Excel / LibreOffice / Google Sheets)

Then: python scripts/score_review.py eval/annotation/review_<run_id>.csv
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    run_id = sys.argv[1]
    run = ROOT / "data" / "runs" / run_id
    job = json.loads((run / "job.json").read_text(encoding="utf-8"))
    meta = json.loads((run / "run.json").read_text(encoding="utf-8"))
    reqs = {r["id"]: r for r in job["requirements"]}
    out = ROOT / "eval" / "annotation" / f"review_{run_id}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["candidate_id", "cv_file", "requirement_id", "type", "requirement", "system_status", "system_reasoning",
                    "system_quotes", "audit", "reviewer_1_status", "reviewer_1_evidence_ok", "reviewer_2_status",
                    "reviewer_2_evidence_ok", "comment"])
        for c in meta["cv_files"]:
            audit_path = run / f"{c['candidate_id']}_audit.json"
            if not audit_path.exists():
                continue
            match = json.loads(audit_path.read_text(encoding="utf-8"))["match"]
            for a in match["assessments"]:
                r = reqs[a["requirement_id"]]
                quotes = " || ".join(f"{e['quote']} (p.{e.get('page', '?')})" for e in a.get("evidence", []) if e.get("found", True))
                w.writerow([c["candidate_id"], c["original_name"], a["requirement_id"], r["type"], r["text"], a["status"],
                            a.get("reasoning", ""), quotes, a.get("audit", ""), "", "", "", "", ""])
                rows += 1
    print(f"{rows} rows -> {out}")


if __name__ == "__main__":
    main()
