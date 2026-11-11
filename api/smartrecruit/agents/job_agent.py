"""Job Analysis Agent: job offer text -> atomic, weighted requirements.

Tools: the skill normalizer (synonyms + ESCO RAG). Weights are set in code, not by the
LLM, so they stay visible and adjustable: must-have = 2, nice-to-have = 1.
"""
from .. import config, llm, prompts, skills

WEIGHTS = {"must": 2, "nice": 1}


def run(job_text: str) -> dict:
    system, user = prompts.load("job_agent")
    job = llm.chat_json(system, prompts.render(user, job_text=job_text))

    reqs = job.get("requirements", [])
    all_skills = [s for r in reqs for s in r.get("skills", [])]
    normalized = skills.normalize_many(all_skills)
    for i, r in enumerate(reqs, start=1):
        r["id"] = f"R{i}"
        r["type"] = "must" if r.get("type") == "must" else "nice"
        r["weight"] = WEIGHTS[r["type"]]
        r["canonical_skills"] = [normalized[s]["canonical"] for s in r.get("skills", []) if s in normalized]

    job["_meta"] = {"agent": "job_agent", "prompt_version": config.PROMPT_VERSIONS["job_agent"], "model": llm.last_model()}
    return job
