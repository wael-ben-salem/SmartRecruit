"""Retrieval evaluation: compare chunking strategies (and a lexical baseline) on eval/queries.json.

For each configuration the CVs (ground-truth text, anonymized like in the pipeline) are
chunked and indexed in an in-memory Qdrant, filtered by candidate like the Matching agent.

    python scripts/eval_retrieval.py            # needs Ollama with bge-m3 at OLLAMA_URL
    python scripts/eval_retrieval.py --tfidf    # lexical baseline only, no embeddings needed

Writes eval/results.json and eval/results.md.
"""
import csv
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

os.environ["QDRANT_URL"] = ":memory:"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from smartrecruit import anonymizer, chunking, vectorstore  # noqa: E402

CONFIGS = [
    {"name": "A · section (max 300 / overlap 30)", "strategy": "section", "kw": {"max_tokens": 300, "overlap": 30}},
    {"name": "B · recursive 500 / 50", "strategy": "recursive", "kw": {"size": 500, "overlap": 50}},
    {"name": "B' · recursive 100 / 20", "strategy": "recursive", "kw": {"size": 100, "overlap": 20}},
]
K = 5


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def relevant(chunk_text: str, q: dict) -> bool:
    """Gold strings (hand-labelled synthetic set) or a regex pattern (silver labels, real set)."""
    if "pattern" in q:
        return re.search(q["pattern"], chunk_text, re.I) is not None
    t = norm(chunk_text)
    return any(norm(g) in t for g in q["gold"])


def load_set(name: str) -> tuple[dict[str, str], list[dict]]:
    if name == "synthetic":
        data = json.loads((ROOT / "eval" / "queries.json").read_text(encoding="utf-8"))
        gt = ROOT / "data" / "samples" / "ground_truth"
        cvs = {p.stem: anonymizer.anonymize(p.read_text(encoding="utf-8"), p.stem)["text"] for p in sorted(gt.glob("*.txt"))}
        return cvs, data["queries"]
    # real: Kaggle CVs read from their PDFs exactly as the pipeline does, then anonymized
    from smartrecruit import pdf_reader
    data = json.loads((ROOT / "eval" / "queries_real.json").read_text(encoding="utf-8"))
    pdf_dir = ROOT / "data" / "resumes" / "pdf" / "INFORMATION-TECHNOLOGY"
    cvs = {i: anonymizer.anonymize(pdf_reader.read_pdf(str(pdf_dir / f"{i}.pdf"), use_vision=False)["full_text"], i)["text"]
           for i in data["cvs"]}
    # one query per (CV, requirement) pair that has evidence somewhere in the CV
    queries = [{"id": f"{r['id']}·{cv}", "cv": cv, "query": r["query"], "pattern": r["pattern"]}
               for r in data["requirements"] for cv in data["cvs"] if re.search(r["pattern"], cvs[cv], re.I)]
    return cvs, queries


def metrics(ranked_rel: list[list[bool]], n_relevant: list[int]) -> dict:
    r1 = sum(r[:1].count(True) > 0 for r in ranked_rel) / len(ranked_rel)
    r3 = sum(r[:3].count(True) > 0 for r in ranked_rel) / len(ranked_rel)
    r5 = sum(r[:5].count(True) > 0 for r in ranked_rel) / len(ranked_rel)
    mrr = sum(next((1 / (i + 1) for i, x in enumerate(r) if x), 0) for r in ranked_rel) / len(ranked_rel)
    ndcg = 0.0
    for r, n in zip(ranked_rel, n_relevant):
        dcg = sum(1 / math.log2(i + 2) for i, x in enumerate(r[:K]) if x)
        idcg = sum(1 / math.log2(i + 2) for i in range(min(n, K))) or 1
        ndcg += dcg / idcg
    return {"recall@1": round(r1, 3), "recall@3": round(r3, 3), "recall@5": round(r5, 3),
            "mrr": round(mrr, 3), "ndcg@5": round(ndcg / len(ranked_rel), 3)}


class TfIdf:
    """Small lexical baseline (the 'N1' level of the coaching project)."""

    def __init__(self, docs: list[str]):
        self.docs = [self._tok(d) for d in docs]
        df = Counter(t for d in self.docs for t in set(d))
        self.idf = {t: math.log((1 + len(docs)) / (1 + n)) + 1 for t, n in df.items()}

    @staticmethod
    def _tok(s):
        return re.findall(r"[a-z0-9+#]+", s.lower())

    def _vec(self, toks):
        c = Counter(toks)
        return {t: c[t] * self.idf.get(t, 0) for t in c}

    def rank(self, query: str, idx: list[int]) -> list[int]:
        q = self._vec(self._tok(query))
        def cos(i):
            d = self._vec(self.docs[i])
            num = sum(q[t] * d.get(t, 0) for t in q)
            den = math.sqrt(sum(v * v for v in q.values())) * math.sqrt(sum(v * v for v in d.values())) or 1
            return num / den
        return sorted(idx, key=cos, reverse=True)


