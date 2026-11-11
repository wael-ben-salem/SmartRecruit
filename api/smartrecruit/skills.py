"""Skill normalization tool, shared by the CV and Job agents.

1. exact match in a small synonym table (abbreviations such as "JS", "k8s")
2. otherwise nearest ESCO skill in Qdrant, kept only above a similarity threshold
"""
import json
from functools import lru_cache

from . import config, vectorstore

ESCO_THRESHOLD = 0.75


@lru_cache
def _synonyms() -> dict[str, str]:
    path = config.DATA_DIR / "skills_synonyms.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {alias.lower(): canonical for canonical, aliases in raw.items() for alias in aliases + [canonical]}


def normalize(skill: str) -> dict:
    key = skill.strip().lower()
    if key in _synonyms():
        return {"input": skill, "canonical": _synonyms()[key], "source": "synonyms", "esco_uri": None}
    try:
        hits = vectorstore.search(vectorstore.SKILL_COLLECTION, skill, top_k=1)
    except Exception:
        hits = []  # ESCO not loaded or embeddings down: keep the raw label
    if hits and hits[0]["score"] >= ESCO_THRESHOLD:
        return {"input": skill, "canonical": hits[0]["label"], "source": "esco",
                "esco_uri": hits[0].get("uri"), "score": hits[0]["score"]}
    return {"input": skill, "canonical": skill.strip(), "source": "raw", "esco_uri": None}


def normalize_many(skills: list[str]) -> dict[str, dict]:
    return {s: normalize(s) for s in dict.fromkeys(skills)}
