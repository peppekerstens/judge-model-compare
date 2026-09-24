"""Send real traffic through the PII gate, and compare the answer with the raw answer.

    python3 pii-proxy/real_traffic.py                 all 12 cases
    python3 pii-proxy/real_traffic.py --cases 4       the first 4 cases
    python3 pii-proxy/real_traffic.py --no-judge      skip the quality judge

For each case it makes 3 calls.

  1. Through the gate. The model reads the masked text, and the gate restores
     the original values in the answer.
  2. Straight to the same model, with the raw text. This is the answer the user
     gets today, with no mask.
  3. A judge reads both answers, and says whether they do the same job.

It checks 4 things that need no judgement:

  a. no placeholder such as `<PERSON_1>` stays in the answer of the gate
  b. the answer of the gate holds the original values again, when the raw
     answer holds them too
  c. the route header matches the decision of the gate
  d. the stream gives the same answer as the normal call

The test writes `results/traffic-<date>.json` with every answer, so a later
reader can judge the quality again without a new run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from datetime import date
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gate  # noqa: E402

PLACEHOLDER = re.compile(r"<[A-Z][A-Z_]*_\d+>")

JUDGE_PROMPT = """Two assistants answered the same request.

Answer A came from the model that read the request with the personal data removed.
Answer B came from the model that read the request in full.

Say whether answer A does the same job for the user as answer B.
Answer with one word: yes or no. Then give one short sentence with the reason.

REQUEST:
{request}

ANSWER A:
{a}

