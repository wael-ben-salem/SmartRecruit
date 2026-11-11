"""HTML report for the recruiter: comparison matrix, evidence, audit flags, run metadata."""
import html
from datetime import datetime

from . import config, scoring, store

STATUS_STYLE = {
    "met": ("Met", "#1d6b3a", "#e3f2e7"),
    "partial": ("Partial", "#8a5a00", "#fdf1d8"),
    "missing": ("Not evidenced", "#8a2b1d", "#fbe4df"),
    "unverified": ("Unverified", "#5b3a8a", "#ece4f7"),
}


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _cell(a: dict) -> str:
    label, fg, bg = STATUS_STYLE.get(a["status"], ("?", "#333", "#eee"))
    quotes = "".join(
        f'<div class="q">“{_e(e["quote"])}”<span class="pg"> p.{_e(e.get("page", "?"))}</span></div>'
        for e in a.get("evidence", []) if e.get("found"))
    audit = ""
    if a.get("audit") not in ("verified", "n/a", None):
        audit = f'<div class="flag">Audit: {_e(a["audit"])} (was {_e(a.get("original_status"))}) {_e(a.get("audit_comment", ""))}</div>'
    elif a.get("audit") == "verified":
        audit = '<div class="ok">Audit: verified</div>'
    return (f'<td><span class="badge" style="color:{fg};background:{bg}">{label}</span>'
            f'<div class="why">{_e(a.get("reasoning", ""))}</div>{quotes}{audit}</td>')


def build(run_id: str) -> dict:
    job = store.load(run_id, "job")
    cands = []
    for cid in store.candidates(run_id):
        audit = store.load(run_id, f"{cid}_audit")
        read = store.load(run_id, f"{cid}_read")
        anon = store.load(run_id, f"{cid}_anon")
        match = audit["match"]
        cands.append({"id": cid, "match": match, "audit": audit, "read": read, "anon": anon,
                      "score": scoring.score(match, job, read)})
    cands.sort(key=lambda c: c["score"]["score"], reverse=True)

    head = "".join(f'<th>{_e(c["id"])}<div class="sc">{c["score"]["score"]} / 100 · must-have {c["score"]["must_have_met"]}</div></th>' for c in cands)
    rows = []
    for r in job["requirements"]:
        cells = "".join(_cell(next(a for a in c["match"]["assessments"] if a["requirement_id"] == r["id"])) for c in cands)
        tag = "Must-have" if r["type"] == "must" else "Nice-to-have"
        rows.append(f'<tr><th class="req">{_e(r["id"])} · {_e(r["text"])}<div class="tag">{tag} · weight {r["weight"]}</div></th>{cells}</tr>')

    summaries = "".join(
        f'<div class="card"><h3>{_e(c["id"])} — {c["score"]["score"]} / 100</h3>'
        f'<p>{_e(c["match"].get("summary", ""))}</p>'
        f'<p><b>Strengths:</b> {_e("; ".join(c["match"].get("strengths", [])))}</p>'
        f'<p><b>Gaps:</b> {_e("; ".join(c["match"].get("gaps", [])))}</p>'
        f'<p class="meta">Pages read: ' + ", ".join(f'p.{p["page"]} {p["method"]} ({_e(p["reason"])})' for p in c["read"]["pages"]) +
        f'<br>Anonymized: {_e(c["anon"]["removed"]) or "nothing found"}'
        f'<br>Audit rounds: {len(c["audit"]["rounds"])} · issues left: {c["audit"]["remaining_issues"]}</p>'
        + (f'<p class="flag">Reading quality to check: {_e("; ".join(c["score"]["reading_quality"]["reasons"]))}</p>'
           if c["score"]["reading_quality"]["status"] == "check" else "")
        + '</div>'
        for c in cands)

    conditions = job.get("conditions", [])
    discarded_html = ""
    if conditions:
        discarded_html += "<p class='meta'>Working conditions (shown, not scored): " + " · ".join(_e(c) for c in conditions) + "</p>"
    discarded = job.get("discarded", [])
    if discarded:
        discarded_html += ("<p class='flag'>Requirements removed from the offer (not job-related or discriminatory): "
                           + "; ".join(_e(d) for d in discarded) + "</p>")

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SmartRecruit report · {_e(job.get("title", ""))}</title><style>
body{{font-family:Inter,Segoe UI,Arial,sans-serif;background:#f4f2ec;color:#1c2433;margin:0;padding:32px}}
h1{{font-size:28px;margin:0 0 4px}} .sub{{color:#4a5568;margin-bottom:24px}}
.note{{background:#16233a;color:#f4f2ec;padding:12px 16px;border-radius:10px;margin-bottom:24px}}
.wrap{{overflow-x:auto}} table{{border-collapse:collapse;background:#fbfbf8;min-width:900px}}
th,td{{border:1px solid #e2ded4;padding:10px;vertical-align:top;text-align:left;font-size:14px}}
thead th{{background:#16233a;color:#f4f2ec}} .sc{{font-weight:400;font-size:13px;color:#f0a04b}}
th.req{{width:260px;background:#efece4}} .tag{{font-weight:400;color:#6b7280;font-size:12px}}
.badge{{display:inline-block;font-weight:700;padding:2px 8px;border-radius:12px;font-size:13px}}
.why{{margin:6px 0;color:#4a5568}} .q{{font-style:italic;margin:4px 0;border-left:3px solid #0e5f8f;padding-left:6px}}
.pg{{font-style:normal;color:#6b7280;font-size:12px}} .flag{{color:#8a2b1d;font-size:12px;margin-top:4px}} .ok{{color:#1d6b3a;font-size:12px;margin-top:4px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;margin-top:24px}}
.card{{background:#fbfbf8;border:1px solid #e2ded4;border-radius:12px;padding:16px}} .card h3{{margin:0 0 8px}}
.meta{{color:#6b7280;font-size:12px}}</style></head><body>
<h1>{_e(job.get("title", "Job offer"))}</h1>
<div class="sub">Run {_e(run_id)} · {datetime.now():%Y-%m-%d %H:%M} · model {_e(config.LLM_MODEL)} · chunking {_e(config.CHUNK_STRATEGY)} · prompts {_e(config.PROMPT_VERSIONS)}</div>
<div class="note">The AI recommends, the recruiter decides. Every “met” or “partial” must show a quote found in the CV; claims the Audit agent could not verify are marked <b>Unverified</b> and score 0. <b>Not evidenced</b> means the CV does not show it, not that the candidate lacks it: ask in the interview. The score measures how well the CV documents the requirements (must-have × 2), never the candidate's worth.</div>
{discarded_html}
<div class="wrap"><table><thead><tr><th>Requirement</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<div class="cards">{summaries}</div></body></html>"""

    out = config.RUNS_DIR / run_id / "report.html"
    out.write_text(page, encoding="utf-8")
    ranking = [{"candidate_id": c["id"], **c["score"]} for c in cands]
    store.save(run_id, "ranking", ranking)
    return {"run_id": run_id, "report_path": str(out), "ranking": ranking, "html": page}
