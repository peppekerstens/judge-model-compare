"""Compare judge models on the 2 router questions, without a model answer.

It sends each case in `judge_cases.jsonl` to the judge service, and it compares
the 2 answers with the expected labels. The question wording comes from
`router/router.yaml`, so the bench and the router always ask the same thing. It calls the judge directly, so no
answer model runs and no cloud request goes out.

Usage:
  python3 judge_bench.py [--judge http://<POC_IP>:8080] [--round 1] [--label name]

It writes `results/judge-<model>-r<rounds>-<date>.json` next to this file, and it
prints a short table. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.request
from datetime import date
from pathlib import Path

import envload  # it reads .env from the repository root

HERE = Path(__file__).parent


def questions() -> dict:
    """The same 2 questions as the router, read from router/router.yaml."""
    import yaml

    config = yaml.safe_load((HERE / "router" / "router.yaml").read_text())
    q = config["questions"]
    return {"sensitive": {"type": "noul", "instructions": q["sensitive"],
                          "criteria": {"true": q["sensitive_true"], "false": q["sensitive_false"]}},
            "difficulty": {"type": "choice", "instructions": q["difficulty"],
                           "criteria": q["difficulty_levels"]}}


QUESTIONS = questions()


def ask(judge: str, text: str) -> tuple[dict, float]:
    body = {"state": {"messages": [{"role": "user", "text": text}], "message_count": 1},
            "questions": QUESTIONS}
    request = urllib.request.Request(judge + "/v1/systemone",
                                    data=json.dumps(body).encode(),
                                    headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=300) as response:
        answers = json.loads(response.read())["answers"]
    return answers, time.perf_counter() - started


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge", default=os.environ.get(
        "JUDGE_URL", f"http://{envload.need('POC_IP')}:8080"))
    parser.add_argument("--round", type=int, action="append",
                        help="run only this round; repeat the flag for more rounds")
    parser.add_argument("--label", default=None)
    args = parser.parse_args()

    with urllib.request.urlopen(args.judge + "/health", timeout=30) as response:
        model = json.loads(response.read())["model"]
    rounds = sorted(set(args.round or []))
    cases = [json.loads(line) for line in (HERE / "judge_cases.jsonl").read_text().splitlines() if line.strip()]
    if rounds:
        cases = [c for c in cases if c["round"] in rounds]
    used_rounds = sorted({c["round"] for c in cases})
    print(f"judge model: {model} | cases: {len(cases)} | rounds: {used_rounds}")

    results, times = [], []
    for case in cases:
        answers, seconds = ask(args.judge, case["text"])
        sensitive = bool(answers["sensitive"]["noul"])
        difficulty = answers["difficulty"]["choice"]
        row = {"id": case["id"], "round": case["round"], "seconds": round(seconds, 3),
               "expected_sensitive": case["sensitive"], "sensitive": sensitive,
               "sensitive_p": round(answers["sensitive"]["probabilities"]["true"], 4),
               "expected_difficulty": case["difficulty"], "difficulty": difficulty,
               "difficulty_p": round(answers["difficulty"]["confidence"], 4),
               "sensitive_ok": sensitive == case["sensitive"],
               "difficulty_ok": difficulty == case["difficulty"]}
        row["ok"] = row["sensitive_ok"] and row["difficulty_ok"]
        results.append(row)
        times.append(seconds)
        mark = "ok " if row["ok"] else "BAD"
        print(f"  {mark} {case['id']} sensitive {sensitive!s:5s} (want {case['sensitive']!s:5s}) "
              f"difficulty {difficulty:6s} (want {case['difficulty']:6s}) {seconds:.2f} s")

    summary = {"judge_model": model, "judge": args.judge, "date": date.today().isoformat(),
               "rounds": used_rounds, "cases": len(results),
               "sensitive_correct": sum(r["sensitive_ok"] for r in results),
               "difficulty_correct": sum(r["difficulty_ok"] for r in results),
               "both_correct": sum(r["ok"] for r in results),
               "seconds_mean": round(statistics.mean(times), 3),
               "seconds_max": round(max(times), 3), "results": results}
    label = args.label or model.split("/")[-1].lower()
    name = f"judge-{label}-r{''.join(str(r) for r in used_rounds)}-{summary['date']}.json"
    out = HERE / "results" / name
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"sensitive {summary['sensitive_correct']}/{len(results)}, "
          f"difficulty {summary['difficulty_correct']}/{len(results)}, "
          f"both {summary['both_correct']}/{len(results)}, "
          f"mean {summary['seconds_mean']} s. Written to {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
