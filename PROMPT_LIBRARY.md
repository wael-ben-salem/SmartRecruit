# SmartRecruit · Prompt library

All prompts live in [prompts/](prompts/), one folder per prompt, one file per version (`v1.md`, `v2.md`, …).
The version used at run time is set in `.env` (`PROMPT_CV_AGENT=v2`, …) and written into every output
(`_meta.prompt_version`) and into the HTML report, so each result can be traced back to its prompt.

How to add a version: copy the latest file to `vN+1.md`, change it, record below **what failed, the evidence, and
the fix**, then run `python scripts/compare_prompts.py` (CV and Job agents) or a full pipeline run (Matching and
Audit agents) to compare the versions.

> **Status of the failure log.** The v1 → v2 changes below were designed from failure modes known for these
> tasks and from our first manual tests. Rows marked **(to confirm)** must be replaced by the numbers from
> `eval/prompt_runs/summary.md` once `compare_prompts.py` has been run with the team's API key. Do not report
> a failure as observed until it has been reproduced.

| Prompt | Agent | Role in the system | Current |
|---|---|---|---|
| `vision_reader` | (tool of the reader) | Transcribe a scanned or multi-column CV page into text, in reading order | v1 |
| `cv_agent` | CV Agent | Anonymized CV → structured profile, one quote per skill | v2 |
| `job_agent` | Job Analysis Agent | Job offer → atomic, typed requirements | v3 |
| `matching_agent` | Matching Agent | Requirement × CV excerpts → met / partial / missing + quotes | v2 |
| `audit_agent` | Audit Agent (LLM layer) | Do the quotes support the status claimed? | v3 |

---

## 1. `cv_agent`

**Role.** Turns one anonymized CV into the JSON profile used by the Matching agent. Feeds the ESCO normalizer.

**Techniques.** Role prompting · explicit JSON schema (structured output, `response_format=json_object`) ·
one few-shot example · grounding (verbatim quote + page per skill) · guardrails (no inference, no protected attributes).

| | v1 | v2 |
|---|---|---|
| Instruction | "Extract skills, experience, education, languages as JSON" | 8 explicit rules + schema + example |
| Output shape | free (keys only) | fixed schema, typed fields |
| Evidence | none | `evidence` (verbatim) + `page` per skill |
| Inference | allowed implicitly | forbidden: "never infer a skill from a job title" |
| Protected attributes | not mentioned | explicitly excluded |

**Failures and fixes.**

| # | Failure in v1 | Evidence | Fix in v2 |
|---|---|---|---|
| 1 | Skills returned as a flat list of strings with no proof, so the Matching agent cannot cite anything | `skills_without_quote` (to confirm) | `evidence` + `page` required; "if you cannot quote it, do not list it" |
| 2 | Skills inferred from titles (e.g. "Data Engineer" → "ETL", "Data modelling") | `skills_not_in_cv` (to confirm) | Rule 1 + example limited to written skills |
| 3 | Combined items ("Python/SQL/Spark") kept as one skill, so they don't match single requirements | output file (to confirm) | Rule 3: split lists |
| 4 | Output keys change between runs (`work_experience` vs `experience`) and break the code | observed while building the pipeline | Fixed schema |
| 5 | Risk: date of birth or nationality copied into the profile if the anonymizer misses it | `protected_attributes_output` (to confirm) | Rule 5 (second safety net after the anonymizer) |

---

## 2. `job_agent`

**Role.** Turns the offer into the checklist the Matching agent scores against. Its output decides the weights
(must-have = 2, nice-to-have = 1, set in code).

**Techniques.** Role prompting (senior technical recruiter) · decision rules with trigger words (EN + FR) ·
JSON schema · guardrail that moves discriminatory criteria to `discarded`.

| # | Failure in v1 | Evidence | Fix in v2 |
|---|---|---|---|
| 1 | Compound requirements ("Python and SQL") cannot be checked one by one | `compound_requirements` (to confirm) | Rule 1: atomic requirements, true alternatives ("AWS or GCP") kept together |
| 2 | "Nice to have" items marked must, or the reverse | `must` count vs the 6 in the offer (to confirm) | Rule 2: trigger words, "when unclear choose nice" |
| 3 | The sample offer contains "Candidates aged 25 to 30 preferred": v1 keeps it as a requirement | `age_criterion_kept` (to confirm) | Rule 7: moved verbatim to `discarded`, shown in the report |
| 4 | Soft skills treated as hard filters | `soft_skills_as_must` (to confirm) | Rule 3 |

**v2 → v3: failure observed on real data.** Run `20261028-154642-ddde99`, real LinkedIn offer *IT Support Specialist*
(job 3754918008), model gemini-3.5-flash.

| | v2 output (before) | v3 output (after, run `20261028-160545-a88e88`) |
|---|---|---|
| R1 | **must** · "On-site availability in Nashville, TN, Monday through Friday" | not a requirement |
| Working conditions | mixed into the requirements | `conditions`: Location Nashville TN · On-site · Full-time · Monday–Friday · Rotational on-call · salary · health insurance · mileage reimbursement (shown, never scored) |
| Degree "is desired" | nice (correct) | nice (correct) |
| Requirements | 14 (4 must) | 10 (3 must) |

Why it mattered: a CV cannot prove "on-site in Nashville", so every candidate lost a must-have, and judging it would push
the Matching agent towards the candidate's address (personal data the anonymizer removes). Fix: rule 7 ("if a CV could not
show it, it is not a requirement") and a separate `conditions` list.

