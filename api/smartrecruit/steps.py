"""One function per pipeline step. Each loads its inputs from the run store, saves its
output, logs it, and returns it. n8n calls them over HTTP (main.py); pipeline.py chains
them in Python for tests and the CLI.
"""
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from . import anonymizer, config, pdf_reader, report, store, vectorstore
from .agents import audit_agent, cv_agent, job_agent, matching_agent


def new_run(job_file: str, cv_files: list[str]) -> dict:
    """Copy the input files into data/uploads/<run_id>/ and register the run."""
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    folder = config.UPLOAD_DIR / run_id
    folder.mkdir(parents=True, exist_ok=True)
    job_dst = folder / ("job" + Path(job_file).suffix.lower())
    shutil.copy(job_file, job_dst)
    cvs = []
    for i, f in enumerate(cv_files, start=1):
        cid = f"candidate_{chr(64 + i)}" if i <= 26 else f"candidate_{i}"  # candidate_A, candidate_B...
        dst = folder / f"{cid}{Path(f).suffix.lower()}"
        shutil.copy(f, dst)
        # the original file name often contains the person's name: kept only in the run file, never sent to an LLM
        cvs.append({"candidate_id": cid, "path": str(dst), "original_name": Path(f).name})
    meta = {"run_id": run_id, "job_file": str(job_dst), "cv_files": cvs}
    store.save(run_id, "run", meta)
    store.log(run_id, "new_run", cvs=len(cvs))
    return meta


def _path_of(run_id: str, doc_id: str) -> str:
    meta = store.load(run_id, "run")
    if doc_id == "job":
        return meta["job_file"]
    return next(c["path"] for c in meta["cv_files"] if c["candidate_id"] == doc_id)


def read(run_id: str, doc_id: str) -> dict:
    out = pdf_reader.read_any(_path_of(run_id, doc_id))
    store.save(run_id, f"{doc_id}_read", out)
    store.log(run_id, "read", doc=doc_id, methods=[p["method"] for p in out["pages"]])
    return {"run_id": run_id, "doc_id": doc_id, **out}


def anonymize(run_id: str, candidate_id: str) -> dict:
    text = store.load(run_id, f"{candidate_id}_read")["full_text"]
    out = anonymizer.anonymize(text, candidate_id)
    store.save(run_id, f"{candidate_id}_anon", out)
    store.log(run_id, "anonymize", candidate=candidate_id, removed=out["removed"])
    return {"run_id": run_id, "candidate_id": candidate_id, **out}


def cv(run_id: str, candidate_id: str) -> dict:
    profile = cv_agent.run(candidate_id, store.load(run_id, f"{candidate_id}_anon")["text"])
    store.save(run_id, f"{candidate_id}_profile", profile)
    store.log(run_id, "cv_agent", candidate=candidate_id, skills=len(profile.get("skills", [])))
    return {"run_id": run_id, "candidate_id": candidate_id, "profile": profile}


def index(run_id: str, candidate_id: str) -> dict:
    n = vectorstore.index_cv(run_id, candidate_id, store.load(run_id, f"{candidate_id}_anon")["text"])
    store.log(run_id, "index", candidate=candidate_id, chunks=n, strategy=config.CHUNK_STRATEGY)
    return {"run_id": run_id, "candidate_id": candidate_id, "chunks_indexed": n}


def job(run_id: str) -> dict:
    text = store.load(run_id, "job_read")["full_text"]
    text = re.sub(r"\[page \d+\]\n", "", text)
    out = job_agent.run(text)
    store.save(run_id, "job", out)
    store.log(run_id, "job_agent", requirements=len(out.get("requirements", [])))
    return {"run_id": run_id, "job": out}


def match(run_id: str, candidate_id: str) -> dict:
    out = matching_agent.run(run_id, candidate_id, store.load(run_id, f"{candidate_id}_profile"), store.load(run_id, "job"))
    store.save(run_id, f"{candidate_id}_match", out)
    store.log(run_id, "matching_agent", candidate=candidate_id,
              statuses=[a["status"] for a in out["assessments"]])
    return {"run_id": run_id, "candidate_id": candidate_id, "match": out}


def audit(run_id: str, candidate_id: str, allow_retry: bool = True) -> dict:
    out = audit_agent.run(run_id, candidate_id,
                          match=store.load(run_id, f"{candidate_id}_match"),
                          job=store.load(run_id, "job"),
                          profile=store.load(run_id, f"{candidate_id}_profile"),
                          cv_text=store.load(run_id, f"{candidate_id}_anon")["text"],
                          allow_retry=allow_retry)
    store.save(run_id, f"{candidate_id}_audit", out)
    store.log(run_id, "audit_agent", candidate=candidate_id, retried=out["retried"],
              issues_first_round=len(out["rounds"][0]["issues"]), issues_left=out["remaining_issues"])
    return {"run_id": run_id, "candidate_id": candidate_id, **out}


def build_report(run_id: str) -> dict:
    out = report.build(run_id)
    store.log(run_id, "report", ranking=out["ranking"])
    return out
