# SmartRecruit · Technical report (draft, 8 pages max)

> Draft written from the implementation. Replace every `[…]` with the team's measured results before submission.
> Sections follow the five graded points.

## 0. Use case (½ page)

Recruiters compare dozens of CVs with one offer. Keyword filters miss synonyms ("k8s" vs Kubernetes), designed CVs
(columns, scans) lose their text, and LLM summaries sound sure of themselves without citing proof. SmartRecruit takes one offer and N CVs
and returns, for every requirement and every candidate, a status (met / partial / missing) **with a quote and page
number from the CV**, checked by an Audit agent. It never rejects anyone: the score only orders the list, and the
recruiter decides (recruitment is a high-risk use case under the EU AI Act).

## 1. Automation platform (½ page)

n8n (self-hosted, Docker) orchestrates the run: webhook trigger → two parallel branches (job offer; one item per CV)
→ merge → Matching → Audit → report → HTTP response. Each agent is one n8n node calling the SmartRecruit API, so an
execution shows every agent's input and output. Error handling: retries on every agent node (2 tries, 5–10 s apart),
rate-limit backoff in the LLM client, JSON re-ask when the model returns invalid JSON, and a fallback assessment
("missing, not assessed") if the model skips a requirement. All outputs are saved in `data/runs/<run_id>/` with an
audit log.

Why the agents run as an API called by n8n rather than as n8n AI-Agent nodes: the quote check, the chunking, the
scoring and the PDF router are deterministic code that we unit-test (`api/tests`); n8n stays responsible for the
flow, parallelism and retries.

## 2. Prompt engineering (1½ pages) — 20 %

See PROMPT_LIBRARY.md. Summarize here: one table of the five prompts (role, technique), then one before/after per
key prompt with the numbers from `eval/prompt_runs/summary.md`:

| Prompt | Check | v1 | v2 |
|---|---|---|---|
| cv_agent | skills without a verbatim quote | […] | […] |
| cv_agent | skills not present in the CV | […] | […] |
| job_agent | discriminatory criterion kept ("aged 25 to 30") | […] | […] |
| job_agent | compound requirements | […] | […] |
| matching_agent | claims rejected by the audit in round 1 | […] | […] |

Discuss one failure that v2 did **not** fix (credit is given for reporting what did not work).

## 3. RAG (2 pages) — 25 %

**Corpus.** Two collections, two jobs.
- *CV evidence store* (`cv_chunks`): the uploaded CVs, chunked at run time, filtered by `run_id` + `candidate_id`.
  Used by the Matching agent (evidence) and indirectly by the Audit agent. Tuning and test material: 3 fictional CVs
  with different layouts + ground truth (`data/samples`); optional larger corpus: HF `opensporks/resumes` (2,484 CVs).
- *Skills KB* (`esco_skills`): ESCO taxonomy (digital skills collection, […] skills; or full set ≈13.9k), one point
  per skill (label + alternative labels + description). Used by the CV and Job agents to normalize skill names, plus a
  hand-made synonym table for abbreviations.

**Chunking.** A: by CV section (headings EN/FR detected, max 300 tokens, 30 overlap, heading repeated on each piece).
B: recursive fixed size (500 / 50, and 100 / 20 as a variant). ESCO: one chunk per skill (a skill is already the unit).

**Embeddings and store.** bge-m3 (multilingual, 1024 dimensions, local via Ollama), Qdrant with payload indexes.

**Retrieval setup.** Query = requirement text + canonical skill names + known aliases; top-k = […]; filter on the
candidate; no reranker (not needed at this size: […]).

**Evaluation** (full tables and comments: `eval/RETRIEVAL_EVAL.md`). Main set: 10 real IT CVs (Kaggle), 67 queries =
the requirements of a real LinkedIn offer, silver labels (keyword patterns). With bge-m3:

| Chunking | R@1 | R@3 | R@5 | MRR | tokens top-3 |
|---|---|---|---|---|---|
| A · section | 0.642 | 0.881 | 0.955 | 0.765 | 529 |
| B · fixed 500/50 | 0.612 | 0.881 | 0.985 | 0.745 | 922 |
| B' · fixed 100/20 | 0.597 | 0.731 | 0.836 | 0.683 | 250 |

- A has the best rank-1 recall and MRR and sends 43 % fewer tokens than B at the same recall@3.
- On the short synthetic CVs B makes one chunk per CV, so every metric is 1.0: the trap that made us build the real set.
- TF-IDF is close or better (A: R@3 0.910): partly a bias of keyword labels, partly real (exact terms like "CompTIA A+").
  Next step: hybrid retrieval.
- Decision: top-k 3 → 5 (R@5 0.955 for A).

## 4. Multi-agent architecture (2 pages) — 25 %

| Agent | Job | Tools | Output |
|---|---|---|---|
| CV Agent | anonymized CV → profile | vision reader (upstream), skill normalizer (synonyms + ESCO RAG) | JSON profile, quote + page per skill |
| Job Analysis Agent | offer → atomic requirements | skill normalizer | requirements with type, category; weights set in code |
| Matching Agent | requirement × CV → status | CV retriever (Qdrant), alias expansion | statuses, short reasoning, quotes |
| Audit Agent | verify every claim | quote check in code, LLM verifier, can call the Matching agent once | verified / overstated / unsupported, final statuses |

Information flow: typed JSON, saved per step, passed by id through n8n. Architecture: sequential chain with parallel
workers (per CV) and one verifier loop.

Rejected alternatives:
- *One LLM call* with the offer and all CVs: long context, no intermediate checks, invented evidence cannot be caught.
- *LLM router / supervisor* deciding which agent to call: the path changes between runs, more calls, harder to audit
  for a high-risk system; our steps are always the same, so routing adds cost without benefit.
- *Hierarchical teams*: no sub-tasks large enough to need managers.

Measured on the first real run (`20261028-160545-a88e88`, real offer, 3 real CVs): the Audit agent found no issue on the
two text CVs; on the scanned CV it rejected 2 claims in round 1, the Matching agent re-assessed them, and 1 claim was
still lowered ("overstated") in round 2. Final scores: 73.1, 34.6, 30.8 (IT specialist, sports coach, IT director).

## 5. Multimodality (1 page) — 15 %

Router per page (`pdf_reader.route_page`): < 200 characters → scan; a vertical gutter with text lines on both sides →
multi-column. Those pages are rendered to PNG (150 dpi) and transcribed by the vision model (`vision_reader` prompt);
other pages use the text layer (free, exact). On the samples: CV A → text (2 pages), CV B (sidebar) → vision,
CV C (scan) → vision. Without vision, CV C would be empty and CV B's sidebar skills would be mixed with experience lines.
On real data: all 120 Kaggle IT CVs are routed to the text path (after fixing a router bug that sent short last pages
to vision), and a real CV turned into a scanned copy is routed to vision; its transcription is 99.4 % identical to the
original text layer (character-level similarity). Privacy trade-off: page images reach the provider before
anonymization (see limits).

## 6. Responsible AI and limits (½ page)

Anonymization before the agents (names, contacts, birth date, nationality…), discriminatory criteria removed from the
offer and shown, no automatic decision, weights visible, audit trail per run. Limits: heuristic name detection, vision
path before anonymization, small synthetic test set, cost per run […] calls.
