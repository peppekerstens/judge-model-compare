#!/usr/bin/env bash
# Build the Codacus llama.cpp fork in a Podman container on legion-t5, and serve
# qwen3.5-4b with it on port 11436. No toolchain lands on the host.
#
# Usage: ./build-legion.sh [build|run|stop|test]
#   build  build the image (30 to 60 minutes, about 6 GB for the build stage)
#   run    start the server on port 11436 with the GPU
#   stop   stop and remove the container
#   test   one /v1/decision call, to prove the endpoint works
#
# Port 11436 belongs to llama-rerank.service, which is stopped. At a reboot that
# service takes the port back.
set -euo pipefail

. "$(cd "$(dirname "$0")" && pwd)/../../scripts-lib.sh"

need LEGION_SSH MODELS_DIR
LEGION=$LEGION_SSH
DIR=$(cd "$(dirname "$0")" && pwd)
NAME=decision-fork

case ${1:-build} in
build)
  rsync -a "$DIR/" "$LEGION:~/decision-fork/"
  ssh -n "$LEGION" "cd ~/decision-fork && podman build -t $NAME . 2>&1 | tail -20"
  ssh -n "$LEGION" "podman run --rm $NAME cat /opt/llama-decision/BUILD_COMMIT.txt"
  ;;
run)
  ssh -n "$LEGION" "podman rm -f $NAME >/dev/null 2>&1 || true; \
    podman run -d --name $NAME --device nvidia.com/gpu=all \
      -v $MODELS_DIR:/models:ro -p 11436:11436 $NAME >/dev/null"
  for _ in $(seq 1 90); do
    if ssh -n "$LEGION" "curl -sf http://127.0.0.1:11436/health" 2>/dev/null; then
      echo; echo "[fork] ready on port 11436"; exit 0
    fi
    sleep 2
  done
  echo "[fork] no answer. Read the log: ssh $LEGION podman logs $NAME" >&2; exit 1
  ;;
stop)
  ssh -n "$LEGION" "podman rm -f $NAME >/dev/null 2>&1 || true"; echo "[fork] stopped"
  ;;
test)
  ssh -n "$LEGION" "curl -s -m 120 http://127.0.0.1:11436/v1/decision \
    -H 'Content-Type: application/json' -d '{\"instructions\":\"Answer both questions about the request.\",\"schema\":{\"difficulty\":{\"type\":\"enum\",\"choices\":[\"simple\",\"medium\",\"hard\"],\"description\":\"How hard is the request?\"},\"sensitive\":{\"type\":\"boolean\",\"description\":\"Does the request contain personal data?\"}},\"contexts\":[\"What is the capital of France?\"]}'"
  echo
  ;;
*) echo "usage: $0 [build|run|stop|test]" >&2; exit 2 ;;
esac
