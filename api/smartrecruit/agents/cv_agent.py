"""CV Agent: one anonymized CV -> structured profile with a quote for every skill.

Tools: the multimodal PDF reader (upstream), the skill normalizer (synonyms + ESCO RAG).
"""
import json

from .. import config, llm, prompts, skills


def run(candidate_id: str, cv_text: str) -> dict:
    system, user = prompts.load("cv_agent")
    profile = llm.chat_json(system, prompts.render(user, cv_text=cv_text))
    profile["candidate_id"] = candidate_id

    # Tool: map every skill to a canonical label so "JS" and "JavaScript" match later
    names = [s.get("name", "") for s in profile.get("skills", []) if s.get("name")]
    normalized = skills.normalize_many(names)
    for s in profile.get("skills", []):
        n = normalized.get(s.get("name", ""), {})
        s["canonical"] = n.get("canonical", s.get("name"))
        s["normalized_by"] = n.get("source")
        s["esco_uri"] = n.get("esco_uri")

    profile["_meta"] = {"agent": "cv_agent", "prompt_version": config.PROMPT_VERSIONS["cv_agent"], "model": llm.last_model()}
    return profile


def short(profile: dict) -> str:
    """Compact text view of a profile, passed to the Matching agent."""
    keep = {k: profile.get(k) for k in ("headline", "total_experience_years", "skills", "experience",
                                         "education", "languages", "certifications")}
    return json.dumps(keep, ensure_ascii=False)
