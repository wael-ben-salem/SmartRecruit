"""Audit Agent: checks that every conclusion is supported by the CV.

Two layers:
  1. code: each quote must really appear in the anonymized CV (exact or near-exact match)
  2. LLM verifier: does the quote, as written, support the status given for that requirement?
If some claims fail, the Audit agent sends them back ONCE to the Matching agent with
feedback, then audits again. Claims still unsupported are marked 'unverified' and count
as 0 in the score; the recruiter sees them flagged.
"""
import json
import re
from difflib import SequenceMatcher

from .. import config, llm, prompts
from . import matching_agent

NEAR_MATCH = 0.9


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w%+#./ ]", " ", s.lower())).strip()


def quote_in_cv(quote: str, cv_text: str) -> tuple[bool, float]:
    """True if the quote is in the CV text, allowing small differences (spacing, punctuation, OCR)."""
    q, t = _norm(quote), _norm(cv_text)
    if not q:
        return False, 0.0
    if q in t:
        return True, 1.0
    words, n = t.split(), len(q.split())
    best = 0.0
    for i in range(0, max(1, len(words) - n + 1)):
        window = " ".join(words[i:i + n])
        best = max(best, SequenceMatcher(None, q, window).ratio())
        if best >= NEAR_MATCH:
            return True, round(best, 3)
    return False, round(best, 3)


def check_quotes(match: dict, cv_text: str) -> list[dict]:
    results = []
    for a in match["assessments"]:
        quotes = [e for e in a.get("evidence", []) if e.get("quote")]
        checked = [{**e, "found": (r := quote_in_cv(e["quote"], cv_text))[0], "similarity": r[1]} for e in quotes]
        a["evidence"] = checked
        found = [e for e in checked if e["found"]]
        if a.get("status") in ("met", "partial") and not found:
            issue = "no quote given" if not quotes else "quote not found in the CV"
            results.append({"requirement_id": a["requirement_id"], "verdict": "unsupported", "comment": issue, "layer": "code"})
    return results


def llm_verify(match: dict, job: dict) -> list[dict]:
    reqs = {r["id"]: r for r in job["requirements"]}
    claims = [{"requirement_id": a["requirement_id"], "requirement": reqs[a["requirement_id"]]["text"],
               "status": a["status"], "quotes": [e["quote"] for e in a.get("evidence", []) if e.get("found")]}
              for a in match["assessments"] if a.get("status") in ("met", "partial") and any(e.get("found") for e in a.get("evidence", []))]
    if not claims:
        return []
    system, user = prompts.load("audit_agent")
    out = llm.chat_json(system, prompts.render(user, claims=json.dumps(claims, ensure_ascii=False)))
    return [{**c, "layer": "llm"} for c in out.get("checks", []) if c.get("verdict") in ("overstated", "unsupported")]


def audit_once(match: dict, job: dict, cv_text: str) -> list[dict]:
    issues = check_quotes(match, cv_text)
    flagged = {i["requirement_id"] for i in issues}
    issues += [i for i in llm_verify(match, job) if i["requirement_id"] not in flagged]
    return issues


def _feedback(issues: list[dict]) -> str:
    lines = [f"- {i['requirement_id']}: {i['verdict']} ({i.get('comment', '')})"
             + (f" -> suggested status: {i['suggested_status']}" if i.get("suggested_status") else "")
             for i in issues]
    return ("The Audit agent rejected these claims. Re-assess them using ONLY verbatim quotes from the "
            "excerpts; if no quote supports the claim, lower the status:\n" + "\n".join(lines))


def run(run_id: str, candidate_id: str, match: dict, job: dict, profile: dict, cv_text: str, allow_retry: bool = True) -> dict:
    rounds = []
    issues = audit_once(match, job, cv_text)
    rounds.append({"round": 1, "issues": issues})

    if issues and allow_retry:
        match = matching_agent.run(run_id, candidate_id, profile, job, feedback=_feedback(issues))
        issues = audit_once(match, job, cv_text)
        rounds.append({"round": 2, "issues": issues, "note": "after one re-match with audit feedback"})

    # Apply the final verdicts: unsupported -> unverified, overstated -> one level down
    final = {i["requirement_id"]: i for i in issues}
    for a in match["assessments"]:
        a["audit"] = "verified" if a["status"] in ("met", "partial") else "n/a"
        issue = final.get(a["requirement_id"])
        if issue:
            a["audit"] = issue["verdict"]
            a["audit_comment"] = issue.get("comment", "")
            a["original_status"] = a["status"]
            if issue["verdict"] == "unsupported":
                a["status"] = "unverified"
            elif issue["verdict"] == "overstated":
                a["status"] = issue.get("suggested_status") if issue.get("suggested_status") in ("partial", "missing") else (
                    "partial" if a["status"] == "met" else "missing")

    return {"candidate_id": candidate_id, "match": match, "rounds": rounds,
            "retried": len(rounds) > 1, "remaining_issues": len(issues),
            "_meta": {"agent": "audit_agent", "prompt_version": config.PROMPT_VERSIONS["audit_agent"], "model": llm.last_model()}}
