"""Tests that need no LLM and no embeddings: router, anonymizer, chunking, audit quote check, scoring.

    cd api && python -m pytest tests -q
"""
from pathlib import Path

import pymupdf

from smartrecruit import anonymizer, chunking, pdf_reader, scoring
from smartrecruit.agents import audit_agent

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"


def test_router_sends_scans_and_columns_to_vision():
    route = lambda f: [pdf_reader.route_page(p)[0] for p in pymupdf.open(SAMPLES / f)]
    assert route("cv_A_single_column.pdf") == ["text", "text"]
    assert route("cv_B_two_columns.pdf") == ["vision"]
    assert route("cv_C_scanned.pdf") == ["vision"]


def test_anonymizer_removes_contact_and_sensitive_but_keeps_dates():
    text = "Sarah Martin\nsarah@x.com | +216 22 345 678\nDate of birth: 14/03/1999\nData Engineer (2019 - 2022) at Acme"
    out = anonymizer.anonymize(text, "candidate_A")["text"]
    assert "Sarah" not in out and "Martin" not in out
    assert "sarah@x.com" not in out and "345 678" not in out and "1999" not in out
    assert "2019 - 2022" in out


def test_anonymizer_does_not_take_a_job_title_for_a_name():
    # observed on the Kaggle CV 39718499: "Coach" was replaced everywhere
    text = "[page 1]\nASSISTANT FOOTBALL COACH\nSummary\nAssistant coach for the varsity team since 2018."
    out = anonymizer.anonymize(text, "candidate_C")
    assert "NAME" not in out["removed"] and "coach for the varsity team" in out["text"]


def test_section_chunking_keeps_headings_and_pages():
    text = (SAMPLES / "ground_truth" / "cv_A_single_column.txt").read_text(encoding="utf-8")
    chunks = chunking.chunk(text, "section")
    sections = {c["section"] for c in chunks}
    assert {"experience", "education", "skills", "languages"} <= sections
    assert next(c for c in chunks if c["section"] == "education")["page"] == 2


def test_recursive_chunking_respects_size():
    text = " ".join(f"word{i}." for i in range(2000))
    assert all(chunking.tokens(c) <= 120 for c in chunking.recursive_split(text, 100, 20))


def test_quote_check_accepts_exact_and_near_rejects_invented():
    cv = "Built batch and streaming pipelines in Python and Apache Spark processing 2 TB per day."
    assert audit_agent.quote_in_cv("pipelines in Python and Apache Spark", cv)[0]
    assert audit_agent.quote_in_cv("pipelines in python and apache-spark", cv)[0]
    assert not audit_agent.quote_in_cv("5 years of Kubernetes administration", cv)[0]


# ---- score behaviour scenarios (review, priority 2) ----
JOB2 = {"requirements": [{"id": "R1", "type": "must", "weight": 2}, {"id": "R2", "type": "nice", "weight": 1}]}


def _m(*statuses):
    return {"assessments": [{"requirement_id": f"R{i}", "status": s} for i, s in enumerate(statuses, start=1)]}


def test_nice_present_but_must_absent_ranks_below_must_present():
    only_nice = scoring.score(_m("missing", "met"), JOB2)
    only_must = scoring.score(_m("met", "missing"), JOB2)
    assert only_nice["score"] < only_must["score"]
    assert only_nice["must_have_not_evidenced"] == ["R1"] and only_must["must_have_not_evidenced"] == []


def test_skill_not_mentioned_counts_zero_but_is_labelled_not_evidenced():
    s = scoring.score(_m("missing", "missing"), JOB2)
    assert s["score"] == 0.0
    assert scoring.STATUS_LABEL["missing"] == "Not evidenced in this CV"


def test_synonym_is_normalized_and_used_in_the_query():
    from smartrecruit import skills
    from smartrecruit.agents import matching_agent
    assert skills.normalize("k8s")["canonical"] == "Kubernetes"
    assert skills.normalize("JS")["canonical"] == "JavaScript"
    q = matching_agent.build_query({"text": "Kubernetes", "canonical_skills": ["Kubernetes"]})
    assert "k8s" in q  # a CV that only says "k8s" can still be retrieved


def test_poor_ocr_quote_is_still_found():
    cv = "Reso1ved hardware and softwar e tickets for 200 users at Northwind Clinics"  # OCR errors: 1 for l, split word
    assert audit_agent.quote_in_cv("Resolved hardware and software tickets for 200 users", cv)[0]


def test_missing_or_empty_page_is_flagged():
    read = {"pages": [{"page": 1, "method": "text", "text": "EXPERIENCE " + "word " * 200},
                      {"page": 2, "method": "vision", "text": ""}]}
    q = scoring.reading_quality(read)
    assert q["status"] == "check" and "page 2" in q["reasons"][0]
    assert scoring.score(_m("met", "missing"), JOB2, read)["reading_quality"]["status"] == "check"
    # a short last page (end of a skills list, seen on a real CV) is normal
    short_last = {"pages": [{"page": 1, "method": "text", "text": "word " * 300},
                            {"page": 2, "method": "text", "text": "Scanner, strategic planning, VPN, VOIP, Word Perfect"}]}
    assert scoring.reading_quality(short_last)["status"] == "ok"


def test_score_is_weighted_and_unverified_counts_zero():
    job = {"requirements": [{"id": "R1", "type": "must", "weight": 2}, {"id": "R2", "type": "nice", "weight": 1}]}
    match = {"assessments": [{"requirement_id": "R1", "status": "met"}, {"requirement_id": "R2", "status": "unverified"}]}
    s = scoring.score(match, job)
    assert s["score"] == round(100 * 2 / 3, 1) and s["must_have_met"] == "1/1" and s["unverified_claims"] == 1
