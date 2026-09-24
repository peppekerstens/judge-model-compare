"""Run the 24 cases through the PII gate, and write a result file.

    python3 pii-proxy/pii_bench.py                 the full chain
    python3 pii-proxy/pii_bench.py --no-audit      Presidio alone, no fork

It measures 4 things for each case.

  1. leaks         the strings of `must_mask` that still reach the cloud model
  2. over-mask     a mask on a case that holds no personal data
  3. audit         the answer of the fork on the masked text
  4. seconds       the time of each stage, apart

A leak is the number that matters. A leak means that a real value goes to the
cloud model. The chain is only safe when the leak count reaches 0, or when the
audit says "sensitive" and the router keeps the request inside the network.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gate  # noqa: E402


def load_env() -> None:
    """Read .env from the repository root, the same file the shell scripts read."""
    path = HERE.parent / ".env"
    if not path.exists():
        raise SystemExit(f"no {path}. Copy .env.example to .env and fill it in.")
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(HERE / "pii_cases.jsonl"))
    parser.add_argument("--out", default=str(HERE / "results"))
    parser.add_argument("--no-audit", action="store_true",
                        help="run Presidio alone, and skip the fork")
    parser.add_argument("--language", default="en")
    parser.add_argument("--tag", default="", help="a suffix for the result file name")
    args = parser.parse_args()

    load_env()
    analyzer = gate.env("PRESIDIO_ANALYZER_URL")
    fork = "" if args.no_audit else gate.env("DECISION_FORK_URL")
    name = "presidio-only" if args.no_audit else "presidio-plus-fork"
    if args.tag:
        name = f"{name}-{args.tag}"

    cases = [json.loads(line) for line in Path(args.cases).read_text().splitlines() if line.strip()]
    print(f"chain: {name} | analyzer: {analyzer} | cases: {len(cases)}")

    results, mask_times, audit_times = [], [], []
    for case in cases:
        masked = gate.mask(case["text"], analyzer, args.language)
        leaks = [s for s in case["must_mask"] if s in masked.text]
        round_trip = gate.restore(masked.text, masked.mapping) == case["text"]

        row = {"id": case["id"], "round": case["round"],
               "expected_sensitive": case["sensitive"],
               "expected_difficulty": case["difficulty"],
               "must_mask": case["must_mask"], "leaks": leaks,
               "entities": [{"type": s["entity_type"], "score": round(s["score"], 3),
                             "text": case["text"][s["start"]:s["end"]]}
                            for s in masked.entities],
               "masked_text": masked.text, "round_trip_exact": round_trip,
               "mask_seconds": round(masked.seconds, 4)}
        mask_times.append(masked.seconds)

        if args.no_audit:
            # Without the fork, the mask itself is the only signal.
            row["audit_sensitive"] = bool(masked.entities)
            row["audit_difficulty"] = None
            row["audit_seconds"] = 0.0
        else:
            audit = gate.audit(masked.text, fork)
            row["audit_sensitive"] = audit["sensitive"]
            row["audit_sensitive_p"] = round(audit["sensitive_p"], 4)
            row["audit_difficulty"] = audit["difficulty"]
            row["audit_difficulty_p"] = round(audit["difficulty_p"], 4)
            row["audit_seconds"] = round(audit["seconds"], 4)
            audit_times.append(audit["seconds"])

        target, reason = gate.route(row["audit_sensitive"], row["audit_difficulty"] or "medium")
        row["route"] = target
        row["route_reason"] = reason
        # A leak is only dangerous when the request still leaves the network.
        row["leak_to_cloud"] = bool(leaks) and target == "qwen3.7-max"
        row["over_mask"] = (not case["sensitive"]) and bool(masked.entities)
        row["seconds"] = round(masked.seconds + row["audit_seconds"], 4)
        results.append(row)

        flag = "LEAK" if row["leak_to_cloud"] else ("held" if leaks else "ok  ")
        print(f"  {flag} {case['id']} entities {len(masked.entities):2d} "
              f"leaks {len(leaks)} route {target:22s} "
              f"{row['mask_seconds']:.3f}+{row['audit_seconds']:.3f} s")

    summary = {
        "chain": name, "date": date.today().isoformat(),
        # The result file names the variable, and never the address.
        "analyzer": "$PRESIDIO_ANALYZER_URL",
        "fork": "$DECISION_FORK_URL" if fork else None,
        "cases": len(results),
        "leaks_total": sum(len(r["leaks"]) for r in results),
        "cases_with_a_leak": sum(1 for r in results if r["leaks"]),
        "leaks_to_cloud": sum(1 for r in results if r["leak_to_cloud"]),
        "over_masked_cases": sum(1 for r in results if r["over_mask"]),
        "round_trip_exact": sum(1 for r in results if r["round_trip_exact"]),
        # The audit reads the MASKED text, so a "no" on a fully masked case is
        # right, not wrong. The number that counts is the residual catch.
        "residual_cases": sum(1 for r in results if r["leaks"]),
        "residual_caught": sum(1 for r in results if r["leaks"] and r["audit_sensitive"]),
        "cleared_after_mask": sum(1 for r in results if r["expected_sensitive"]
                                  and not r["leaks"] and not r["audit_sensitive"]),
        "false_alarms": sum(1 for r in results if not r["expected_sensitive"]
                            and r["audit_sensitive"]),
        # Kept for the comparison with the judge bench. It measures the audit
        # against the label of the ORIGINAL text, which the audit never reads.
        "sensitive_correct_vs_original_label": sum(
            1 for r in results if r["audit_sensitive"] == r["expected_sensitive"]),
        "difficulty_correct": sum(1 for r in results
                                  if r["audit_difficulty"] == r["expected_difficulty"]),
        "mask_seconds_mean": round(statistics.mean(mask_times), 4),
        "mask_seconds_max": round(max(mask_times), 4),
        "audit_seconds_mean": round(statistics.mean(audit_times), 4) if audit_times else 0.0,
        "audit_seconds_max": round(max(audit_times), 4) if audit_times else 0.0,
        "results": results,
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"pii-{name}-{summary['date']}.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(f"\nresidual caught {summary['residual_caught']}/{summary['residual_cases']}, "
          f"cleared after the mask {summary['cleared_after_mask']}/8, "
          f"false alarms {summary['false_alarms']}/16.")
    print(f"leaks {summary['leaks_total']} in {summary['cases_with_a_leak']} cases, "
          f"{summary['leaks_to_cloud']} reach the cloud. "
          f"over-masked {summary['over_masked_cases']}/16. "
          f"round trip exact {summary['round_trip_exact']}/{len(results)}. "
          f"mask {summary['mask_seconds_mean']:.3f} s, audit {summary['audit_seconds_mean']:.3f} s.")
    print(f"written to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
