"""Consistency / fairness test: equivalent CVs should get the same statuses.

Variants of real Kaggle CVs, all run through the full pipeline in ONE run (same job analysis, same model):
  layout   : cv_24038620 as a text PDF  vs  the same CV printed and scanned (vision path)
  wording  : cv_46260230 original       vs  the same text with skills written with synonyms
  missing  : cv_46260230 original       vs  the same CV without its page 2

    docker compose exec api sh -c "cd /app && LLM_FALLBACK_MODELS= python scripts/eval_consistency.py --model gemini-3.5-flash-lite"

LLM_FALLBACK_MODELS= forbids switching model mid-run, so differences come from the CV, not from the model.
Writes eval/consistency_results.md. About 15-20 LLM calls.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

import pymupdf  # noqa: E402

DEMO = ROOT / "data" / "demo"
OUT = ROOT / "data" / "consistency"
# wording variant: same facts, other words (all real synonyms a recruiter would accept)
SYNONYMS = [
    (r"Windows OS", "Microsoft Windows"), (r"Mac OS", "Apple macOS"), (r"Active Directory", "AD (directory services)"),
    (r"customer service", "client support"), (r"customers", "clients"), (r"troubleshoot", "diagnose and fix"),
    (r"Tier 1", "first-line"), (r"help desk", "service desk"),
]


def text_pdf(text: str, dst: Path):
    """Write plain text to a simple single-column PDF (keeps the wording, drops the original layout)."""
    import textwrap
    lines = [w for line in text.splitlines() for w in (textwrap.wrap(line, 100) or [""])]
    doc = pymupdf.open()
    for start in range(0, len(lines), 66):
        page = doc.new_page()
        for i, line in enumerate(lines[start:start + 66]):
            page.insert_text((50, 60 + i * 11), line, fontsize=9)
    doc.save(dst)


def make_variants() -> dict[str, Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    src = pymupdf.open(DEMO / "cv_46260230.pdf")
    original_text = "\n".join(p.get_text("text", sort=True) for p in src)
    # the wording variant is rebuilt from text, so its "original" twin is rebuilt the same way (same layout)
    text_pdf(original_text, OUT / "wording_original.pdf")
    reworded = original_text
    for pattern, repl in SYNONYMS:
        reworded = re.sub(pattern, repl, reworded, flags=re.I)
    text_pdf(reworded, OUT / "wording_synonyms.pdf")
    missing = pymupdf.open(DEMO / "cv_46260230.pdf")
    missing.delete_page(1)  # drop page 2
    missing.save(OUT / "missing_page2.pdf")
    return {
        "layout_text": DEMO / "cv_24038620.pdf",
        "layout_scan": DEMO / "cv_24038620_scanned.pdf",
        "wording_original": OUT / "wording_original.pdf",
        "wording_synonyms": OUT / "wording_synonyms.pdf",
        "missing_full": DEMO / "cv_46260230.pdf",
        "missing_page2": OUT / "missing_page2.pdf",
    }


PAIRS = [("layout", "layout_text", "layout_scan"), ("wording", "wording_original", "wording_synonyms"),
         ("missing page", "missing_full", "missing_page2")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    args = ap.parse_args()
    if args.model:
        os.environ["LLM_MODEL"] = os.environ["VISION_MODEL"] = args.model
    from smartrecruit import config, pipeline, scoring, store  # imported after the model is set

    variants = make_variants()
    names = list(variants)
    result = pipeline.run(str(DEMO / "job_it_support_specialist.txt"), [str(variants[n]) for n in names])
    run_id = result["run_id"]
    job = store.load(run_id, "job")
    by_variant = {}
    for name, cid in zip(names, [c["candidate_id"] for c in store.load(run_id, "run")["cv_files"]]):
        audit = store.load(run_id, f"{cid}_audit")
        by_variant[name] = {"statuses": {a["requirement_id"]: a["status"] for a in audit["match"]["assessments"]},
                            **scoring.score(audit["match"], job, store.load(run_id, f"{cid}_read"))}

    lines = [f"Run {run_id} · model {config.LLM_MODEL} · prompts {config.PROMPT_VERSIONS}", "",
             "| Pair | Score A | Score B | Same status | Requirements that changed |", "|---|---|---|---|---|"]
    for label, a, b in PAIRS:
        sa, sb = by_variant[a], by_variant[b]
        changed = [f"{r}: {sa['statuses'][r]} → {sb['statuses'].get(r)}" for r in sa["statuses"] if sa["statuses"][r] != sb["statuses"].get(r)]
        same = len(sa["statuses"]) - len(changed)
        lines.append(f"| {label} ({a} vs {b}) | {sa['score']} | {sb['score']} | {same}/{len(sa['statuses'])} | {'; '.join(changed) or '–'} |")
    lines += ["", "Requirements: " + "; ".join(f"{r['id']} {r['text']}" for r in job["requirements"]),
              "", "Reading quality: " + "; ".join(f"{n}: {v['reading_quality']['status']}" for n, v in by_variant.items())]
    (ROOT / "eval" / "consistency_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ROOT / "eval" / "consistency_results.json").write_text(json.dumps({"run_id": run_id, **by_variant}, indent=2), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
