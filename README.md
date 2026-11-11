# SmartRecruit · evidence-based CV matching

Advanced Deep Learning final project (Esprit 5DS). Upload one job offer and several CVs (PDF, any layout).
An n8n workflow runs four agents and returns a comparison where **every conclusion is backed by a quote from the CV**,
checked by an Audit agent. The AI recommends; the recruiter decides.

Guides en français : [dossier du projet](projet.md) (architecture, installation, validation et limites) et [détail des fichiers et des choix](detail.md) pour la soutenance.

```
                   ┌─────────────── n8n workflow (orchestrator) ────────────────┐
 upload page ──► webhook ─┬─► read job offer ─► Job Analysis Agent ───────────┐  │
                          │                                                    ▼  │
                          └─► per CV: read (text | vision) ─► anonymize ─► CV Agent ─► index chunks (Qdrant)
                                                                                   │  │
                                      per CV: Matching Agent (RAG) ─► Audit Agent ─┘  │
                                                    ▲                  │ (once)       │
                                                    └──── feedback ────┘              │
                                            collect ─► report (HTML) ─► response ─────┘
```

| Requirement | Where |
|---|---|
| Automation platform | [n8n/smartrecruit.json](n8n/smartrecruit.json): triggered end to end by a webhook (upload page at http://localhost:8000) |
| Prompt engineering | [PROMPT_LIBRARY.md](PROMPT_LIBRARY.md), prompts in [prompts/](prompts/) (v1, v2 per agent), [scripts/compare_prompts.py](scripts/compare_prompts.py) |
| RAG | CV evidence store + ESCO skills KB in Qdrant ([vectorstore.py](api/smartrecruit/vectorstore.py), [chunking.py](api/smartrecruit/chunking.py)); evaluation in [eval/](eval/) |
| Multi-agent | [api/smartrecruit/agents/](api/smartrecruit/agents/): CV, Job Analysis, Matching, Audit |
| Multimodality | [pdf_reader.py](api/smartrecruit/pdf_reader.py): per-page router, vision model for scans and multi-column CVs |

## Stack

| Component | Choice | Why |
|---|---|---|
| Orchestration | n8n (Docker) | Fixed, replayable path; each agent is a visible node |
| Agents and tools | Python FastAPI service (`api/`) | Testable code for parsing, chunking, quote checks and scoring |
| LLM (text + vision) | Any OpenAI-compatible API; Gemini 3.5 Flash by default | One model reads text and page images, JSON mode, low cost. A 4 GB GPU is too small for a good local vision model |
| Embeddings | bge-m3 via Ollama (local) | Multilingual FR / EN, free, CVs never leave the machine for indexing |
| Vector store | Qdrant | Payload filters (`run_id`, `candidate_id`), native n8n node available |

## Run it

Requirements: Docker Desktop, an LLM API key (for example a free Gemini key from https://aistudio.google.com/apikey).

```bash
cp .env.example .env              # then put your key in LLM_API_KEY
npm --prefix dashboard install && npm --prefix dashboard run build   # React dashboard
docker compose up -d --build
docker compose exec ollama ollama pull bge-m3
# import the workflow while n8n is stopped (n8n uses SQLite, which is locked while it runs)
docker compose stop n8n
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps n8n import:workflow --input=/workflows/smartrecruit.json
docker compose run --rm --no-deps n8n update:workflow --id=SmartRecruitMain --active=true
docker compose up -d n8n
```

(`MSYS_NO_PATHCONV=1` is only needed in Git Bash on Windows.)

1. Open **http://localhost:8000**: the SmartRecruit dashboard.
   - Job offer: paste a **link** to a public job page (read from its schema.org JobPosting data or page text), **paste the text**, or upload a file.
   - Drop one or more **CV PDFs** (any layout; scans go through the vision model).
   - Click **Analyse**: the run goes through the n8n workflow, the page shows each agent's progress, then the
     ranking, the score per candidate, every requirement with its status, the quotes from the CV and the audit result.
2. Open http://localhost:5678 to see the workflow and every execution in n8n (create the local owner account the first time).
3. A ready-made real demo set is in [data/demo/](data/demo/): a real LinkedIn offer and 3 real CVs, one of them as a scanned copy.

Dashboard development: `npm --prefix dashboard run dev` (http://localhost:5173, calls the API on :8000).

Every intermediate output is saved in `data/runs/<run_id>/` (read pages, anonymized text, profiles, job, matches,
audit rounds, `audit_log.jsonl`, `report.html`).

### Optional: ESCO skills knowledge base

Download the ESCO CSV files (https://esco.ec.europa.eu/en/use-esco/download, English) into `data/esco/`, then:

```bash
docker compose exec api python /app/scripts/ingest_esco.py /app/data/esco/digitalSkillsCollection_en.csv
```

Without ESCO, skills are normalized with the synonym table [data/skills_synonyms.json](data/skills_synonyms.json) only.

### Without Docker (development)

```bash
python -m venv .venv && .venv/Scripts/pip install -r api/requirements.txt pytest
cd api && ../.venv/Scripts/python -m pytest tests -q        # offline tests, no key needed
../.venv/Scripts/python -m smartrecruit.pipeline ../data/samples/job_offer_data_engineer.txt ../data/samples/cv_*.pdf
```

## Evaluation

Run the scripts that need the models inside the API container (`docker compose exec api sh -c "cd /app && python scripts/<script>"`).

| What | Script | Needs | Results |
|---|---|---|---|
| Retrieval: chunking A / B / B', bge-m3 vs TF-IDF, real and synthetic CVs | `eval_retrieval.py [--real]` | Ollama | [eval/RETRIEVAL_EVAL.md](eval/RETRIEVAL_EVAL.md) |
| Audit: does it catch misleading matches? (v2 vs v3, `--repeats N`) | `eval_audit.py` | LLM (1 call / version / repeat) | `eval/audit_results.md`, [PROMPT_LIBRARY.md](PROMPT_LIBRARY.md) §4 |
| Anonymization across layouts (leaks and false removals) | `eval_anonymization.py` | nothing | `eval/anonymization_results.md` |
| Consistency: same CV as text vs scan, synonyms, missing page | `eval_consistency.py --model …` | LLM (~15-20 calls) | `eval/consistency_results.md` |
| Prompt versions v1 vs v2 (CV and Job agents) | `compare_prompts.py` | LLM (~9 calls) | `eval/prompt_runs/summary.md` |
| Score behaviour scenarios | `cd api && python -m pytest tests` | nothing | 12 tests |

**Human checks (two team members, independently):**

1. Retrieval labels: fill the two annotator columns of `eval/annotation/retrieval_labels_real.csv`, then
   `python scripts/score_review.py eval/annotation/retrieval_labels_real.csv` (Cohen's kappa, silver-label precision, recall with human labels).
2. End-to-end conclusions: `python scripts/export_review.py <run_id>`, fill the reviewer columns of
   `eval/annotation/review_<run_id>.csv` (read the CV, give the status it really supports and whether the system's quotes support its
   status), then `python scripts/score_review.py eval/annotation/review_<run_id>.csv` (status agreement, evidence correctness).
3. Audit labels: fill `reviewed_by` in `eval/audit_cases.json`.

Privacy, retention, fairness and their limits: [docs/PRIVACY_AND_FAIRNESS.md](docs/PRIVACY_AND_FAIRNESS.md).

## Layout

```
api/smartrecruit/      agents/ (4 agents), pdf_reader, anonymizer, chunking, vectorstore, skills, scoring, report, main (API)
prompts/<agent>/vN.md  versioned prompts
n8n/smartrecruit.json  exported workflow
data/samples/          fictional job offer + 3 CVs (text PDF, two-column PDF, scanned PDF) + ground truth
eval/                  test queries, retrieval results
scripts/               sample generator, ESCO ingestion, retrieval eval, prompt comparison
presentation/          week 1 check-in deck (source)
```

## Limits we know about

- The vision path sends the page image to the LLM provider **before** anonymization (the name is on the image). For real CVs use a local vision model or a provider under a data processing agreement.
- The name detector is a heuristic; the anonymization test set was written by us (see the privacy doc).
- Retrieval labels are keyword-based (silver) until two team members check them.
- The free Gemini tier allows about 20 requests per day per model; one run of 3 CVs uses 15-20. The client falls back to a lighter model, and every result records the model that produced it.
- A missing page cannot be detected unless it leaves an empty page: "not evidenced" may hide it (see the consistency test).
