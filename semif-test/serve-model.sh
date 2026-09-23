#!/usr/bin/env bash
# Start one test model in llama-server on legion-t5 (GPU).
# Run it on legion-t5 as user peppe. It stops an earlier server on the same port first.
# Port 11435 is the port of llama-embed.service. Stop that service before you use 11435.
#
# Usage: serve-model.sh GGUF_PATH ALIAS [LLAMA_DIR] [PORT]
#   LLAMA_DIR  default /opt/llama.cpp. Use /opt/llama.cpp-prism for Ternary Bonsai (PTQ1_0).
#   PORT       default 11435. Use another port to keep the LiteLLM embed-local port free.
set -euo pipefail

# This script runs ON the model host, so it reads no .env. The caller gives the paths.
GGUF=$1 ALIAS=$2 DIR=${3:-/opt/llama.cpp} PORT=${4:-11435}
WORK=$HOME/semif-test
mkdir -p "$WORK"

# Stop every llama-server on port 11435, also one without a PID file.
pkill -u "$USER" -f -- "llama-server .*--port $PORT( |$)" || true
for _ in $(seq 1 30); do
  pgrep -u "$USER" -f -- "llama-server .*--port $PORT( |$)" > /dev/null || break
  sleep 1
done

# --parallel 1: one request at a time, like the SemIf reference runs.
# --ctx-size 16384: the longest JevBench hard item is about 6k tokens plus the prompt.
# The prism build has no CUDA runtime. /opt/llama.cpp/cuda_v12 gives it (same CUDA 12.8). $DIR comes first.
LD_LIBRARY_PATH="$DIR:/opt/llama.cpp/cuda_v12" nohup "$DIR/llama-server" \
  --model "$GGUF" --alias "$ALIAS" --host 0.0.0.0 --port "$PORT" \
  --n-gpu-layers 99 --ctx-size 16384 --parallel 1 --flash-attn on \
  > "$WORK/server-$ALIAS.log" 2>&1 < /dev/null &
echo $! > "$WORK/server.pid"

for _ in $(seq 1 120); do
  if curl -sf http://127.0.0.1:$PORT/health > /dev/null; then
    # Make sure the server on the port is the new one, with the requested file.
    loaded=$(curl -s http://127.0.0.1:$PORT/props | python3 -c 'import sys,json; print(json.load(sys.stdin).get("model_path",""))')
    if [ "$loaded" != "$GGUF" ]; then
      echo "wrong model on port $PORT: $loaded (expected $GGUF)" >&2
      exit 1
    fi
    echo "ready: $ALIAS ($GGUF) with $DIR on port $PORT"
    exit 0
  fi
  sleep 2
done
echo "llama-server did not become ready. See $WORK/server-$ALIAS.log" >&2
exit 1
