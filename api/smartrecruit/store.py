"""Run store: every intermediate result is saved under data/runs/<run_id>/ (audit trail).

Agents pass ids through n8n and load their inputs from here, so each step can be
replayed on its own and the recruiter can see exactly what each agent produced.
"""
import json
import re
from datetime import datetime, timezone

from . import config

_SAFE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _dir(run_id: str):
    if not _SAFE.match(run_id):
        raise ValueError(f"Invalid run_id: {run_id!r}")
    d = config.RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(run_id: str, name: str, obj) -> None:
    if not _SAFE.match(name):
        raise ValueError(f"Invalid name: {name!r}")
    (_dir(run_id) / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def load(run_id: str, name: str):
    path = _dir(run_id) / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"{run_id}/{name} not found: run the previous step first")
    return json.loads(path.read_text(encoding="utf-8"))


def exists(run_id: str, name: str) -> bool:
    return (_dir(run_id) / f"{name}.json").exists()


def log(run_id: str, step: str, **details) -> None:
    """Append one line to the run's audit log."""
    entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "step": step, **details}
    with open(_dir(run_id) / "audit_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def delete_run(run_id: str, reason: str) -> None:
    """Delete everything kept for a run: files, uploads and vectors. Only the run id and the date stay in the deletion log."""
    import shutil
    from . import vectorstore
    _dir(run_id)  # validates the id
    for d in (config.RUNS_DIR / run_id, config.UPLOAD_DIR / run_id):
        shutil.rmtree(d, ignore_errors=True)
    try:
        vectorstore.delete_run(run_id)
    except Exception:
        pass  # vector store down: the purge at the next start removes nothing more, chunks expire with the volume
    entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "run_id": run_id, "reason": reason}
    with open(config.DATA_DIR / "deletions.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def purge_older_than(days: int) -> list[str]:
    """Retention: delete runs older than `days` days."""
    if days <= 0 or not config.RUNS_DIR.exists():
        return []
    limit = datetime.now(timezone.utc).timestamp() - days * 86400
    old = [d.name for d in config.RUNS_DIR.iterdir() if d.is_dir() and d.stat().st_mtime < limit]
    for run_id in old:
        delete_run(run_id, f"retention: older than {days} days")
    return old


def candidates(run_id: str) -> list[str]:
    meta = load(run_id, "run")
    return [c["candidate_id"] for c in meta["cv_files"]]