ANSWER B:
{b}
"""


def load_env() -> None:
    path = HERE.parent / ".env"
    if not path.exists():
        raise SystemExit(f"no {path}. Copy .env.example to .env and fill it in.")
    for source in (path, Path.home() / ".env"):
        if not source.exists():
            continue
        for line in source.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def chat(client: httpx.Client, url: str, key: str, model: str, text: str,
         max_tokens: int = 1500) -> tuple:
    """One normal call. It returns the text, the headers and the time."""
    started = time.perf_counter()
    answer = client.post(f"{url}/v1/chat/completions", headers=(
        {"Authorization": f"Bearer {key}"} if key else {}), json={
        "model": model, "max_tokens": max_tokens, "temperature": 0,
        "cache": {"no-cache": True},
        "messages": [{"role": "user", "content": text}]})
    seconds = time.perf_counter() - started
    if answer.status_code != 200:
        return f"HTTP {answer.status_code}: {answer.text[:200]}", dict(answer.headers), seconds
    payload = answer.json()
    content = payload["choices"][0]["message"].get("content") or ""
    return content, dict(answer.headers), seconds


def chat_stream(client: httpx.Client, url: str, key: str, model: str, text: str,
                max_tokens: int = 1500) -> tuple:
    """One stream call. It joins the chunks, and returns the same shape."""
    started = time.perf_counter()
    out, headers, first = [], {}, None
    with client.stream("POST", f"{url}/v1/chat/completions", headers=(
            {"Authorization": f"Bearer {key}"} if key else {}), json={
            "model": model, "max_tokens": max_tokens, "temperature": 0, "stream": True,
            "cache": {"no-cache": True},
            "messages": [{"role": "user", "content": text}]}) as answer:
        headers = dict(answer.headers)
        for line in answer.iter_lines():
            if first is None:
                first = time.perf_counter() - started
            if not line.startswith("data: "):
                continue
            body = line[6:].strip()
            if body == "[DONE]":
                break
            try:
                delta = json.loads(body)["choices"][0].get("delta", {})
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
            out.append(delta.get("content") or "")
    return "".join(out), headers, time.perf_counter() - started, first


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=12)
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--out", default=str(HERE / "results"))
    args = parser.parse_args()

    load_env()
    gate_url = f"http://{os.environ['POC_IP']}:8086"
    upstream = os.environ["LITELLM_URL"]
    key = os.environ.get("LITELLM_KEY", "")
    # The judge must not reason, or the token budget goes to the reasoning.
    judge_model = os.environ.get("TRAFFIC_JUDGE", "qwen3.8-27b-nothink")

    cases = [json.loads(line) for line in
             (HERE / "pii_cases.jsonl").read_text().splitlines() if line.strip()]
    # 8 sensitive cases first, then 4 clean ones, so a short run still covers both.
    cases = [c for c in cases if c["sensitive"]] + [c for c in cases if not c["sensitive"]]
    cases = cases[:args.cases]
    print(f"gate: {gate_url} | upstream: {upstream} | cases: {len(cases)}")

    results, gate_times, raw_times = [], [], []
    with httpx.Client(timeout=900) as client:
        for case in cases:
            gate_text, headers, gate_s = chat(client, gate_url, "", "auto", case["text"])
            route = headers.get("x-pii-route", "")
            left = PLACEHOLDER.findall(gate_text)
            # A secret placeholder stays in the answer on purpose, so it is not a
            # defect. Every other placeholder is one.
            kept = [x for x in left if gate.is_secret(x)]
            defects = [x for x in left if not gate.is_secret(x)]
            restored = [s for s in case["must_mask"] if s in gate_text]
            raw_text, _, raw_s = chat(client, upstream, key, route or "qwen3.8-27b-local",
                                      case["text"])
            gate_times.append(gate_s)
            raw_times.append(raw_s)

            row = {"id": case["id"], "sensitive": case["sensitive"],
                   "difficulty": case["difficulty"], "request": case["text"],
                   "route": route, "reason": headers.get("x-pii-reason", ""),
                   "entities": headers.get("x-pii-entities", ""),
                   "remains": headers.get("x-pii-remains", ""),
                   "judged_difficulty": headers.get("x-pii-difficulty", ""),
                   "mask_seconds": float(headers.get("x-pii-mask-seconds", 0) or 0),
                   "audit_seconds": float(headers.get("x-pii-audit-seconds", 0) or 0),
                   "gate_seconds": round(gate_s, 2), "raw_seconds": round(raw_s, 2),
                   "gate_answer": gate_text, "raw_answer": raw_text,
                   "placeholders_left": left,
                   "secrets_kept": kept, "placeholder_defects": defects,
                   "values_restored": restored,
                   "gate_answer_chars": len(gate_text), "raw_answer_chars": len(raw_text)}

            if not args.no_judge:
                verdict, _, _ = chat(client, upstream, key, judge_model,
                                     JUDGE_PROMPT.format(request=case["text"],
                                                         a=gate_text, b=raw_text),
                                     max_tokens=200)
                row["judge_verdict"] = verdict.strip()
                row["same_job"] = verdict.strip().lower().lstrip("*# ").startswith("yes")
            results.append(row)
            mark = "BAD " if defects else "ok  "
            print(f"  {mark} {case['id']} route {route:20s} left {len(left)} "
                  f"restored {len(restored)}/{len(case['must_mask'])} "
                  f"same_job {row.get('same_job', '-')} "
                  f"{gate_s:.1f}s vs {raw_s:.1f}s")

        # 2 stream calls, 1 with personal data and 1 without.
        streams = []
        clean = next((c for c in cases if not c["sensitive"]), cases[-1])
        for case in (cases[0], clean):
            text, headers, seconds, first = chat_stream(client, gate_url, "", "auto",
                                                        case["text"])
            streams.append({"id": case["id"], "route": headers.get("x-pii-route", ""),
                            "seconds": round(seconds, 2),
                            "first_chunk_seconds": round(first or 0, 2),
                            "placeholders_left": PLACEHOLDER.findall(text),
                            "values_restored": [s for s in case["must_mask"] if s in text],
                            "answer": text, "chars": len(text)})
            print(f"  stream {case['id']} {seconds:.1f}s, first chunk "
                  f"{(first or 0):.1f}s, left {len(streams[-1]['placeholders_left'])}")

    summary = {
        "date": date.today().isoformat(), "gate": "$POC_IP:8086", "upstream": "$LITELLM_URL",
        "cases": len(results),
        "placeholder_defects": sum(1 for r in results if r["placeholder_defects"]),
        "secrets_kept_masked": sum(1 for r in results if r["secrets_kept"]),
        "same_job": sum(1 for r in results if r.get("same_job")),
        "judged": sum(1 for r in results if "same_job" in r),
        "gate_seconds_mean": round(statistics.mean(gate_times), 2),
        "raw_seconds_mean": round(statistics.mean(raw_times), 2),
        "mask_seconds_mean": round(statistics.mean(r["mask_seconds"] for r in results), 4),
        "audit_seconds_mean": round(statistics.mean(r["audit_seconds"] for r in results), 4),
        "streams": streams, "results": results}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"traffic-{summary['date']}.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(f"\nplaceholder defects {summary['placeholder_defects']}/{len(results)}, "
          f"secrets kept masked {summary['secrets_kept_masked']}, "
          f"same job {summary['same_job']}/{summary['judged']}, "
          f"gate {summary['gate_seconds_mean']} s against raw {summary['raw_seconds_mean']} s.")
    print(f"written to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
