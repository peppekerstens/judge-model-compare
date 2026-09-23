#!/usr/bin/env bash
# Live network test of the Codacus llama.cpp fork on legion-t5.
# The static audit of the diff is in ../../docs/08-codacus-llama-fork.md. This script
# proves the runtime behavior, with the same method as the PrismML audit of 2026-09-21.
#
# Usage: ./security-test.sh
#
# 3 parts:
#   1. No network at all. The server must start and answer a decision call inside the
#      container. A hidden outbound call fails visibly.
#   2. Host network, with strace on every network call and every file open.
#   3. A packet capture on the host during a decision call.
# Part 2 and part 3 live in audit-privileged.sh, because they need root on legion-t5.
# The evidence lands in ~/decision-fork/audit/ on legion-t5.
#
# strace and tcpdump need root on legion-t5, because ptrace_scope is 1. The password
# comes from ~/.env, the one plain-text copy, with gopass as the source.
set -euo pipefail

. "$(cd "$(dirname "$0")" && pwd)/../../scripts-lib.sh"

need LEGION_SSH MODELS_DIR
LEGION=$LEGION_SSH
NAME=decision-fork-audit
OUT='~/decision-fork/audit'


# Part 2 and part 3 run as root on legion-t5, from audit-privileged.sh. That file gets
# copied there, so the password stays on stdin and never lands on a command line.

ssh -n "$LEGION" "mkdir -p $OUT"

echo "[1/3] no network, one decision call inside the container"
ssh -n "$LEGION" "podman rm -f $NAME >/dev/null 2>&1 || true
podman run -d --name $NAME --network none --device nvidia.com/gpu=all \
  -v $MODELS_DIR:/models:ro decision-fork >/dev/null
for i in \$(seq 1 120); do
  podman exec $NAME curl -sf http://127.0.0.1:11436/health >/dev/null 2>&1 && break
  sleep 2
done
podman exec $NAME curl -s -m 300 http://127.0.0.1:11436/v1/decision \
  -H 'Content-Type: application/json' \
  -d '{\"instructions\":\"Answer the question about the request.\",\"schema\":{\"difficulty\":{\"type\":\"enum\",\"choices\":[\"simple\",\"medium\",\"hard\"],\"description\":\"How hard is the request for a language model?\"}},\"contexts\":[\"What is the capital of France?\"]}' \
  | tee $OUT/no-network.json
echo
podman logs $NAME 2>&1 | tail -5 > $OUT/no-network.log
podman rm -f $NAME >/dev/null"

echo "[2/3] host network, with strace on every network call"
ssh -n "$LEGION" "podman rm -f $NAME >/dev/null 2>&1 || true
podman run -d --name $NAME --network host --device nvidia.com/gpu=all \
  -v $MODELS_DIR:/models:ro -e PORT=11437 decision-fork >/dev/null
for i in \$(seq 1 120); do
  curl -sf http://127.0.0.1:11437/health >/dev/null 2>&1 && break
  sleep 2
done
podman inspect $NAME --format '{{.State.Pid}}' > $OUT/pid.txt
cat $OUT/pid.txt"

scp -q "$(dirname "$0")/audit-privileged.sh" "$LEGION:/tmp/audit-privileged.sh"
printf '%s\n' "$HOMELAB_PEPPE_SUDO_PASSWORD" | ssh "$LEGION" "sudo -S -p '' bash /tmp/audit-privileged.sh /home/peppe/decision-fork/audit"

ssh -n "$LEGION" "podman rm -f $NAME >/dev/null 2>&1 || true"
echo "[done] the evidence is in $OUT on $LEGION"
