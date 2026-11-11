"""Text embeddings: bge-m3 served by Ollama (local, FR/EN), or an OpenAI-compatible API."""
import httpx

from . import config


def embed(texts: list[str], batch: int = 8) -> list[list[float]]:
    out = []
    for i in range(0, len(texts), batch):
        out.extend(_embed_batch(texts[i:i + batch]))
    return out


def _embed_batch(texts: list[str]) -> list[list[float]]:
    if config.EMBED_PROVIDER == "ollama":
        r = httpx.post(f"{config.OLLAMA_URL}/api/embed",
                       json={"model": config.EMBED_MODEL, "input": texts}, timeout=900)
        r.raise_for_status()
        return r.json()["embeddings"]
    if config.EMBED_PROVIDER == "openai":
        from .llm import client
        resp = client().embeddings.create(model=config.EMBED_MODEL, input=texts)
        return [d.embedding for d in resp.data]
    raise ValueError(f"Unknown EMBED_PROVIDER: {config.EMBED_PROVIDER}")
