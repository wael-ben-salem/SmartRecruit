"""Qdrant collections used by the agents.

cv_chunks   : chunks of the uploaded CVs, payload {run_id, candidate_id, section, page, text, strategy}
esco_skills : one point per ESCO skill, payload {label, alt_labels, uri, description}
"""
import uuid

from qdrant_client import QdrantClient, models

from . import config
from .embeddings import embed

CV_COLLECTION = "cv_chunks"
SKILL_COLLECTION = "esco_skills"

_client = None


def client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(location=":memory:") if config.QDRANT_URL == ":memory:" else QdrantClient(url=config.QDRANT_URL)
    return _client


def use_client(c: QdrantClient):
    """Swap the client (used by the evaluation script with an in-memory store)."""
    global _client
    _client = c


def ensure_collection(name: str, dim: int):
    c = client()
    if not c.collection_exists(name):
        c.create_collection(name, vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE))
        for field in ("run_id", "candidate_id", "section", "strategy"):
            if name == CV_COLLECTION:
                c.create_payload_index(name, field, models.PayloadSchemaType.KEYWORD)


def upsert(name: str, texts: list[str], payloads: list[dict]) -> int:
    if not texts:
        return 0
    vectors = embed(texts)
    ensure_collection(name, len(vectors[0]))
    points = [models.PointStruct(id=str(uuid.uuid4()), vector=v, payload=p) for v, p in zip(vectors, payloads)]
    client().upsert(name, points=points)
    return len(points)


def search(name: str, query: str, top_k: int = 5, filters: dict | None = None) -> list[dict]:
    if not client().collection_exists(name):
        return []
    flt = None
    if filters:
        flt = models.Filter(must=[models.FieldCondition(key=k, match=models.MatchValue(value=v))
                                  for k, v in filters.items()])
    res = client().query_points(name, query=embed([query])[0], query_filter=flt, limit=top_k, with_payload=True)
    return [{**p.payload, "score": round(p.score, 4)} for p in res.points]


def index_cv(run_id: str, candidate_id: str, text: str, strategy: str | None = None) -> int:
    from .chunking import chunk
    strategy = strategy or config.CHUNK_STRATEGY
    chunks = chunk(text, strategy)
    payloads = [{**c, "run_id": run_id, "candidate_id": candidate_id, "strategy": strategy} for c in chunks]
    return upsert(CV_COLLECTION, [c["text"] for c in chunks], payloads)


def delete_run(run_id: str) -> None:
    """Remove every CV chunk of a run (data deletion)."""
    if client().collection_exists(CV_COLLECTION):
        client().delete(CV_COLLECTION, points_selector=models.FilterSelector(filter=models.Filter(
            must=[models.FieldCondition(key="run_id", match=models.MatchValue(value=run_id))])))


def search_cv(run_id: str, candidate_id: str, query: str, top_k: int | None = None) -> list[dict]:
    return search(CV_COLLECTION, query, top_k or config.TOP_K, {"run_id": run_id, "candidate_id": candidate_id})
