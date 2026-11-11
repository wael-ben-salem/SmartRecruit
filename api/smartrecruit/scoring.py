"""Deterministic, explainable score: a weighted average over requirements.

status value : met = 1, partial = 0.5, missing / unverified = 0
weight       : must-have = 2, nice-to-have = 1 (set by job_agent.WEIGHTS)

"missing" means NOT EVIDENCED IN THIS CV: the CV does not show it. It does not mean the candidate
lacks the skill; it is a question for the interview. The score therefore measures how well the CV
documents the requirements, never the candidate's worth, and it never rejects anyone.
"""
STATUS_VALUE = {"met": 1.0, "partial": 0.5, "missing": 0.0, "unverified": 0.0}
STATUS_LABEL = {"met": "Met", "partial": "Partial", "missing": "Not evidenced in this CV", "unverified": "Unverified claim"}
MIN_PAGE_CHARS = 100


def reading_quality(read: dict | None) -> dict:
    """Flags a CV whose text may be incomplete, so that 'not evidenced' can be read with caution."""
    if not read:
        return {"status": "unknown", "reasons": []}
    reasons = []
    pages = read.get("pages", [])
    for i, p in enumerate(pages):
        chars = len("".join(p.get("text", "").split()))
        last = i == len(pages) - 1
        # a short LAST page is normal (end of a list); an empty page, or a short page in the middle, is not
        if chars < 20 or (chars < MIN_PAGE_CHARS and not last):
            reasons.append(f"page {p['page']} is almost empty ({chars} characters): missing or unreadable page")
        elif p.get("method") == "vision":
            reasons.append(f"page {p['page']} was a scan or a multi-column layout, read by the vision model: check quotes against the original")
    blocking = any("almost empty" in r for r in reasons)
    return {"status": "check" if blocking else ("ok" if not reasons else "info"), "reasons": reasons}


def score(match: dict, job: dict, read: dict | None = None) -> dict:
    reqs = {r["id"]: r for r in job["requirements"]}
    total = gained = 0.0
    must_total = must_met = 0
    for a in match["assessments"]:
        r = reqs[a["requirement_id"]]
        value = STATUS_VALUE.get(a["status"], 0.0)
        total += r["weight"]
        gained += r["weight"] * value
        if r["type"] == "must":
            must_total += 1
            must_met += a["status"] == "met"
    quality = reading_quality(read)
    return {
        "score": round(100 * gained / total, 1) if total else 0.0,
        "must_have_met": f"{must_met}/{must_total}",
        "must_have_not_evidenced": [a["requirement_id"] for a in match["assessments"]
                                    if reqs[a["requirement_id"]]["type"] == "must" and a["status"] in ("missing", "unverified")],
        "unverified_claims": sum(a["status"] == "unverified" for a in match["assessments"]),
        "reading_quality": quality,
    }
