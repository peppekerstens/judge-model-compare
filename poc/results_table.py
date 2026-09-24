"""Build the comparison tables from the files in `results/`.

Usage: python3 results_table.py > results/tables.md

It reads every `judge-*.json` (the judge bench) and every other `*.json`
(the end-to-end router test), and it prints Markdown. Standard library only.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

RESULTS = Path(__file__).parent / "results"
# The Qwen judges run on the legion GPU. Laya runs on the legion CPU, so it uses no VRAM.
VRAM = {"Qwen/Qwen3.5-2B": "1,712 MiB", "Qwen/Qwen3.5-4B": "3,568 MiB", "Qwen/Qwen3.5-9B": "5,932 MiB",
        "convaiinnovations/laya-multilingual": "none, CPU", "laya-multilingual-gpu": "1,715 MiB",
        "qwen3.5-4b-decision-fork": "3,452 MiB",
        "qwen3.5-4b-decision-fork-true_only": "3,452 MiB",
        "qwen3.5-4b-decision-fork-both": "3,452 MiB",
        "qwen3.5-4b-decision-fork-enum": "3,452 MiB",
        "needle3-record_decision": "none, CPU", "needle3-tools": "none, CPU"}
ORDER = ["Qwen/Qwen3.5-2B", "Qwen/Qwen3.5-4B", "Qwen/Qwen3.5-9B",
         "qwen3.5-4b-decision-fork", "qwen3.5-4b-decision-fork-true_only",
         "qwen3.5-4b-decision-fork-both", "qwen3.5-4b-decision-fork-enum",
         "convaiinnovations/laya-multilingual", "laya-multilingual-gpu",
         "needle3-record_decision", "needle3-tools"]
# The CPU run and the GPU run of Laya report the same model name, so the label of the
# result file separates them.
LABEL_AS_MODEL = {"laya-multilingual-gpu"}


def load(pattern: str) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(RESULTS.glob(pattern))]


def judge_table() -> None:
    by_model: dict[str, list[dict]] = {}
    for path in sorted(RESULTS.glob("judge-*.json")):
        run = json.loads(path.read_text())
        name = run["judge_model"]
        for label in LABEL_AS_MODEL:
            if path.name.startswith(f"judge-{label}-"):
                name = label
        by_model.setdefault(name, []).extend(run["results"])
    print("## Judge bench: 24 cases, both questions\n")
    print("| Judge model | VRAM | Sensitive | Difficulty | Both | Median time | Mean time | Slowest |")
    print("|---|---|---|---|---|---|---|---|")
    for model in [m for m in ORDER if m in by_model] + [m for m in by_model if m not in ORDER]:
        rows = by_model[model]
        times = [r["seconds"] for r in rows]
        print(f"| {model} | {VRAM.get(model, '-')} | "
              f"{sum(r['sensitive_ok'] for r in rows)}/{len(rows)} | "
              f"{sum(r['difficulty_ok'] for r in rows)}/{len(rows)} | "
              f"{sum(r['ok'] for r in rows)}/{len(rows)} | "
              f"{statistics.median(times):.2f} s | {statistics.mean(times):.2f} s | {max(times):.2f} s |")

    print("\n### The cases that a judge reads differently\n")
    # The header follows ORDER, so a new judge needs no edit here.
    short = {"Qwen/Qwen3.5-2B": "2B", "Qwen/Qwen3.5-4B": "4B", "Qwen/Qwen3.5-9B": "9B",
             "qwen3.5-4b-decision-fork": "fork", "qwen3.5-4b-decision-fork-true_only": "fork true_only",
             "qwen3.5-4b-decision-fork-both": "fork both", "qwen3.5-4b-decision-fork-enum": "fork enum",
             "convaiinnovations/laya-multilingual": "Laya CPU", "laya-multilingual-gpu": "Laya GPU",
             "needle3-record_decision": "Needle record", "needle3-tools": "Needle tools"}
    columns = [m for m in ORDER if m in by_model]
    print("| Case | Wanted | " + " | ".join(short.get(m, m) for m in columns) + " |")
    print("|" + "---|" * (len(columns) + 2))
    ids = sorted({r["id"] for rows in by_model.values() for r in rows})
    for case_id in ids:
        picks = {}
        want = None
        for model, rows in by_model.items():
            row = next((r for r in rows if r["id"] == case_id), None)
            if row:
                picks[model] = row
                want = row["expected_difficulty"], row["expected_sensitive"]
        if all(r["ok"] for r in picks.values()):
            continue
        cells = []
        for model in columns:
            row = picks.get(model)
            if not row:
                cells.append("-")
                continue
            # An abstention gives None. Needle abstains, and that counts as a wrong answer.
            text = "ok" if row["difficulty"] == want[0] else str(row["difficulty"] or "abstained")
            if row["sensitive"] != want[1]:
                text += ", sensitive %s" % (row["sensitive"] if row["sensitive"] is not None else "abstained")
            cells.append(text)
        print(f"| {case_id} | {want[0]}, sensitive {want[1]} | " + " | ".join(cells) + " |")


def router_table() -> None:
    runs = [r for r in load("*.json") if not r.get("rounds")]
    if not runs:
        return
    print("\n## End-to-end router test: 7 examples\n")
    print("| Judge model | Routes correct | Mean judge time | Slowest judge time |")
    print("|---|---|---|---|")
    for run in sorted(runs, key=lambda r: r["judge_model"]):
        times = [r["judge_seconds"] for r in run["results"]]
        print(f"| {run['judge_model']} | {run['correct']}/{run['cases']} | "
              f"{statistics.mean(times):.2f} s | {max(times):.2f} s |")


if __name__ == "__main__":
    judge_table()
    router_table()
