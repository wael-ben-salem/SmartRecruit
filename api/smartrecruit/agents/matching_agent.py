"""Matching Agent: for each requirement, retrieve evidence from the CV and decide met / partial / missing.

Tools: the CV retriever (Qdrant, filtered on run_id + candidate_id), the synonym table
to widen queries. The score itself is computed in code (scoring.py), not by the LLM.
"""
import json

from .. import config, llm, prompts, skills, vectorstore
from . import cv_agent


def build_query(req: dict) -> str:
    """Requirement text + canonical skill names + known aliases, so 'k8s' finds 'Kubernetes'."""
    terms = [req.get("text", "")] + req.get("canonical_skills", [])
    syn = skills._synonyms()
    for canonical in req.get("canonical_skills", []):
        terms += [alias for alias, c in syn.items() if c == canonical][:3]
    return " ; ".join(dict.fromkeys(t for t in terms if t))


def retrieve(run_id: str, candidate_id: str, job: dict) -> dict[str, list[dict]]:
    evidence = {}
    for req in job["requirements"]:
        hits = vectorstore.search_cv(run_id, candidate_id, build_query(req))
        evidence[req["id"]] = [{"page": h.get("page"), "section": h.get("section"),
                                "score": h.get("score"), "text": h["text"]} for h in hits]
    return evidence


def run(run_id: str, candidate_id: str, profile: dict, job: dict, feedback: str = "") -> dict:
    evidence = retrieve(run_id, candidate_id, job)
    requirements = [{k: r.get(k) for k in ("id", "text", "type", "category", "canonical_skills", "min_years")}
                    for r in job["requirements"]]
    system, user = prompts.load("matching_agent")
    out = llm.chat_json(system, prompts.render(
        user,
        requirements=json.dumps(requirements, ensure_ascii=False),
        profile=cv_agent.short(profile),
        evidence=json.dumps(evidence, ensure_ascii=False),
        feedback=feedback or "None (first pass).",
    ))
    # Make sure every requirement has exactly one assessment, even if the model skipped one
    by_id = {a.get("requirement_id"): a for a in out.get("assessments", [])}
    out["assessments"] = [by_id.get(r["id"], {"requirement_id": r["id"], "status": "missing",
                                               "reasoning": "Not assessed by the model.", "evidence": []})
                          for r in job["requirements"]]
    out["candidate_id"] = candidate_id
    out["retrieved"] = evidence
    out["_meta"] = {"agent": "matching_agent", "prompt_version": config.PROMPT_VERSIONS["matching_agent"],
                    "model": llm.last_model(), "top_k": config.TOP_K, "chunking": config.CHUNK_STRATEGY,
                    "with_feedback": bool(feedback)}
    return out
