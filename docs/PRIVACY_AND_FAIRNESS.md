# SmartRecruit · Privacy, fairness and human control

Recruitment is a **high-risk use case** under the EU AI Act (Annex III) and CVs are personal data under the GDPR.
This page states what SmartRecruit does, what we measured, and what it does **not** guarantee. Anonymization helps, but
it does not by itself make the system fair or compliant.

## 1. What data goes where

| Data | Where it is processed | Where it is stored |
|---|---|---|
| CV PDF, job offer | API container (local) | `data/uploads/<run_id>/` |
| Text of text pages | local (PyMuPDF) | `data/runs/<run_id>/*_read.json` |
| **Image of scanned / multi-column pages** | **sent to the LLM provider (Gemini) BEFORE anonymization** — the name and photo are on the image | not stored by us beyond the run |
| Anonymized CV text, requirements, quotes | sent to the LLM provider for the 4 agents | `data/runs/<run_id>/` |
| Embeddings of CV chunks | local (Ollama, bge-m3) | Qdrant (local), tagged with `run_id` |
| Recruiter decisions and notes | local | `data/runs/<run_id>/decisions.json` + audit log |

The vision path is the main privacy gap: for real use, use a local vision model or a provider under a data processing
agreement, or blank the top of the page before sending it. The original file name (often the person's name) is kept
only in `run.json` and shown to the recruiter; it is never sent to an LLM.

## 2. Retention and deletion

- **Automatic retention:** every run (CV files, texts, agent outputs, vectors) is deleted after `RETENTION_DAYS`
  (default **30**), checked at every API start (`store.purge_older_than`).
- **Deletion on request:** "Delete analysis" in the dashboard, or `DELETE /api/runs/<run_id>`, removes the run folder,
  the uploads and the Qdrant points of that run.
- **Deletion log:** `data/deletions.jsonl` keeps only the run id, the date and the reason — no personal data.
- Not covered: backups of the host, the LLM provider's own retention (see its terms), copies the recruiter downloads.

## 3. Anonymization: what is removed and how well

Removed before the agents read a CV: candidate name (first line that looks like a name, or a first name / last name split
over two lines next to the contact details), e-mail, phone, URLs, birth date / gender / nationality / marital-status lines,
age, family status, street addresses, and **referees' names** (third-party data found in real CVs: "Supervisor: Mr. …").

Measured with `scripts/eval_anonymization.py` (10 layouts: single column, title above name, two-column with split name,
references, French address and birth date, US formats, age in a sentence, and two cases taken from real Kaggle CVs):

| Version | Planted identifiers leaked | Useful text removed by mistake |
|---|---|---|
| first version | **8 / 27** (addresses, age, family status, split name) | 0 / 14 |
| current | 0 / 29 | 0 / 18 |

On the **120 real IT CVs** (which contain no candidate names but do contain referees' details), the first version removed
"single" in "single instance database" 6 times and treated "(MCSE 2003) 2003" as a phone number; both fixed. The
current version removes 18 phone numbers, 10 referee names, 13 URLs, 2 e-mails, 2 addresses.

**Caveat:** the test cases were written by us and the fixes were made against them, so 0 / 29 is optimistic. Names in
unusual positions, non-Latin names, and the text inside photos or logos are not covered. A held-out set written by
another team member is needed for an honest number.

## 4. Protected characteristics are never scored

- The **Job Analysis agent** moves criteria about age, gender, origin, nationality, religion, family status, health or
  appearance to `discarded` (shown to the recruiter, never scored). Working conditions (location, schedule, salary) go to
  `conditions`, also never scored — a CV cannot prove them and checking them would point at the candidate's address.
- The **Matching agent** is told to ignore names, age, gender, origin and photos; it only sees anonymized text.
- The **score** uses only the requirement statuses and fixed weights (must-have 2, nice-to-have 1), computed in code.

## 5. What the score means

The score measures **how well the CV documents the requirements**, not the candidate's worth. "Not evidenced in this CV"
is not "the candidate does not have this skill": it is a question for the interview. Must-have requirements that are not
evidenced are listed separately, and a **reading-quality** flag warns when a page is empty or a scan was transcribed, so
that "not evidenced" can come from a reading problem.

## 6. The recruiter stays in control

- No automatic rejection or shortlisting; the ranking is a reading order.
- The recruiter records the decision per candidate (invite to interview / undecided / not retained) with a note; it is
  stored with the evidence and logged (`recruiter_decision` in `audit_log.jsonl`).
- Every conclusion shows its quotes and page, and the audit verdict, so it can be checked against the CV.

## 7. Consistency (fairness) tests

| Test | Status |
|---|---|
| Same CV as text PDF and as a scan: same statuses? | text extraction identical at 99.4 %; full agent comparison: `scripts/eval_consistency.py` (to run) |
| Same CV, skills written with synonyms ("k8s" / "Kubernetes") | normalization + query expansion unit-tested; agent-level test in `eval_consistency.py` |
| Score behaviour (must vs nice, not evidenced, unverified, empty page) | unit tests in `api/tests/test_offline.py` |

## 8. What is NOT done (AI Act obligations for high-risk systems)

A real deployment would also need: a risk-management process, data-governance documentation for any training or tuning
data, accuracy and bias monitoring over time (selection rates per group, with the legal basis to collect that data),
logging retained for the legally required period, information to candidates that AI is used, and a DPIA. This
student project implements human oversight, logging, transparency of each conclusion and deletion; it does not claim
compliance.
