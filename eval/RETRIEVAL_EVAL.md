# SmartRecruit · Retrieval evaluation

What is evaluated: the retrieval step of the **Matching agent**. For one requirement of the offer and one candidate, the
agent searches that candidate's CV chunks in Qdrant (filtered on the candidate) and reads the top-k. If the passage that
proves the requirement is not in the top-k, the agent cannot cite it and will answer "missing".

Reproduce: `docker compose exec api sh -c "cd /app && python scripts/eval_retrieval.py --real"` (and without `--real`
for the synthetic set). Raw results: `results_real.json`, `results_synthetic.json`.

## Test sets

| Set | CVs | Queries | Labels |
|---|---|---|---|
| **Real** (main) | 10 real IT CVs from the Kaggle Resume Dataset, read from their PDFs like in the pipeline, the 10 most similar to the offer | 67 = the 10 requirements of the real LinkedIn offer *IT Support Specialist* × the CVs that contain evidence for them | **Silver**: a chunk is relevant if it matches a keyword pattern written for the requirement (`queries_real.json`). To be checked by 2 team members. |
| Synthetic | 3 fictional CVs (one per layout) | 30 | Gold: exact evidence strings, hand-written |

Configurations: chunking **A** by CV section (max 300 tokens, 30 overlap, heading repeated on each piece),
**B** recursive fixed size 500 / 50, **B'** recursive 100 / 20; each with **bge-m3** (dense, the pipeline's retriever) and
**TF-IDF** (lexical baseline).

**Settings, stated separately.** Every configuration returns one ranked list of 5 chunks per query; all metrics are read
from that same list, so they are comparable. Each metric is paired with the k it uses:

| Metric | k | Meaning |
|---|---|---|
| R@1, R@3, R@5 | 1, 3, 5 | share of queries with at least one relevant chunk in the first k |
| MRR, nDCG@5 | 5 | rank quality of the first 5 |
| P@3 / tokens@3 | 3 | share of relevant chunks / text the Matching agent receives per requirement when top_k = 3 (setting of the first real run) |
| P@5 / tokens@5 | 5 | the same when top_k = 5 (setting since 28/10, `TOP_K=5`) |

Tokens are estimated as words × 1.3. Compare R@3 with tokens@3 and R@5 with tokens@5, never across k.

## Results on real CVs (67 queries)

Latest run (after the anonymizer fixes of 29/10, which slightly change the indexed text; the first run gave R@5 0.955 and
MRR 0.765 for A · bge-m3, all other values within ±0.01):

| Configuration | R@1 | R@3 | R@5 | MRR | nDCG@5 | P@3 | tokens@3 | P@5 | tokens@5 | chunks / CV | tokens / chunk |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **A · section · bge-m3** (pipeline) | **0.642** | 0.881 | 0.970 | **0.768** | 0.761 | 0.443 | **529** | 0.343 | 909 | 10.8 | 145 |
| A · section · TF-IDF | 0.597 | 0.910 | 0.970 | 0.746 | 0.739 | 0.458 | 625 | 0.337 | 1021 | 10.8 | 145 |
| B · recursive 500/50 · bge-m3 | 0.612 | 0.881 | 0.985 | 0.745 | 0.760 | 0.443 | 922 | 0.439 | 1377 | 4.3 | 362 |
| B · recursive 500/50 · TF-IDF | 0.672 | 0.940 | 0.985 | 0.799 | 0.814 | 0.517 | 1130 | 0.454 | 1472 | 4.3 | 362 |
| B' · recursive 100/20 · bge-m3 | 0.597 | 0.731 | 0.836 | 0.682 | 0.625 | 0.393 | 251 | 0.316 | 412 | 22.8 | 74 |
| B' · recursive 100/20 · TF-IDF | 0.627 | 0.821 | 0.896 | 0.731 | 0.691 | 0.448 | 240 | 0.340 | 412 | 22.8 | 74 |

## Results on synthetic CVs (30 queries)

| Configuration | R@1 | R@3 | R@5 | MRR | P@3 | chunks / CV | tokens top-3 |
|---|---|---|---|---|---|---|---|
| A · section · bge-m3 | 0.567 | 0.900 | 0.967 | 0.722 | 0.367 | 6.7 | 79 |
| A · section · TF-IDF | 0.633 | 0.967 | 1.000 | 0.796 | 0.389 | 6.7 | 105 |
| B · recursive 500/50 (both) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.0 | 161 |
| B' · recursive 100/20 · bge-m3 | 0.867 | 1.000 | 1.000 | 0.933 | 0.650 | 2.0 | 179 |

## Comments

1. **The synthetic set is too easy to choose a strategy.** The fictional CVs are short (~150 tokens), so B puts each CV
   in **one** chunk: every metric is 1.0 because "retrieval" returns the whole CV. This is why we built the real set; we
   keep the synthetic results to show the trap.
2. **On real CVs (median ~850 words), section chunking (A) is the best trade-off for the agent.** With bge-m3 it has the
   best rank-1 recall (0.642) and MRR (0.768) of the dense configurations, and **at k = 3** it sends 529 tokens per
   requirement against 922 for B for the same R@3 (0.881). **At k = 5**, A and B are close in recall (0.970 vs 0.985) but B
   sends 1,377 tokens against 909: with 4.3 chunks per CV, B's top-5 is almost the whole CV.
3. **Small fixed chunks (B') are clearly worse** (recall@3 0.731 with bge-m3): 100-token windows cut experience lines
   away from their context, and the evidence is split between chunks.
4. **TF-IDF is as good as, or better than, bge-m3 here.** Part of this is a bias of our labels: they are keyword patterns,
   which favour lexical matching. Part is real: requirements such as "CompTIA A+" or "Active Directory" are exact terms.
   bge-m3 still wins on rank 1 with section chunks and is needed for French CVs and paraphrases ("tier 1 support" for
   "technical support"). **Next step: hybrid retrieval** (dense + TF-IDF scores), which Qdrant supports with sparse vectors.
5. **Decision taken from these numbers: top-k raised from 3 to 5** (`TOP_K=5`). With A · bge-m3, R@k goes from 0.881
   (k = 3, 529 tokens) to 0.970 (k = 5, 909 tokens). The price: 72 % more text per requirement and lower precision
   (P@5 0.343 vs P@3 0.443), i.e. more irrelevant passages for the Matching agent to ignore. *Correction:* an earlier
   version of this page estimated ~725 tokens at k = 5 from the average chunk size; the measured value is 909, about the
   same as B at k = 3 (922). We keep k = 5 because missing evidence produces a false "not evidenced", which is worse for
   the candidate than extra context; this is a trade-off to revisit with hybrid retrieval.
6. **Failure cases.** R02 ("1 year of technical support") is the requirement most often not ranked first (7 of the 24
   rank-1 misses for A · bge-m3); a likely cause, still to check by reading the chunks, is that CVs phrase support work in
   many ways. Only 2 queries have no relevant chunk at all in the top 5 for A · bge-m3: R08 (Active Directory) on CV
   46260230 and R10 (workstation setup) on CV 38753827. Note that the eval query is the bare requirement text, while the
   pipeline also adds canonical skill names and aliases (`matching_agent.build_query`): in the real run, R08's evidence
   for 46260230 ("Active Directory knowledge") was retrieved. The per-query ranks are in `results_real.md`.

## Limits

- Silver labels written by us; two team members must check a sample (precision of the patterns) before the defence.
- 10 CVs, one offer, IT domain only; the Kaggle CVs all use the same livecareer template (single column).
- The reranker and the ESCO query expansion are not evaluated yet.