**Still to watch in v3 (same run):** "Minimum of 1 year experience providing technical support" became the text
"Experience providing technical support" with `min_years: 1`. The duration is kept in `min_years`, which the Matching
agent receives, but the requirement shown to the recruiter no longer says "1 year". Candidate fix for v4: keep the
number in `text` too.

---

## 3. `matching_agent`

**Role.** For each requirement, reads the CV excerpts retrieved from Qdrant (RAG) and decides met / partial /
missing with quotes. Does **not** compute the score (done in code, `scoring.py`).

**Techniques.** Role prompting · rubric with one definition and one example per status · hidden step-by-step
reasoning with a short visible justification (≤ 30 words) · grounding guardrail (quotes only from the excerpts) ·
JSON schema · feedback loop from the Audit agent (`{feedback}` placeholder).

| # | Failure in v1 | Evidence | Fix in v2 |
|---|---|---|---|
| 1 | "partial" used as a safe default, so the ranking is flat | status distribution in `<cand>_match.json` (to confirm) | Definitions + one example per status |
| 2 | Paraphrased "quotes" that cannot be found in the CV | Audit round 1: `quote not found in the CV` (to confirm) | Rule 1: copy verbatim; audit sends them back |
| 3 | Absence of evidence read as "probably has it" (e.g. Docker assumed for a back-end developer) | to confirm | "Absence of evidence is missing, never a guess" |
| 4 | Long reasoning paragraphs (cost, unreadable report) | token count (to confirm) | Reasoning capped at 30 words |
| 5 | Model returned a numeric score in v1 that disagreed with its own statuses | observed while designing | Score removed from the prompt, computed in code |

---

## 4. `audit_agent`

**Role.** Second layer of the Audit agent. Layer 1 (code, `audit_agent.quote_in_cv`) checks that each quote
exists in the CV (exact or ≥ 0.9 similarity, to tolerate OCR noise). Layer 2 (this prompt) checks that the quote
supports the status.

**Techniques.** Role prompting (strict auditor) · closed-world guardrail · three-way verdict with definitions ·
suggested correction used by the feedback loop.

| # | Failure in v1 | Evidence | Fix in v2 |
|---|---|---|---|
| 1 | An LLM asked "are these claims correct?" approves almost everything, including quotes that are not in the CV | to confirm on round-1 issues | Quote existence moved to code (deterministic) |
| 2 | Binary verdict deletes useful but weak evidence | to confirm | `overstated` verdict + `suggested_status` |
| 3 | Uses outside knowledge ("this school is good") | to confirm | "You know nothing else about the candidate" |

**v2 → v3: measured.** Trigger: review feedback — a quote can exist in the CV and still not prove the requirement
("distributing classroom equipment" was accepted as technical support in the first real run). Test set:
[eval/audit_cases.json](eval/audit_cases.json), claims labelled supported / overstated / unsupported; script
`scripts/eval_audit.py`; model **gemini-3.5-flash-lite** (Flash was out of free quota), temperature 0, one call per version.

| Run | Set | Prompt | Wrong claims caught | Correct claims flagged | Exact verdict |
|---|---|---|---|---|---|
| 1 | 24 claims (8 correct, 16 wrong) | v2 | 16/16 | 1/8 | 87.5 % |
| 1 | same | v3 | 15/16 | 1/8 | 79.2 % |
| 2 | 28 claims (8 correct, 20 wrong) | v2 | 18/20 | 0/8 | 89.3 % |
| 2 | same | v3 | **19/20** | 0/8 | **92.9 %** |

What we learned, in order:
1. **Run 1 did not show v3 to be better.** The only "false alarm" (S01, both versions) was **our label error**: the requirement asks for
   1 year, the quote shows support work but no dates, and the audit only sees the quotes. Relabelled overstated (old label kept in the file).
   It also shows a design gap: for a duration requirement, the Matching agent should cite a quote that contains the dates.
2. **Run 1 caught the classroom-equipment claim (O01) for the wrong reason**: both versions flagged the missing "1 year", not the
   competence mismatch. We added O09 — the same quotes against a requirement with **no duration** — plus two "neighbouring activity"
   cases (using ≠ administering, selling ≠ supporting) and a supported case with dates (S09).
3. **Run 2: on O09, v2 says "supported", v3 says "overstated".** That is the case the review asked about, and the reason v3 is now in production.
4. **Instability:** O03 ("Active Directory knowledge" claimed as met for AD + Azure AD experience) was caught by v2 in run 1 and missed in
   run 2; v3 missed it twice. Single runs at temperature 0 are not stable: before the defence, run each version 5 times and report mean and range.

Labels are ours; they must be confirmed by two team members (`reviewed_by`), and the results re-run on gemini-3.5-flash.

---

## 5. `vision_reader`

**Role.** Multimodal step: used only when the router finds < 200 characters on a page (scan) or two text
columns. Transcribes the page image in reading order.

**Techniques.** Role prompting · explicit reading-order rules · faithfulness guardrail (transcribe, never summarize) ·
icons / progress bars turned into text.

| # | Risk | Mitigation |
|---|---|---|
| 1 | Columns interleaved line by line | Rule 2 (one column at a time) |
| 2 | Model "cleans up" or summarizes the CV, so quotes no longer match | Rule 1; the audit's near-match (0.9) tolerates small OCR differences |
| 3 | Photo described (bias) | Rule 5 |

v2 is planned once failures are observed on real scanned CVs (the sample `cv_C_scanned.pdf` is a clean synthetic scan).
