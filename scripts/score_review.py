"""Score human annotations. Two kinds of sheets:

1. End-to-end review (from export_review.py): agreement between the system and each reviewer on the status,
   evidence correctness (share of system quotes that reviewers accept), and agreement between reviewers.
       python scripts/score_review.py eval/annotation/review_<run_id>.csv

2. Retrieval labels (from eval_retrieval.py): agreement between the two annotators (Cohen's kappa), precision of
   the silver (keyword) labels against the human consensus, and precision@k of the retriever with human labels.
       python scripts/score_review.py eval/annotation/retrieval_labels_real.csv

Rows that are not filled by both people are skipped and counted.
"""
import csv
import sys
from collections import Counter


def kappa(a: list, b: list) -> float:
    """Cohen's kappa for two annotators on the same items."""
    n = len(a)
    if not n:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0


def pct(x: float) -> str:
    return f"{100 * x:.1f} %"


def review(rows: list[dict]):
    filled = [r for r in rows if r["reviewer_1_status"].strip() and r["reviewer_2_status"].strip()]
    print(f"{len(filled)} of {len(rows)} rows reviewed by both reviewers")
    if not filled:
        return
    s = [r["system_status"].strip() for r in filled]
    r1 = [r["reviewer_1_status"].strip() for r in filled]
    r2 = [r["reviewer_2_status"].strip() for r in filled]
    print("Inter-reviewer agreement on the status: kappa", kappa(r1, r2), f"(raw {pct(sum(a == b for a, b in zip(r1, r2)) / len(r1))})")
    both = [(x, a) for x, a, b in zip(s, r1, r2) if a == b]  # items where the reviewers agree = reference
    print(f"System vs reviewers' consensus ({len(both)} items): {pct(sum(x == a for x, a in both) / len(both))} same status")
    print("Confusion (system -> consensus):", dict(Counter(f"{x}->{a}" for x, a in both if x != a)))
    # 'not evidenced' that a reviewer finds in the CV = a retrieval or extraction miss
    missed = [1 for x, a in both if x == "missing" and a in ("met", "partial")]
    print(f"'Not evidenced' that the reviewers found in the CV: {len(missed)}")
    ev = [r for r in filled if r["reviewer_1_evidence_ok"].strip() and r["reviewer_2_evidence_ok"].strip()]
    if ev:
        ok = [int(r["reviewer_1_evidence_ok"]) and int(r["reviewer_2_evidence_ok"]) for r in ev]
        print(f"Evidence correctness (quotes accepted by both reviewers): {pct(sum(ok) / len(ok))} of {len(ev)} claims with quotes")
        print("Inter-reviewer agreement on evidence: kappa",
              kappa([r["reviewer_1_evidence_ok"] for r in ev], [r["reviewer_2_evidence_ok"] for r in ev]))


def retrieval(rows: list[dict]):
    c1, c2 = "annotator_1 (1=relevant, 0=not)", "annotator_2 (1=relevant, 0=not)"
    filled = [r for r in rows if r[c1].strip() and r[c2].strip()]
    print(f"{len(filled)} of {len(rows)} chunks labelled by both annotators")
    if not filled:
        return
    a = [r[c1].strip() for r in filled]
    b = [r[c2].strip() for r in filled]
    print("Inter-annotator agreement: kappa", kappa(a, b), f"(raw {pct(sum(x == y for x, y in zip(a, b)) / len(a))})")
    agreed = [r for r, x, y in zip(filled, a, b) if x == y]
    silver_ok = sum(int(r["silver_label"]) == int(r[c1]) for r in agreed)
    print(f"Silver (keyword) label = human consensus on {pct(silver_ok / len(agreed))} of {len(agreed)} agreed chunks")
    for k in (3, 5):
        top = [r for r in agreed if int(r["rank"]) <= k]
        print(f"precision@{k} with human labels: {pct(sum(int(r[c1]) for r in top) / len(top))}" if top else "")
    queries = {}
    for r in agreed:
        queries.setdefault(r["query_id"], []).append((int(r["rank"]), int(r[c1])))
    for k in (1, 3, 5):
        hit = sum(any(rel for rank, rel in v if rank <= k) for v in queries.values())
        print(f"recall@{k} with human labels: {pct(hit / len(queries))} of {len(queries)} queries")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    (review if "system_status" in rows[0] else retrieval)(rows)


if __name__ == "__main__":
    main()
