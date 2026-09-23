"""Run the router test examples, check the route, and write the result to a file.

Usage:
  python3 run_tests.py [--url http://<POC_IP>:8081] [--label <name>]

It runs 7 examples: 5 normal requests and 2 stream requests. For each example it
compares the route with the expected route. It reads the judge model from
`/health`, and it writes `results/<judge>-<date>.json` next to this file.
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.request
from datetime import date
from pathlib import Path

import envload  # it reads .env from the repository root

CASES = [
    ("simple", "qwen3.8-27b-nothink", False,
     "What is the capital of France?"),
    ("medium", "qwen3.8-27b-local", False,
     "Write a bash one-liner that counts the lines of every .py file in a folder, and explain it."),
    ("hard", "qwen3.7-max", False,
     "Design a fault-tolerant job queue for a 3-node cluster. Compare at-least-once and "
     "exactly-once delivery, and explain the trade-offs for retries, idempotency and back pressure."),
    ("sensitive and hard", "qwen3.8-27b-local", False,
     "Here is my mortgage file: loan 124, 84384.42 euro at 2.69 percent, owner Peppe Kerstens, "
     "IBAN NL91ABNA0417164300. Design the optimal repayment plan across the 3 loans and compare "
     "the tax effects."),
    ("sensitive and simple", "qwen3.8-27b-local", False,
     "My colleague Jan de Vries lives at Kerkstraat 12 in Utrecht. Write a one-line greeting for "
     "his birthday card."),
    ("stream, simple", "qwen3.8-27b-nothink", True,
     "What is the capital of France?"),
    ("stream, hard", "qwen3.7-max", True,
     "Design a fault-tolerant job queue for a 3-node cluster and compare the delivery guarantees."),
]
TIMEOUT_S = 900


def post(url: str, body: dict, stream: bool):
    data = json.dumps(body).encode()
    request = urllib.request.Request(url + "/v1/chat/completions", data=data,
                                     headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        headers = {k.lower(): v for k, v in response.headers.items()}
        raw = response.read()
    return headers, raw, time.perf_counter() - started


def run_case(url: str, case: tuple) -> dict:
    name, expected, stream, prompt = case
    body = {"messages": [{"role": "user", "content": prompt}]}
    if stream:
        body["stream"] = True
    headers, raw, seconds = post(url, body, stream)
    out = {"case": name, "expected": expected, "stream": stream, "seconds": round(seconds, 2)}
    if stream:
        text = raw.decode("utf-8", "replace")
        events = [line[6:].strip() for line in text.splitlines() if line.startswith("data: ")]
        out["events"] = len(events)
        out["ends_with_done"] = bool(events) and events[-1] == "[DONE]"
        out["route"] = headers.get("x-jev-route")
        out["reason"] = headers.get("x-jev-reason")
        out["difficulty"] = headers.get("x-jev-difficulty")
        out["sensitive"] = headers.get("x-jev-sensitive") == "true"
        out["judge_seconds"] = float(headers.get("x-jev-judge-seconds", 0))
        answer = ""
        for event in events:
            if event == "[DONE]":
                continue
            try:
                chunk = json.loads(event)
            except json.JSONDecodeError:
                continue
            for choice in chunk.get("choices", []):
                answer += (choice.get("delta") or {}).get("content") or ""
            if "error" in chunk:
                out["stream_error"] = json.dumps(chunk["error"])[:200]
        out["answer_head"] = re.sub(r"\s+", " ", answer)[:120]
    else:
        data = json.loads(raw)
        route = data.get("x_jev_router", {})
        out["route"] = route.get("chosen")
        out["reason"] = route.get("reason")
        out["difficulty"] = route.get("difficulty")
        out["sensitive"] = bool(route.get("sensitive"))
        out["judge_seconds"] = round(float(route.get("judge_seconds") or 0), 3)
        message = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        out["answer_head"] = re.sub(r"\s+", " ", message)[:120]
    out["correct"] = out["route"] == expected
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.environ.get(
        "ROUTER_URL", f"http://{envload.need('POC_IP')}:8081"))
    parser.add_argument("--label", default=None, help="name of the result file, default the judge model")
    args = parser.parse_args()

    with urllib.request.urlopen(args.url + "/health", timeout=30) as response:
        health = json.loads(response.read())
    judge = (health.get("judge") or {}).get("model", "unknown")
    label = args.label or judge.split("/")[-1].lower()
    print(f"judge model: {judge}")

    results = []
    for case in CASES:
        result = run_case(args.url, case)
        results.append(result)
        mark = "ok " if result["correct"] else "BAD"
        print(f"  {mark} {result['case']:22s} -> {result['route']:20s} "
              f"judge {result['judge_seconds']:.2f} s, total {result['seconds']:.1f} s"
              + (f", {result['events']} events" if result["stream"] else ""))
        if result.get("stream_error"):
            print(f"      the backend ended the stream with an error: {result['stream_error'][:100]}")

    correct = sum(r["correct"] for r in results)
    judge_times = [r["judge_seconds"] for r in results]
    summary = {"judge_model": judge, "router": args.url, "date": date.today().isoformat(),
               "correct": correct, "cases": len(results),
               "judge_seconds_mean": round(sum(judge_times) / len(judge_times), 3),
               "judge_seconds_max": max(judge_times), "results": results}
    out = Path(__file__).parent / "results" / f"{label}-{summary['date']}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"routes correct: {correct}/{len(results)}. Written to {out}")
    return 0 if correct == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
