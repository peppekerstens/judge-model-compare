#!/usr/bin/env bash
# Switch the judge model. It serves the GGUF on legion-t5, and it points the
# judge container at the matching tokenizer. The image holds the tokenizer of
# the 2B, the 4B and the 9B model, so no rebuild is needed.
#
# Usage: ./switch_judge.sh 2b|4b|9b
set -euo pipefail

. "$(cd "$(dirname "$0")" && pwd)/../scripts-lib.sh"

case ${1:-} in
  2b) GGUF=$MODELS_DIR/qwen3.5-2b.gguf;          MODEL=Qwen/Qwen3.5-2B; REV=15852e8c16360a2fea060d615a32b45270f8a8fc ;;
  4b) GGUF=$MODELS_DIR/qwen3.5-4b.gguf;          MODEL=Qwen/Qwen3.5-4B; REV=851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a ;;
  9b) GGUF=$MODELS_DIR/qwen3.5-9b-standard.gguf; MODEL=Qwen/Qwen3.5-9B; REV=c202236235762e1c871ad0ccb60c8ee5ba337b9a ;;
  *) echo "usage: $0 2b|4b|9b" >&2; exit 2 ;;
esac

need LEGION_SSH POC_SSH POC_DIR MODELS_DIR LLAMA_DIR
LEGION=$LEGION_SSH
POC_HOST=$POC_SSH
POC_COMPOSE_DIR=$POC_DIR/poc

echo "[switch] serving $GGUF on $LEGION port 11434"
ssh -n "$LEGION" "bash ~/semif-test/serve-model.sh $GGUF judge-$1 $LLAMA_DIR 11434"

echo "[switch] pointing the judge container at $MODEL"
ssh -n "$POC_HOST" "cd $POC_COMPOSE_DIR && \
  sed -i 's#^JUDGE_MODEL=.*#JUDGE_MODEL=$MODEL#; s#^JUDGE_REVISION=.*#JUDGE_REVISION=$REV#' .env && \
  grep -q '^JUDGE_MODEL=' .env || printf 'JUDGE_MODEL=%s\nJUDGE_REVISION=%s\n' '$MODEL' '$REV' >> .env && \
  docker compose up -d semif-judge >/dev/null 2>&1"

sleep 5
ssh -n "$POC_HOST" "curl -s localhost:8080/health"
echo
