#!/usr/bin/env bash
# Free the GPU of legion-t5 for the test, and give it back at the end.
#
#   ./pii-proxy/gpu-window.sh open     stop the embed and rerank tiers, start the fork
#   ./pii-proxy/gpu-window.sh close    stop the fork, start both tiers again
#   ./pii-proxy/gpu-window.sh state    show what runs now
#
# LiteLLM keeps working during the window. It falls back to the gaming-b650 CPU
# tiers. The 2 units are enabled, so a reboot starts them again by itself.
#
# The 2 units are system units, so the stop and the start need sudo. The script
# reads the password from ~/.env through scripts-lib.sh. It never writes it to a
# file, and it never puts it on a command line.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=scripts-lib.sh
source ./scripts-lib.sh
load_env
need LEGION_SSH LEGION_IP HOMELAB_PEPPE_SUDO_PASSWORD

# It pipes the password into the standard input of sudo -S on the far side.
remote_sudo() {
  printf '%s\n' "$HOMELAB_PEPPE_SUDO_PASSWORD" |
    ssh "$LEGION_SSH" "sudo -S -p '' $*"
}

state() {
  ssh -n "$LEGION_SSH" 'echo "--- units ---"; systemctl is-active llama-embed llama-rerank
echo "--- fork ---"; podman ps --filter name=decision-fork --format "{{.Names}} {{.Status}}"
echo "--- gpu ---"; nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader'
}

case "${1:-state}" in
  open)
    echo "step 1/3: stop the embed and rerank tiers"
    remote_sudo systemctl stop llama-embed llama-rerank
    echo "step 2/3: start the fork on port 11436"
    ssh -n "$LEGION_SSH" 'podman start decision-fork'
    echo "step 3/3: wait for the health check"
    for i in $(seq 1 60); do
      if curl -fsS --max-time 5 "http://${LEGION_IP}:11436/health" >/dev/null 2>&1; then
        echo "fork ready on ${LEGION_IP}:11436"; state; exit 0
      fi
      sleep 5
    done
    echo "the fork did not answer in 300 seconds" >&2; state; exit 1 ;;
  close)
    echo "step 1/2: stop the fork"
    ssh -n "$LEGION_SSH" 'podman stop decision-fork || true'
    echo "step 2/2: start the embed and rerank tiers again"
    remote_sudo systemctl start llama-embed llama-rerank
    state ;;
  state) state ;;
  *) echo "use open, close or state" >&2; exit 1 ;;
esac
