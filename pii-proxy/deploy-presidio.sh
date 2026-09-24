#!/usr/bin/env bash
# Deploy the 2 Microsoft Presidio containers on the LiteLLM host.
#
#   ./pii-proxy/deploy-presidio.sh          deploy and check
#   ./pii-proxy/deploy-presidio.sh check    check only
#   ./pii-proxy/deploy-presidio.sh stop     stop and remove both containers
#
# The analyzer finds the spans. The anonymizer replaces them. Both are local,
# and neither makes an outbound call after the image pull.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=scripts-lib.sh
source ./scripts-lib.sh
load_env
need LITELLM_SSH
need LITELLM_HOST_IP

ANALYZER_IMAGE=mcr.microsoft.com/presidio-analyzer:latest
ANONYMIZER_IMAGE=mcr.microsoft.com/presidio-anonymizer:latest
ACTION="${1:-deploy}"

check() {
  echo "--- containers ---"
  ssh -n "$LITELLM_SSH" 'docker ps --filter name=presidio --format "{{.Names}}\t{{.Status}}\t{{.Ports}}"'
  echo "--- analyzer health ---"
  curl -fsS --max-time 10 "http://${LITELLM_HOST_IP}:5002/health" && echo
  echo "--- anonymizer health ---"
  curl -fsS --max-time 10 "http://${LITELLM_HOST_IP}:5001/health" && echo
  echo "--- one analyze call ---"
  curl -fsS --max-time 30 -X POST "http://${LITELLM_HOST_IP}:5002/analyze" \
    -H 'Content-Type: application/json' \
    -d '{"text":"My name is Jan de Vries and my number is 06-12345678","language":"en"}' | head -c 400
  echo
}

case "$ACTION" in
  check) check; exit 0 ;;
  stop)
    ssh -n "$LITELLM_SSH" 'docker rm -f presidio-analyzer presidio-anonymizer 2>/dev/null; true'
    echo "both containers removed"
    exit 0 ;;
esac

# The analyzer holds a spaCy model in memory. 4 GB is not enough next to the
# LiteLLM stack, so the LXC needs 6 GB. Raise it on the Proxmox node first.
echo "step 1/4: pull the images"
ssh -n "$LITELLM_SSH" "docker pull $ANALYZER_IMAGE && docker pull $ANONYMIZER_IMAGE"

echo "step 2/4: start the anonymizer on port 5001"
ssh -n "$LITELLM_SSH" "docker rm -f presidio-anonymizer 2>/dev/null; \
  docker run -d --name presidio-anonymizer --restart unless-stopped \
    -p 5001:3000 $ANONYMIZER_IMAGE"

echo "step 3/4: start the analyzer on port 5002"
ssh -n "$LITELLM_SSH" "docker rm -f presidio-analyzer 2>/dev/null; \
  docker run -d --name presidio-analyzer --restart unless-stopped \
    -p 5002:3000 $ANALYZER_IMAGE"

echo "step 4/4: wait for the analyzer, then check"
for i in $(seq 1 60); do
  if curl -fsS --max-time 5 "http://${LITELLM_HOST_IP}:5002/health" >/dev/null 2>&1; then break; fi
  sleep 5
done
check
