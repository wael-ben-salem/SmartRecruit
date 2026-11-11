"""HTTP API called by the n8n workflow, plus the recruiter upload page.

    uvicorn smartrecruit.main:app --port 8000
"""
import os
from contextlib import asynccontextmanager
import tempfile
from pathlib import Path

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config, pipeline, steps, store
from .dashboard_api import router as dashboard_router

@asynccontextmanager
async def lifespan(_app):
    store.purge_older_than(config.RETENTION_DAYS)  # data retention, applied at every start
    yield


app = FastAPI(title="SmartRecruit API", lifespan=lifespan)
app.include_router(dashboard_router)
# the Vite dev server (npm run dev) runs on another port
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
DASHBOARD_DIST = Path(os.getenv("DASHBOARD_DIST", str(config.ROOT / "dashboard" / "dist")))
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/smartrecruit")


class Doc(BaseModel):
    run_id: str
    doc_id: str


class Cand(BaseModel):
    run_id: str
    candidate_id: str


class Run(BaseModel):
    run_id: str


class AuditReq(Cand):
    allow_retry: bool = True


def _guard(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/health")
def health():
    return {"ok": True, "model": config.LLM_MODEL, "embeddings": config.EMBED_MODEL, "chunking": config.CHUNK_STRATEGY}


# ---- pipeline steps (one n8n node each) ----
@app.post("/read")
def read(req: Doc):
    return _guard(steps.read, req.run_id, req.doc_id)


@app.post("/anonymize")
def anonymize(req: Cand):
    return _guard(steps.anonymize, req.run_id, req.candidate_id)


@app.post("/agents/cv")
def cv(req: Cand):
    return _guard(steps.cv, req.run_id, req.candidate_id)


@app.post("/index")
def index(req: Cand):
    return _guard(steps.index, req.run_id, req.candidate_id)


@app.post("/agents/job")
def job(req: Run):
    return _guard(steps.job, req.run_id)


@app.post("/agents/match")
def match(req: Cand):
    return _guard(steps.match, req.run_id, req.candidate_id)


@app.post("/agents/audit")
def audit(req: AuditReq):
    return _guard(steps.audit, req.run_id, req.candidate_id, req.allow_retry)


@app.post("/report")
def report(req: Run):
    out = _guard(steps.build_report, req.run_id)
    return {k: v for k, v in out.items() if k != "html"} | {"report_url": f"/runs/{req.run_id}/report"}


@app.get("/runs/{run_id}/report", response_class=HTMLResponse)
def show_report(run_id: str):
    path = config.RUNS_DIR / run_id / "report.html"
    if not store._SAFE.match(run_id) or not path.exists():
        raise HTTPException(404, "No report for this run yet")
    return path.read_text(encoding="utf-8")


# ---- entry points ----
async def _save_uploads(job_offer: UploadFile, cvs: list[UploadFile]) -> tuple[str, list[str], str]:
    tmp = tempfile.mkdtemp(prefix="smartrecruit-")
    paths = []
    for f in [job_offer, *cvs]:
        name = Path(f.filename or "file").name
        if Path(name).suffix.lower() not in (".pdf", ".txt"):
            raise HTTPException(400, f"{name}: only .pdf and .txt files are accepted")
        p = Path(tmp) / f"{len(paths)}_{name}"
        p.write_bytes(await f.read())
        paths.append(str(p))
    return paths[0], paths[1:], tmp


@app.post("/start")
async def start(job_offer: UploadFile = File(...), cvs: list[UploadFile] = File(...)):
    """Upload page -> register the run -> trigger the n8n workflow -> return the report link."""
    job_path, cv_paths, _ = await _save_uploads(job_offer, cvs)
    meta = steps.new_run(job_path, cv_paths)
    payload = {"run_id": meta["run_id"], "candidates": [c["candidate_id"] for c in meta["cv_files"]]}
    async with httpx.AsyncClient(timeout=900) as client:
        r = await client.post(N8N_WEBHOOK_URL, json=payload)
    if r.status_code >= 400:
        raise HTTPException(502, f"n8n workflow failed ({r.status_code}): {r.text[:500]}")
    return {"run_id": meta["run_id"], "report_url": f"/runs/{meta['run_id']}/report", "n8n": r.json()}


@app.post("/pipeline/run")
async def run_direct(job_offer: UploadFile = File(...), cvs: list[UploadFile] = File(...)):
    """Same pipeline without n8n (debugging only)."""
    job_path, cv_paths, _ = await _save_uploads(job_offer, cvs)
    out = pipeline.run(job_path, cv_paths)
    return {k: v for k, v in out.items() if k != "html"} | {"report_url": f"/runs/{out['run_id']}/report"}


@app.get("/simple", response_class=HTMLResponse)
def simple_page():
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


# React dashboard (built with `npm run build` in dashboard/); the simple page stays as a fallback
if (DASHBOARD_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=DASHBOARD_DIST, html=True), name="dashboard")
else:
    @app.get("/", response_class=HTMLResponse)
    def home():
        return simple_page()
