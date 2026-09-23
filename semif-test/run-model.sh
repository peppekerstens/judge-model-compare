#!/usr/bin/env bash
# Run both SemIf accuracy tests for one model that llama-server serves.
# Runs on the buildbox, from /srv/semif-test, inside the localhost/semif-remote image.
#
# Usage: EXPECT_GGUF=/opt/models/x.gguf run-model.sh LABEL HF_MODEL_ID HF_REVISION [SERVER_URL]
#   EXPECT_GGUF  required: the GGUF path that llama-server must have loaded. The run stops on a mismatch.
#   LABEL        short name for the run directory, for example qwen3.5-4b-q4km
#   HF_MODEL_ID  the Hugging Face model that matches the GGUF (the tokenizer comes from it)
#   HF_REVISION  pinned commit of that model
#   SERVER_URL   llama-server base URL (default http://<LEGION_IP>:11435)
set -euo pipefail

. "$(cd "$(dirname "$0")" && pwd)/../scripts-lib.sh"

LABEL=$1 MODEL=$2 REV=$3 need LEGION_IP
URL=${4:-http://$LEGION_IP:11435}
BASE=${BUILDBOX_DIR:-/srv/semif-test}
OUT=runs/$LABEL
cd "$BASE"
mkdir "$OUT"   # fails on purpose if the run directory exists: never overwrite a result

# The 3 public JevBench splits as one task file (72 standard + 48 easy + 111 hard = 231).
if [ ! -f jevbench-public231.jsonl ]; then
  cat jevbench/datasets/public/original.jsonl jevbench/datasets/public/easy.jsonl \
      jevbench/datasets/public/hard.jsonl > jevbench-public231.jsonl
fi

run() {
  podman run --rm --network host -v "$BASE:$BASE" \
    -e SEMIF_LLAMA_URL="$URL" -e SEMIF_N_PROBS="${SEMIF_N_PROBS:-200}" \
    -e SEMIF_MAX_TOKENS="${SEMIF_MAX_TOKENS:-16384}" -e HF_TOKEN="${HF_TOKEN:-}" \
    localhost/semif-remote "$@" </dev/null
}

run python -c 'import json, remote_semif; print(json.dumps(remote_semif.server_props()))' > "$OUT/server.json"
echo "[run] $LABEL on $(cat "$OUT/server.json")"
loaded=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["model_path"])' "$OUT/server.json")
if [ "$loaded" != "${EXPECT_GGUF:?set EXPECT_GGUF to the GGUF path on the server}" ]; then
  echo "[run] wrong model on the server: $loaded (expected $EXPECT_GGUF)" >&2
  mv "$OUT" "runs/invalid/$LABEL-wrong-model-$(date +%s)"
  exit 1
fi

# Test 1: SemIf authored144, scored with the SemIf evaluate.py.
run python remote_semif.py score --model "$MODEL" --revision "$REV" \
  --input SemIf/benchmarks/data/authored144.jsonl --output "$OUT/authored144.predictions.jsonl" \
  | tee "$OUT/authored144.log"
run python SemIf/benchmarks/evaluate.py --gold SemIf/benchmarks/data/authored144.jsonl \
  --predictions "$OUT/authored144.predictions.jsonl" --output "$OUT/authored144.eval.json" \
  | tee -a "$OUT/authored144.log"

# Test 2: JevBench public items through the JevBench harness (semif_direct adapter, remote forward pass).
run python remote_semif.py jevbench -- run --tasks jevbench-public231.jsonl \
  --adapter semif_direct --endpoint "$MODEL" --revision "$REV" \
  --price-in-per-m 0 --price-out-per-m 0 --reserve-usd 0 --cost-basis self_hosted_gpu \
  --results "$OUT/jevbench.results.jsonl" --raw-dir "$OUT/jevbench-raw" \
  --ledger "$OUT/jevbench.ledger.jsonl" --run-label "$LABEL" \
  | tee "$OUT/jevbench.log"
run python -m jevbench.cli summarize --tasks jevbench-public231.jsonl \
  --results "$OUT/jevbench.results.jsonl" --public-export "$OUT/jevbench.summary.json" \
  | tee -a "$OUT/jevbench.log"

echo "[run] done: $OUT"
