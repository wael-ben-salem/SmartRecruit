"""Endpoints used by the React dashboard: start a run in the background (job link, text or
file + CVs), follow its progress, read structured results.
"""
import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from . import config, jobfetch, pipeline, scoring, steps, store

router = APIRouter(prefix="/api")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/smartrecruit")
_tasks: set[asyncio.Task] = set()  # keep references so background runs are not garbage-collected


def _status(run_id: str, **fields):
    current = store.load(run_id, "status") if store.exists(run_id, "status") else {}
    store.save(run_id, "status", current | fields)


async def _execute(run_id: str, mode: str):
    try:
        if mode == "n8n":
            meta = store.load(run_id, "run")
            async with httpx.AsyncClient(timeout=3600) as client:
                r = await client.post(N8N_WEBHOOK_URL, json={"run_id": run_id, "candidates": [c["candidate_id"] for c in meta["cv_files"]]})
            if r.status_code >= 400 or not store.exists(run_id, "ranking"):
                raise RuntimeError(f"n8n workflow failed ({r.status_code}): {r.text[:300] or 'see the execution in n8n'}")
        else:
            await asyncio.to_thread(pipeline.run_existing, run_id)
        _status(run_id, status="done", finished=_now())
    except Exception as e:  # shown in the dashboard
        _status(run_id, status="error", error=str(e)[:800], finished=_now())
        store.log(run_id, "error", message=str(e)[:800])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@router.post("/runs")
async def create_run(cvs: list[UploadFile] = File(...), job_url: str = Form(""), job_text: str = Form(""),
                     job_file: UploadFile | None = File(None), mode: str = Form("n8n")):
    tmp = Path(tempfile.mkdtemp(prefix="smartrecruit-"))
    job_meta = {}
    if job_file is not None and job_file.filename:
        job_path = tmp / ("job" + Path(job_file.filename).suffix.lower())
        job_path.write_bytes(await job_file.read())
        job_meta = {"source": "file", "name": job_file.filename}
    else:
        if job_url.strip():
            try:
                fetched = await asyncio.to_thread(jobfetch.fetch_job, job_url.strip())
            except Exception as e:
                raise HTTPException(400, f"Could not read the job link: {e}")
            job_text = (fetched["title"] + "\n\n" + fetched["text"]).strip()
            job_meta = {"source": "url", "url": fetched["url"], "extracted_with": fetched["source"]}
        else:
            job_meta = {"source": "text"}
        if len(job_text.strip()) < 100:
            raise HTTPException(400, "The job description is empty or too short: give a link, paste the text or upload a file.")
        job_path = tmp / "job.txt"
        job_path.write_text(job_text, encoding="utf-8")

    cv_paths = []
    for f in cvs:
        name = Path(f.filename or "cv.pdf").name
        if Path(name).suffix.lower() != ".pdf":
            raise HTTPException(400, f"{name}: CVs must be PDF files")
        p = tmp / name
        p.write_bytes(await f.read())
        cv_paths.append(str(p))

    meta = steps.new_run(str(job_path), cv_paths)
    run_id = meta["run_id"]
    _status(run_id, status="running", mode=mode, started=_now(), job=job_meta)
    task = asyncio.create_task(_execute(run_id, "n8n" if mode == "n8n" else "direct"))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"run_id": run_id}


@router.get("/runs")
def list_runs():
    out = []
    for d in sorted(config.RUNS_DIR.glob("*"), reverse=True)[:30]:
        if not (d / "run.json").exists():
            continue
        st = json.loads((d / "status.json").read_text(encoding="utf-8")) if (d / "status.json").exists() else {}
        job = json.loads((d / "job.json").read_text(encoding="utf-8")) if (d / "job.json").exists() else {}
        meta = json.loads((d / "run.json").read_text(encoding="utf-8"))
        out.append({"run_id": d.name, "status": st.get("status", "unknown"), "title": job.get("title"),
                    "cvs": len(meta["cv_files"]), "started": st.get("started")})
    return out


