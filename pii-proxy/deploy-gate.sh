#!/usr/bin/env bash
# Build the PII gate and run it on the proof of concept host, next to the router.
#
#   ./pii-proxy/deploy-gate.sh          build, copy and run
#   ./pii-proxy/deploy-gate.sh check    health and a mask test
#   ./pii-proxy/deploy-gate.sh stop     stop and remove the container
#
# The host uses Docker, and Docker reads only a file named Dockerfile. The
# build therefore names the file with -f.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=scripts-lib.sh
source ./scripts-lib.sh
load_env
need POC_SSH POC_IP POC_DIR PRESIDIO_ANALYZER_URL DECISION_FORK_URL LITELLM_URL

NAME=pii-gate
PORT=8086
SRC="$POC_DIR/pii-proxy"

case "${1:-deploy}" in
  check)
    curl -fsS --max-time 10 "http://${POC_IP}:${PORT}/healthz" && echo
    curl -fsS --max-time 30 -X POST "http://${POC_IP}:${PORT}/v1/mask" \
      -H 'Content-Type: application/json' \
      -d '{"text":"Jan de Vries lives at Kerkstraat 12 in Utrecht"}' && echo
    echo "log page: http://${POC_IP}:${PORT}/log"
    exit 0 ;;
  stop)
    ssh -n "$POC_SSH" "docker rm -f $NAME 2>/dev/null; true"
    echo "$NAME removed"; exit 0 ;;
esac

echo "step 1/4: copy the code"
ssh -n "$POC_SSH" "mkdir -p $SRC/gate"
scp -q pii-proxy/gate.py "$POC_SSH:$SRC/gate.py"
scp -q pii-proxy/gate/app.py pii-proxy/gate/Containerfile "$POC_SSH:$SRC/gate/"

echo "step 2/4: build the image"
ssh -n "$POC_SSH" "cd $SRC && docker build -f gate/Containerfile -t $NAME:latest ."

echo "step 3/4: start the container on port $PORT"
ssh -n "$POC_SSH" "docker rm -f $NAME 2>/dev/null; \
  docker run -d --name $NAME --restart unless-stopped -p $PORT:$PORT \
    -v ${NAME}-data:/data \
    -e PRESIDIO_ANALYZER_URL='$PRESIDIO_ANALYZER_URL' \
    -e DECISION_FORK_URL='$DECISION_FORK_URL' \
    -e UPSTREAM_URL='$LITELLM_URL' \
    -e UPSTREAM_KEY=\"\${LITELLM_KEY:-}\" \
    $NAME:latest"

echo "step 4/4: wait, then check"
for i in $(seq 1 30); do
  if curl -fsS --max-time 5 "http://${POC_IP}:${PORT}/healthz" >/dev/null 2>&1; then break; fi
  sleep 2
done
"$0" check
