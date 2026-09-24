"""Run the 24 judge cases against Needle 3, in both modes, and write a result file.

Needle is not a service here. It runs in the same process, because the package holds
no server. The result file has the same shape as `../judge_bench.py` writes, so
`../results_table.py` puts Needle next to every other judge.

It runs inside the container on the model host:
  podman run --rm -v ~/needle-smoke:/app:ro -v ~/needle-cache:/root/.cache \\
    -v <repo>/poc:/poc:ro needle-smoke python /app/needle_bench.py \\
    --cases /poc/judge_cases.jsonl --out /app/out

Needle answers with 1 label and 1 confidence value, and with no probability per option.
The probability fields therefore stay empty, and the calibration column stays empty too.
An abstention counts as a wrong answer, exactly as JevBench does.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import date
from pathlib import Path

import needle

DIFFICULTY = ("How hard is this request for a language model? Judge the reasoning that the answer "
              "needs, not the length of the text.")
LEVELS = {
    "simple": "A fact, a definition, a short rewrite, a translation, a greeting, or a question with "
              "one clear answer.",
    "medium": "A short explanation, a small piece of code, a summary, or a comparison with 2 or 3 "
              "reasoning steps.",
    "hard": "A multi-step analysis, a design or an architecture question, a proof, a long piece of "
            "code, or a trade-off between several options.",
}
SENSITIVE = ("Does the conversation contain personal data or sensitive information? Personal data is "
             "a name, an address, an e-mail address, a telephone number, a bank or a medical detail "
             "of a person. Sensitive information is a password, an API key, an internal IP address, "
             "or a private file path.")


def record_tool(question: str, param: dict) -> list:
    return [{"name": "record_decision",
             "description": "Record the answer to this question about the text: " + question,
             "parameters": {"type": "object", "properties": {"decision": param},
                            "required": ["decision"]}}]


def option_tools() -> list:
    return [{"name": name, "description": text,
             "parameters": {"type": "object", "properties": {}, "required": []}}
            for name, text in LEVELS.items()]


def ask(tools: list, system: str, text: str, pick_name: bool) -> tuple:
    agent = needle.Needle(tools=tools, system=system)
    started = time.perf_counter()
    try:
        out = agent.complete(text, max_new_tokens=128)
    finally:
        agent.close()
    seconds = time.perf_counter() - started
    calls = out.get("function_calls") or []
    value = None
    if calls:
        value = calls[0].get("name") if pick_name else (calls[0].get("arguments") or {}).get("decision")
    return value, seconds, out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="/poc/judge_cases.jsonl")
    parser.add_argument("--out", default="/app/out")
    parser.add_argument("--mode", choices=("record_decision", "tools"), default="record_decision",
                        help="how a choice question becomes a tool")
    args = parser.parse_args()

    cases = [json.loads(line) for line in Path(args.cases).read_text().splitlines() if line.strip()]
    version = getattr(needle, "__version__", "unknown")
    model = f"needle3-{args.mode}"
    print(f"judge model: {model} (cactus-needle {version}) | cases: {len(cases)}")

    results, times, abstentions = [], [], 0
    for case in cases:
        text = case["text"]
        if args.mode == "tools":
            difficulty, d_seconds, d_out = ask(option_tools(), DIFFICULTY, text, pick_name=True)
        else:
            param = {"type": "string", "enum": list(LEVELS),
                     "description": DIFFICULTY + " Options: "
                                    + "; ".join(f"{k}: {v}" for k, v in LEVELS.items())}
            difficulty, d_seconds, d_out = ask(record_tool(DIFFICULTY, param), DIFFICULTY, text,
                                               pick_name=False)
        raw, s_seconds, s_out = ask(record_tool(SENSITIVE, {"type": "boolean", "description": SENSITIVE}),
                                    SENSITIVE, text, pick_name=False)
        sensitive = None
        if isinstance(raw, bool):
            sensitive = raw
        elif isinstance(raw, str) and raw.lower() in ("true", "false", "yes", "no"):
            sensitive = raw.lower() in ("true", "yes")

        seconds = d_seconds + s_seconds
        row = {"id": case["id"], "round": case["round"], "seconds": round(seconds, 3),
               "expected_sensitive": case["sensitive"], "sensitive": sensitive,
               "sensitive_p": None, "expected_difficulty": case["difficulty"],
               "difficulty": difficulty, "difficulty_p": None,
               "sensitive_ok": sensitive == case["sensitive"],
               "difficulty_ok": difficulty == case["difficulty"],
               "abstained_difficulty": difficulty is None, "abstained_sensitive": sensitive is None,
               "confidence_difficulty": d_out.get("confidence"),
               "confidence_sensitive": s_out.get("confidence"),
               "peak_ram_mb": d_out.get("peak_ram_mb")}
        row["ok"] = row["sensitive_ok"] and row["difficulty_ok"]
        abstentions += int(row["abstained_difficulty"]) + int(row["abstained_sensitive"])
        results.append(row)
        times.append(seconds)
        mark = "ok " if row["ok"] else "BAD"
        print(f"  {mark} {case['id']} sensitive {str(sensitive):5s} (want {case['sensitive']!s:5s}) "
              f"difficulty {str(difficulty):6s} (want {case['difficulty']:6s}) {seconds:.2f} s")

    summary = {"judge_model": model, "judge": f"in-process cactus-needle {version}",
               "date": date.today().isoformat(), "rounds": sorted({c["round"] for c in cases}),
               "cases": len(results), "mode": args.mode, "abstentions": abstentions,
               "sensitive_correct": sum(r["sensitive_ok"] for r in results),
               "difficulty_correct": sum(r["difficulty_ok"] for r in results),
               "both_correct": sum(r["ok"] for r in results),
               "seconds_mean": round(statistics.mean(times), 3),
               "seconds_max": round(max(times), 3), "results": results}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name = f"judge-{model}-r{''.join(str(r) for r in summary['rounds'])}-{summary['date']}.json"
    (out / name).write_text(json.dumps(summary, indent=2) + "\n")
    print(f"sensitive {summary['sensitive_correct']}/{len(results)}, "
          f"difficulty {summary['difficulty_correct']}/{len(results)}, "
          f"both {summary['both_correct']}/{len(results)}, "
          f"abstentions {abstentions}/{2 * len(results)}, mean {summary['seconds_mean']} s. "
          f"Written to {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
