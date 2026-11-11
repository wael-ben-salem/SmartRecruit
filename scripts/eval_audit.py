"""Does the Audit agent catch misleading matches? Runs the LLM layer of the Audit agent (one call per
prompt version, all claims at once) on eval/audit_cases.json and measures:

  catch rate      share of wrong claims (expected overstated or unsupported) that the audit flags
  false alarms    share of correct claims (expected supported) that the audit flags
  exact verdict   share of cases where the verdict equals the expected one

    python scripts/eval_audit.py                       # versions v2 and v3, model from .env
    python scripts/eval_audit.py --model gemini-3.5-flash-lite --versions v3

Writes eval/audit_results.md and eval/audit_results.json.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from smartrecruit import config, llm, prompts  # noqa: E402


def run(version: str, cases: list[dict], model: str) -> dict[str, dict]:
    claims = [{"requirement_id": c["id"], "requirement": c["requirement"], "status": c["status"], "quotes": c["quotes"]} for c in cases]
    system, user = prompts.load("audit_agent", version)
    out = llm.chat_json(system, prompts.render(user, claims=json.dumps(claims, ensure_ascii=False)), model=model)
    return {c.get("requirement_id"): c for c in out.get("checks", [])}


def score(cases: list[dict], checks: dict[str, dict]) -> dict:
    wrong = [c for c in cases if c["expected"] != "supported"]
    right = [c for c in cases if c["expected"] == "supported"]
    verdict = lambda c: checks.get(c["id"], {}).get("verdict", "missing-from-output")
    flagged = lambda c: verdict(c) in ("overstated", "unsupported")
    return {
        "catch_rate": round(sum(flagged(c) for c in wrong) / len(wrong), 3),
        "false_alarm_rate": round(sum(flagged(c) for c in right) / len(right), 3),
        "exact_verdict": round(sum(verdict(c) == c["expected"] for c in cases) / len(cases), 3),
        "not_answered": sum(verdict(c) == "missing-from-output" for c in cases),
        "missed": [c["id"] for c in wrong if not flagged(c)],
        "false_alarms": [c["id"] for c in right if flagged(c)],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", default="v2,v3")
    ap.add_argument("--model", default=config.LLM_MODEL)
    ap.add_argument("--repeats", type=int, default=1, help="runs per version, to measure instability")
    args = ap.parse_args()
    cases = json.loads((ROOT / "eval" / "audit_cases.json").read_text(encoding="utf-8"))["cases"]

    results, lines, spread = {}, [], {}
    for v in args.versions.split(","):
        runs = [run(v, cases, args.model) for _ in range(args.repeats)]
        scores = [score(cases, c) for c in runs]
        results[v] = {"score": scores[-1], "checks": runs[-1], "all_scores": scores}
        spread[v] = {k: (min(s[k] for s in scores), round(sum(s[k] for s in scores) / len(scores), 3), max(s[k] for s in scores))
                     for k in ("catch_rate", "false_alarm_rate", "exact_verdict")}
    lines += [f"Model: {args.model} · {len(cases)} claims ({sum(c['expected'] == 'supported' for c in cases)} correct, "
              f"{sum(c['expected'] != 'supported' for c in cases)} wrong)", "",
              "| Prompt | Catch rate (wrong claims flagged) | False alarms (correct claims flagged) | Exact verdict | Missed | False alarms |",
              "|---|---|---|---|---|---|"]
    for v, r in results.items():
        s = r["score"]
        lines.append(f"| audit {v} | {s['catch_rate']} | {s['false_alarm_rate']} | {s['exact_verdict']} | {', '.join(s['missed']) or '–'} | {', '.join(s['false_alarms']) or '–'} |")
    if args.repeats > 1:
        lines += ["", f"Over {args.repeats} runs (min / mean / max):", "",
                  "| Prompt | Catch rate | False alarms | Exact verdict |", "|---|---|---|---|"]
        for v, s in spread.items():
            lines.append(f"| audit {v} | " + " | ".join(" / ".join(map(str, s[k])) for k in ("catch_rate", "false_alarm_rate", "exact_verdict")) + " |")
    lines += ["", "Per case, last run (expected → verdict per version):", ""]
    for c in cases:
        lines.append(f"- {c['id']} expected **{c['expected']}** → " + ", ".join(
            f"{v}: {r['checks'].get(c['id'], {}).get('verdict', '—')}" for v, r in results.items()) + f" · {c['requirement'][:60]}")
    (ROOT / "eval" / "audit_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ROOT / "eval" / "audit_results.json").write_text(json.dumps({"model": args.model, **results}, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n".join(lines[:6 + len(results)]))


if __name__ == "__main__":
    main()
