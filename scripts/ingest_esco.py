"""Load the ESCO skills taxonomy into Qdrant (collection esco_skills).

Download from https://esco.ec.europa.eu/en/use-esco/download (CSV, English; the French
file works too) and put the files in data/esco/. Two options:
  - digitalSkillsCollection_en.csv : ~1.3k digital skills, a few minutes on CPU (recommended)
  - skills_en.csv                  : ~13.9k skills, 20-40 minutes on CPU

Chunking: one point per skill (preferred label + alternative labels + description), the
natural unit of a taxonomy: splitting a skill would separate its synonyms from its label.

    python scripts/ingest_esco.py data/esco/digitalSkillsCollection_en.csv [--limit 500]
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from smartrecruit import vectorstore  # noqa: E402


def rows(path: str):
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            label = (r.get("preferredLabel") or "").strip()
            if not label:
                continue
            alts = [a.strip() for a in (r.get("altLabels") or "").split("\n") if a.strip()]
            desc = (r.get("description") or r.get("definition") or "").strip()
            yield {
                "label": label, "alt_labels": alts[:15], "uri": r.get("conceptUri"),
                "skill_type": r.get("skillType"), "description": desc[:400],
                "text": f"{label} | {', '.join(alts[:15])} | {desc[:300]}",
            }


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    items = list(rows(sys.argv[1]))[:limit]
    print(f"{len(items)} skills to index")
    for i in range(0, len(items), 256):
        batch = items[i:i + 256]
        vectorstore.upsert(vectorstore.SKILL_COLLECTION, [b.pop("text") for b in batch], batch)
        print(f"  {min(i + 256, len(items))}/{len(items)}")
    print("done:", vectorstore.client().count(vectorstore.SKILL_COLLECTION).count, "points in", vectorstore.SKILL_COLLECTION)


if __name__ == "__main__":
    main()