@router.get("/runs/{run_id}/status")
def run_status(run_id: str):
    try:
        meta = store.load(run_id, "run")
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Unknown run")
    st = store.load(run_id, "status") if store.exists(run_id, "status") else {"status": "unknown"}
    log_path = config.RUNS_DIR / run_id / "audit_log.jsonl"
    events = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines()] if log_path.exists() else []
    done = {(e["step"], e.get("candidate") or e.get("doc")) for e in events}
    cands = [c["candidate_id"] for c in meta["cv_files"]]
    per_cv = ["read", "anonymize", "cv_agent", "index", "matching_agent", "audit_agent"]
    total = 2 + len(cands) * len(per_cv) + 1
    finished = ("read", "job") in done
    finished += ("job_agent", None) in done
    finished += sum((s, c) in done for c in cands for s in per_cv)
    finished += ("report", None) in done
    return {**st, "run_id": run_id, "progress": round(finished / total, 2),
            "candidates": [{"candidate_id": c, "file": next(x["original_name"] for x in meta["cv_files"] if x["candidate_id"] == c),
                            "done": [s for s in per_cv if (s, c) in done]} for c in cands],
            "events": events[-12:]}


@router.delete("/runs/{run_id}")
def delete_run(run_id: str):
    if not store._SAFE.match(run_id) or not (config.RUNS_DIR / run_id).exists():
        raise HTTPException(404, "Unknown run")
    store.delete_run(run_id, "deleted by the recruiter")
    return {"deleted": run_id}


DECISIONS = {"interview", "not_retained", "undecided"}


class Decision(BaseModel):
    candidate_id: str
    decision: str
    note: str = ""


@router.post("/runs/{run_id}/decisions")
def record_decision(run_id: str, d: Decision):
    """The recruiter's decision. The system never decides: this is recorded with the evidence it was based on."""
    if d.decision not in DECISIONS:
        raise HTTPException(400, f"decision must be one of {sorted(DECISIONS)}")
    try:
        if d.candidate_id not in store.candidates(run_id):
            raise HTTPException(404, "Unknown candidate")
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Unknown run")
    decisions = store.load(run_id, "decisions") if store.exists(run_id, "decisions") else {}
    decisions[d.candidate_id] = {"decision": d.decision, "note": d.note[:1000], "at": _now()}
    store.save(run_id, "decisions", decisions)
    store.log(run_id, "recruiter_decision", candidate=d.candidate_id, decision=d.decision)
    return decisions[d.candidate_id]


@router.get("/runs/{run_id}/result")
def run_result(run_id: str):
    try:
        job = store.load(run_id, "job")
        meta = store.load(run_id, "run")
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "No result for this run yet")
    names = {c["candidate_id"]: c["original_name"] for c in meta["cv_files"]}
    candidates = []
    for cid in names:
        if not store.exists(run_id, f"{cid}_audit"):
            continue
        audit = store.load(run_id, f"{cid}_audit")
        read = store.load(run_id, f"{cid}_read")
        match = audit["match"]
        candidates.append({
            "candidate_id": cid, "file": names[cid], **scoring.score(match, job, read),
            "summary": match.get("summary", ""), "strengths": match.get("strengths", []), "gaps": match.get("gaps", []),
            "assessments": [{k: a.get(k) for k in ("requirement_id", "status", "reasoning", "evidence", "audit",
                                                     "audit_comment", "original_status")} for a in match["assessments"]],
            "pages": [{k: p[k] for k in ("page", "method", "reason")} for p in read["pages"]],
            "audit_rounds": [{"round": r["round"], "issues": len(r["issues"])} for r in audit["rounds"]],
            "anonymized": store.load(run_id, f"{cid}_anon")["removed"],
        })
    candidates.sort(key=lambda c: c["score"], reverse=True)
    # the settings actually used by this run (they can differ from today's config, e.g. a fallback model)
    audits = [store.load(run_id, f"{c['candidate_id']}_audit") for c in candidates]
    metas = [job.get("_meta", {})] + [a["match"].get("_meta", {}) for a in audits] + [a.get("_meta", {}) for a in audits]
    return {"run_id": run_id, "job": {k: job.get(k) for k in ("title", "seniority", "requirements", "conditions", "discarded")},
            "candidates": candidates, "report_url": f"/runs/{run_id}/report",
            "decisions": store.load(run_id, "decisions") if store.exists(run_id, "decisions") else {},
            "meta": {"models": sorted({m.get("model") for m in metas if m.get("model")}),
                     "chunking": next((m["chunking"] for m in metas if m.get("chunking")), config.CHUNK_STRATEGY),
                     "top_k": next((m["top_k"] for m in metas if m.get("top_k")), config.TOP_K),
                     "prompts": {m["agent"]: m["prompt_version"] for m in metas if m.get("agent")}}}