def run_config(cfg: dict, cvs: dict[str, str], queries: list[dict], dense: bool) -> dict:
    chunks = {cv: chunking.chunk(text, cfg["strategy"], **cfg["kw"]) for cv, text in cvs.items()}
    if dense:
        vectorstore.use_client(None)  # fresh in-memory store per configuration
        vectorstore._client = None
        for cv, cs in chunks.items():
            vectorstore.upsert(vectorstore.CV_COLLECTION, [c["text"] for c in cs],
                               [{**c, "run_id": "eval", "candidate_id": cv} for c in cs])
    flat = [(cv, c["text"]) for cv, cs in chunks.items() for c in cs]
    tfidf = TfIdf([t for _, t in flat])

    per_query, ranked_rel, n_rel, ctx_tokens, ctx_precision, ctx_tokens5, ctx_precision5 = [], [], [], [], [], [], []
    for q in queries:
        if dense:
            hits = [h["text"] for h in vectorstore.search(vectorstore.CV_COLLECTION, q["query"], K,
                                                          {"run_id": "eval", "candidate_id": q["cv"]})]
        else:
            idx = [i for i, (cv, _) in enumerate(flat) if cv == q["cv"]]
            hits = [flat[i][1] for i in tfidf.rank(q["query"], idx)[:K]]
        rel = [relevant(h, q) for h in hits]
        ranked_rel.append(rel)
        # what the Matching agent receives with top_k = 3 (first setting) and top_k = 5 (current setting)
        ctx_tokens.append(sum(chunking.tokens(h) for h in hits[:3]))
        ctx_precision.append(sum(rel[:3]) / len(rel[:3]) if rel else 0)
        ctx_tokens5.append(sum(chunking.tokens(h) for h in hits[:5]))
        ctx_precision5.append(sum(rel[:5]) / len(rel[:5]) if rel else 0)
        n_rel.append(sum(relevant(c["text"], q) for c in chunks[q["cv"]]))
        first = next((i + 1 for i, x in enumerate(rel) if x), None)
        per_query.append({"id": q["id"], "cv": q["cv"], "query": q["query"], "rank_of_first_relevant": first,
                          "top1": hits[0][:120].replace("\n", " ") if hits else "",
                          "hits": [{"rank": i + 1, "text": h, "silver": r} for i, (h, r) in enumerate(zip(hits, rel))]})

    n_chunks = [len(cs) for cs in chunks.values()]
    sizes = [chunking.tokens(c["text"]) for cs in chunks.values() for c in cs]
    return {
        "config": cfg["name"] + (" · bge-m3" if dense else " · TF-IDF"),
        **metrics(ranked_rel, n_rel),
        "chunks_per_cv": round(sum(n_chunks) / len(n_chunks), 1),
        "avg_chunk_tokens": round(sum(sizes) / len(sizes)),
        "precision@3": round(sum(ctx_precision) / len(ctx_precision), 3),
        "tokens_top3": round(sum(ctx_tokens) / len(ctx_tokens)),
        "precision@5": round(sum(ctx_precision5) / len(ctx_precision5), 3),
        "tokens_top5": round(sum(ctx_tokens5) / len(ctx_tokens5)),
        "per_query": per_query,
    }


def main():
    only_tfidf = "--tfidf" in sys.argv
    name = "real" if "--real" in sys.argv else "synthetic"
    cvs, queries = load_set(name)
    print(f"{name} set: {len(cvs)} CVs, {len(queries)} queries")

    results = []
    for cfg in CONFIGS:
        results.append(run_config(cfg, cvs, queries, dense=False))
        if not only_tfidf:
            results.append(run_config(cfg, cvs, queries, dense=True))

    (ROOT / "eval" / f"results_{name}.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    # sheet for the two human annotators: the top-5 chunks of the configuration used in production
    used = next(r for r in results if r["config"].startswith("A ·") and r["config"].endswith("bge-m3")) if not only_tfidf else results[0]
    ann_dir = ROOT / "eval" / "annotation"
    ann_dir.mkdir(exist_ok=True)
    with open(ann_dir / f"retrieval_labels_{name}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["query_id", "cv", "requirement", "rank", "chunk_text", "silver_label", "annotator_1 (1=relevant, 0=not)", "annotator_2 (1=relevant, 0=not)"])
        for p in used["per_query"]:
            for h in p["hits"]:
                w.writerow([p["id"], p["cv"], p["query"], h["rank"], h["text"], int(h["silver"]), "", ""])

    cols = ["recall@1", "recall@3", "recall@5", "mrr", "ndcg@5", "precision@3", "tokens_top3", "precision@5", "tokens_top5", "chunks_per_cv", "avg_chunk_tokens"]
    lines = ["| Configuration | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for r in results:
        lines.append(f"| {r['config']} | " + " | ".join(str(r[c]) for c in cols) + " |")
    misses = ["", "Queries where the first relevant chunk is not ranked 1:", ""]
    for r in results:
        bad = [f"{p['id']} (rank {p['rank_of_first_relevant']})" for p in r["per_query"] if p["rank_of_first_relevant"] != 1]
        misses.append(f"- {r['config']}: " + (", ".join(bad) or "none"))
    table = "\n".join(lines + misses)
    (ROOT / "eval" / f"results_{name}.md").write_text(table + "\n", encoding="utf-8")
    print(table)


if __name__ == "__main__":
    main()
