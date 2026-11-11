"""Central configuration, read from environment variables (see .env.example)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


# LLM: any OpenAI-compatible endpoint (Gemini, OpenAI, Groq, Ollama...)
LLM_BASE_URL = _env("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
LLM_API_KEY = _env("LLM_API_KEY", "")
LLM_MODEL = _env("LLM_MODEL", "gemini-3.5-flash")
VISION_MODEL = _env("VISION_MODEL", LLM_MODEL)
# used in order when a model's daily quota is exhausted (free tiers: about 20 requests / day / model)
LLM_FALLBACK_MODELS = [m.strip() for m in _env("LLM_FALLBACK_MODELS", "gemini-3.5-flash-lite").split(",") if m.strip()]
LLM_TEMPERATURE = float(_env("LLM_TEMPERATURE", "0"))

# Embeddings: Ollama (local) by default
EMBED_PROVIDER = _env("EMBED_PROVIDER", "ollama")  # ollama | openai
EMBED_MODEL = _env("EMBED_MODEL", "bge-m3")
OLLAMA_URL = _env("OLLAMA_URL", "http://localhost:11434")

# Vector store: Qdrant server URL, or ":memory:" for tests / evaluation
QDRANT_URL = _env("QDRANT_URL", "http://localhost:6333")

# RAG settings
CHUNK_STRATEGY = _env("CHUNK_STRATEGY", "section")  # section | recursive
TOP_K = int(_env("TOP_K", "5"))

# Multimodal router: below this many characters per page, the page goes to the vision model
MIN_CHARS_PER_PAGE = int(_env("MIN_CHARS_PER_PAGE", "200"))

# Prompt versions used at run time (the library keeps every version)
PROMPT_VERSIONS = {
    "cv_agent": _env("PROMPT_CV_AGENT", "v2"),
    "job_agent": _env("PROMPT_JOB_AGENT", "v3"),
    "matching_agent": _env("PROMPT_MATCHING_AGENT", "v2"),
    "audit_agent": _env("PROMPT_AUDIT_AGENT", "v3"),
    "vision_reader": _env("PROMPT_VISION_READER", "v1"),
}

# Data retention: runs (CVs, texts, outputs, vectors) are deleted after this many days; 0 = keep
RETENTION_DAYS = int(_env("RETENTION_DAYS", "30"))

PROMPTS_DIR = Path(_env("PROMPTS_DIR", str(ROOT / "prompts")))
DATA_DIR = Path(_env("DATA_DIR", str(ROOT / "data")))
UPLOAD_DIR = DATA_DIR / "uploads"
RUNS_DIR = DATA_DIR / "runs"
