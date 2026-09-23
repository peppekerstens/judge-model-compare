"""Compare SemIf test runs with the public reference results.

Usage (on the buildbox, from /srv/semif-test):
  python3 compare.py runs/<label> [runs/<label> ...] > runs/compare.md

Standard library only. It reads:
  runs/<label>/authored144.eval.json    SemIf evaluate.py output
  runs/<label>/jevbench.results.jsonl   JevBench harness output (231 public items)
  runs/<label>/server.json              the GGUF that llama-server served
and the public references:
  SemIf/results/raw/browser-model-ladder.json   authored144, BF16, per model
  SemIf/README.md figure for the Qwen3.8-27B EXL3 bridge (0.958)
  jevbench/results/v1.2/jevbench-v1.2-per-task.json  per-item outcomes (JevBench v1.3.0)
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

LADDER = json.load(open("SemIf/results/raw/browser-model-ladder.json"))
AUTHORED_REF = {m["source"]: m["authored"] for m in LADDER["quality_boundary"]["models"]}
AUTHORED_REF["Qwen/Qwen3.8-27B"] = 0.958  # SemIf README, EXL3 5 bpw bridge, not a GGUF run

PER_TASK = json.load(open("jevbench/results/v1.2/jevbench-v1.2-per-task.json"))
TIER = {t["id"]: t["tier"] for t in PER_TASK["tasks"]}
SYSTEMS = PER_TASK["systems"]
SEMIF_KEY = "semif-qwen3.5-4b"
JEV_KEY = "jev-1.13.0"


def ref_outcomes(key: str) -> dict:
    return {tid: out[0] == "c" for tid, out in SYSTEMS[key]["public_tasks"].items()}


def ece(pairs: list[tuple[float, bool]], bins: int = 10) -> float | None:
    """Top-label expected calibration error in equal-width bins (JevBench method)."""
    if not pairs:
        return None
    total = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        inside = [(c, ok) for c, ok in pairs if (lo <= c < hi) or (b == bins - 1 and c == 1.0)]
        if inside:
            conf = sum(c for c, _ in inside) / len(inside)
            acc = sum(ok for _, ok in inside) / len(inside)
            total += len(inside) / len(pairs) * abs(conf - acc)
    return total


def parse(value):
    if isinstance(value, str):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return value
    return value


def tier_acc(outcomes: dict) -> dict:
    result = {}
    for tier in ("easy", "standard", "hard"):
        items = [ok for tid, ok in outcomes.items() if TIER.get(tid) == tier]
        result[tier] = (sum(items), len(items))
    items = list(outcomes.values())
    result["all"] = (sum(items), len(items))
    return result


def jevbench_run(run: Path) -> dict:
    rows = [json.loads(line) for line in open(run / "jevbench.results.jsonl")]
    outcomes, pairs, lat, failed = {}, [], [], 0
    for r in rows:
        ok = parse(r["correct"]) is True
        outcomes[r["task_id"]] = ok
        if parse(r["ok"]) is not True:
            failed += 1
        probs = parse(r["probs"])
        if isinstance(probs, dict) and probs and TIER.get(r["task_id"]) == "hard":
            pairs.append((max(probs.values()), ok))
        lat.append(float(r["latency_s"]))
    lat.sort()
    return {"outcomes": outcomes, "hard_ece": ece(pairs), "failed": failed,
            "p50_latency_s": lat[len(lat) // 2] if lat else None}


def pct(pair) -> str:
    c, n = pair
    return f"{100 * c / n:.1f} % ({c}/{n})" if n else "-"


def main(paths: list[str]) -> None:
    semif_ref = ref_outcomes(SEMIF_KEY)
    jev_ref = ref_outcomes(JEV_KEY)
    lines = ["| Run | GGUF | Tokenizer | authored144 | Reference (BF16) | Diff |", "|---|---|---|---|---|---|"]
    jb = ["| Run | Easy | Standard | Hard | All 231 | Hard ECE | Same outcome as SemIf ref | Failed | p50 latency |",
          "|---|---|---|---|---|---|---|---|---|"]
    for p in paths:
        run = Path(p)
        server = json.load(open(run / "server.json"))
        ev = json.load(open(run / "authored144.eval.json"))
        preds = [json.loads(line) for line in open(run / "authored144.predictions.jsonl")]
        model = preds[0]["model"]["source"]
        score = ev["mean_family_balanced_accuracy"]
        ref = AUTHORED_REF.get(model)
        missing = sum(1 for r in preds if r.get("missing_letters"))
        lines.append(f"| {run.name} | `{Path(server['model_path']).name}` | {model} | {score:.3f}"
                     f"{' (' + str(missing) + ' rows with a missing letter)' if missing else ''} | "
                     f"{ref:.3f} | {score - ref:+.3f} |" if ref is not None else
                     f"| {run.name} | `{Path(server['model_path']).name}` | {model} | {score:.3f} | - | - |")
        j = jevbench_run(run)
        t = tier_acc(j["outcomes"])
        same = sum(1 for tid, ok in j["outcomes"].items() if tid in semif_ref and semif_ref[tid] == ok)
        jb.append(f"| {run.name} | {pct(t['easy'])} | {pct(t['standard'])} | {pct(t['hard'])} | {pct(t['all'])} | "
                  f"{j['hard_ece']:.3f} | {same}/{len(j['outcomes'])} | {j['failed']} | {j['p50_latency_s']:.2f} s |")
    for label, ref in (("Published: SemIf Qwen3.5-4B BF16", semif_ref), ("Published: Jev 1.13.0", jev_ref)):
        t = tier_acc(ref)
        jb.append(f"| {label} | {pct(t['easy'])} | {pct(t['standard'])} | {pct(t['hard'])} | {pct(t['all'])} | - | - | - | - |")
    print("## Test 1: SemIf authored144 (mean family balanced accuracy)\n")
    print("\n".join(lines))
    print("\n## Test 2: JevBench public items (accuracy per tier)\n")
    print("\n".join(jb))


if __name__ == "__main__":
    main(sys.argv[1:])
