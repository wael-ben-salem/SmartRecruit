"""Does anonymization work across CV layouts? Plants personal data in realistic places and measures
what leaks through anonymizer.anonymize(), and what useful content is wrongly removed.

    python scripts/eval_anonymization.py      # no LLM needed; writes eval/anonymization_results.md
"""
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
from smartrecruit import anonymizer  # noqa: E402

# (layout, text, {category: [strings that must disappear]}, [strings that must survive])
CASES = [
    ("single column, name on top",
     "[page 1]\nSarah Martin\nsarah.martin@example.com | +216 22 345 678\nEXPERIENCE\nData Engineer (2019 - 2022)\nBuilt pipelines in Python.",
     {"name": ["Sarah", "Martin"], "email": ["sarah.martin@example.com"], "phone": ["22 345 678"]},
     ["2019 - 2022", "Python"]),
    ("job title above the name",
     "[page 1]\nDATA ENGINEER\nSarah Martin\nPROFILE\nThree years in finance data.",
     {"name": ["Sarah", "Martin"]}, ["DATA ENGINEER", "finance"]),
    ("two-column transcription, name split over two lines",
     "[page 1]\nPROFILE\nFull-stack developer.\nEXPERIENCE\nWebify (01/2022 - present)\nCONTACT\nYoussef\nHaddad\ny.haddad@example.org\n+216 98 765 432",
     {"name": ["Youssef", "Haddad"], "email": ["y.haddad@example.org"], "phone": ["98 765 432"]}, ["01/2022 - present", "Webify"]),
    ("name repeated in references",
     "[page 1]\nAmira Ben Salah\nSKILLS\nSQL, Tableau\nREFERENCES\nAvailable on request - contact Amira Ben Salah directly.",
     {"name": ["Amira", "Salah"]}, ["SQL, Tableau"]),
    ("French CV, address and birth date",
     "[page 1]\nMohamed Trabelsi\n12 rue de Marseille, 1002 Tunis\nNé le 03/05/1998 à Sfax\nNationalité : tunisienne\nCOMPÉTENCES\nPython, Docker",
     {"name": ["Mohamed", "Trabelsi"], "address": ["rue de Marseille"], "birth": ["03/05/1998"], "nationality": ["tunisienne"]},
     ["Python, Docker"]),
    ("US formats",
     "[page 1]\nJohn Smith\n(555) 123-4567 · 742 Evergreen Terrace, Springfield\nAge: 27 · Married\nEXPERIENCE\nIT Support Technician (01/2021 - 06/2023)",
     {"name": ["John", "Smith"], "phone": ["123-4567"], "address": ["Evergreen Terrace"], "age": ["Age: 27"], "family": ["Married"]},
     ["01/2021 - 06/2023", "IT Support Technician"]),
    ("age in a sentence",
     "[page 1]\nLina Gharbi\nSUMMARY\n27 years old data analyst, single, looking for a first job.\nSKILLS\nExcel",
     {"name": ["Lina", "Gharbi"], "age": ["27 years old"], "family": ["single"]}, ["data analyst", "Excel"]),
    # the two cases below come from the real Kaggle CVs (found by running the anonymizer on all 120 IT CVs)
    ("real CV: referee details",
     "[page 1]\nSystems Integrator\nSupervisor: Robert Kessler - (520) 417-0959. Okay to contact.",
     {"third party": ["Robert Kessler", "417-0959"]}, ["Systems Integrator"]),
    ("real CV: certification year next to a year",
     "[page 1]\nMicrosoft Certified System Engineer (MCSE 2003) 2003\nMigrated single instance databases to a single domain.",
     {}, ["MCSE 2003", "single instance", "single domain"]),
    ("Kaggle-style CV (no name, job title in capitals)",
     "[page 1]\nINFORMATION TECHNOLOGY SPECIALIST\nSummary\nAccomplished with over 10 years of IT support experience.\nCity , State",
     {}, ["INFORMATION TECHNOLOGY SPECIALIST", "10 years of IT support"]),
]


def main():
    leaks, totals, broken = defaultdict(int), defaultdict(int), []
    details = []
    for layout, text, pii, keep in CASES:
        out = anonymizer.anonymize(text, "candidate")["text"]
        for cat, items in pii.items():
            for s in items:
                totals[cat] += 1
                if s.lower() in out.lower():
                    leaks[cat] += 1
                    details.append(f"- LEAK [{cat}] “{s}” · {layout}")
        for s in keep:
            totals["_kept"] += 1
            if s.lower() not in out.lower():
                broken.append(f"- REMOVED BY MISTAKE “{s}” · {layout}")

    lines = ["| Category | Planted | Leaked |", "|---|---|---|"]
    for cat in sorted(c for c in totals if c != "_kept"):
        lines.append(f"| {cat} | {totals[cat]} | {leaks[cat]} |")
    n_pii = sum(v for k, v in totals.items() if k != "_kept")
    lines += ["", f"Total: {sum(leaks.values())} of {n_pii} planted identifiers leaked; "
              f"{len(broken)} of {totals['_kept']} useful strings removed by mistake.", ""] + details + broken
    (ROOT / "eval" / "anonymization_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
