"""Before / after evidence for the prompt library: run v1 and v2 of the CV and Job agents
on the sample data and measure the failures each version shows.

    python scripts/compare_prompts.py

Writes eval/prompt_runs/<agent>_<version>_<sample>.json and eval/prompt_runs/summary.md.
Checks (computed in code, so they are reproducible):
  cv_agent  : skills without a quote, quotes not found in the CV, protected attributes output
  job_agent : number of requirements, compound requirements, discriminatory criterion kept
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from smartrecruit import anonymizer, llm, prompts  # noqa: E402
from smartrecruit.agents.audit_agent import quote_in_cv  # noqa: E402

OUT = ROOT / "eval" / "prompt_runs"
PROTECTED = re.compile(r"\b(age|born|birth|gender|nationality|married)\b", re.I)


def cv_checks(out: dict, cv_text: str) -> dict:
    skills = out.get("skills", [])
    names = [s if isinstance(s, str) else s.get("name", "") for s in skills]
    quotes = [s.get("evidence") for s in skills if isinstance(s, dict)]
    return {
        "skills": len(skills),
        "skills_without_quote": sum(1 for q in quotes if not q) + sum(isinstance(s, str) for s in skills),
        "quotes_not_in_cv": sum(1 for q in quotes if q and not quote_in_cv(q, cv_text)[0]),
        "skills_not_in_cv": [n for n in names if n and n.lower() not in cv_text.lower()],
        "protected_attributes_output": bool(PROTECTED.search(json.dumps(out))),
    }


def job_checks(out: dict) -> dict:
    reqs = out.get("requirements", [])
    texts = [r.get("text", "") for r in reqs]
    return {
        "requirements": len(reqs),
        "must": sum(r.get("type") == "must" for r in reqs),
        "compound_requirements": [t for t in texts if re.search(r"\b(and|,)\b", t) and not re.search(r"\bor\b", t)],
        "age_criterion_kept": any("age" in t.lower() for t in texts),
        "soft_skills_as_must": [r.get("text") for r in reqs if r.get("category") == "soft" and r.get("type") == "must"],
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gt = ROOT / "data" / "samples" / "ground_truth"
    job_text = (ROOT / "data" / "samples" / "job_offer_data_engineer.txt").read_text(encoding="utf-8")
    lines = ["| Agent | Version | Sample | Checks |", "|---|---|---|---|"]

    for version in ("v1", "v2"):
        system, user = prompts.load("job_agent", version)
        out = llm.chat_json(system, prompts.render(user, job_text=job_text))
        (OUT / f"job_agent_{version}_job_offer.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        lines.append(f"| job_agent | {version} | job offer | {json.dumps(job_checks(out), ensure_ascii=False)} |")

        for cv in sorted(gt.glob("*.txt")):
            text = anonymizer.anonymize(cv.read_text(encoding="utf-8"), "candidate")["text"]
            system, user = prompts.load("cv_agent", version)
            out = llm.chat_json(system, prompts.render(user, cv_text=text))
            (OUT / f"cv_agent_{version}_{cv.stem}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
            lines.append(f"| cv_agent | {version} | {cv.stem} | {json.dumps(cv_checks(out, text), ensure_ascii=False)} |")
        print("\n".join(lines))

    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
