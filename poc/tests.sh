#!/usr/bin/env bash
# The test examples of the proof of concept.
# Part 1: 5 normal requests, one for each route.
# Part 2: 2 stream requests, one local and one to the cloud.
# Usage: ./tests.sh [ROUTER_URL]   default http://<POC_IP>:8081
set -euo pipefail

. "$(cd "$(dirname "$0")" && pwd)/../scripts-lib.sh"
need POC_IP
URL=${1:-http://$POC_IP:8081}

ask() {
  echo "== $1"
  curl -s -m 300 "$URL/v1/chat/completions" -H 'Content-Type: application/json' \
    -d "{\"messages\":[{\"role\":\"user\",\"content\":$2}]}" |
  python3 -c '
import sys, json
d = json.load(sys.stdin)
r = d.get("x_jev_router", {})
msg = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
print("   route:", r.get("chosen"), "| reason:", r.get("reason"),
      "| judge %.2f s" % (r.get("judge_seconds") or 0))
print("   answer:", (msg or json.dumps(d)[:200]).replace("\n", " ")[:140])'
}

ask "1 simple, expect qwen3.8-27b-nothink" '"What is the capital of France?"'
ask "2 medium, expect qwen3.8-27b-local" '"Write a bash one-liner that counts the lines of every .py file in a folder, and explain it."'
ask "3 hard, expect qwen3.7-max (cloud)" '"Design a fault-tolerant job queue for a 3-node cluster. Compare at-least-once and exactly-once delivery, and explain the trade-offs for retries, idempotency and back pressure."'
ask "4 sensitive and hard, expect qwen3.8-27b-local" '"Here is my mortgage file: loan 124, 84384.42 euro at 2.69 percent, owner Peppe Kerstens, IBAN NL91ABNA0417164300. Design the optimal repayment plan across the 3 loans and compare the tax effects."'
ask "5 sensitive and simple, expect qwen3.8-27b-local" '"My colleague Jan de Vries lives at Kerkstraat 12 in Utrecht. Write a one-line greeting for his birthday card."'

stream_ask() {
  echo "== $1"
  head=$(mktemp) body=$(mktemp) t0=$SECONDS
  # 900 s: a long cloud answer of 5,000 tokens or more needs more than 300 s.
  curl -s -N -m 900 -D "$head" "$URL/v1/chat/completions" -H 'Content-Type: application/json' \
    -d "{\"stream\":true,\"messages\":[{\"role\":\"user\",\"content\":$2}]}" > "$body"
  grep -i "^x-jev" "$head" | sed 's/^/   /'
  python3 - "$body" <<'PYEOF'
import json, sys
lines = [l for l in open(sys.argv[1]) if l.startswith("data: ")]
text = ""
for line in lines:
    payload = line[6:].strip()
    if payload == "[DONE]":
        continue
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        continue
    for choice in data.get("choices", []):
        text += (choice.get("delta") or {}).get("content") or ""
done = lines[-1].strip() == "data: [DONE]" if lines else False
print("   events:", len(lines), "| ends with [DONE]:", done)
print("   text:", text.replace("\n", " ")[:120])
PYEOF
  echo "   seconds: $((SECONDS - t0))"
  rm -f "$head" "$body"
}

stream_ask "6 stream, simple, expect qwen3.8-27b-nothink" '"What is the capital of France?"'
stream_ask "7 stream, hard, expect qwen3.7-max (cloud)" '"Design a fault-tolerant job queue for a 3-node cluster and compare the delivery guarantees."'

echo "== the decision log"
echo "   open $URL/ in a browser"
