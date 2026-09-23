#!/usr/bin/env bash
# Deploy the Laya judge to legion-t5 with Podman.
#
# Usage: ./deploy-legion.sh [cpu|gpu]
#   cpu  image laya-judge,     container laya-judge,     host port 8082 (the default)
#   gpu  image laya-judge-gpu, container laya-judge-gpu, host port 8083
#
# The GPU variant needs the NVIDIA container toolkit and a CDI spec on legion-t5:
#   sudo apt-get install -y nvidia-container-toolkit
#   sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
set -euo pipefail

. "$(cd "$(dirname "$0")" && pwd)/../../scripts-lib.sh"

MODE=${1:-cpu}
need LEGION_SSH
LEGION=$LEGION_SSH
DIR=$(cd "$(dirname "$0")" && pwd)

case $MODE in
  cpu) FILE=Containerfile;     IMAGE=laya-judge;     PORT=8082; EXTRA=""; DEVICE=cpu ;;
  gpu) FILE=Containerfile.gpu; IMAGE=laya-judge-gpu; PORT=8083; EXTRA="--device nvidia.com/gpu=all"; DEVICE=cuda ;;
  *) echo "usage: $0 [cpu|gpu]" >&2; exit 2 ;;
esac

echo "[deploy] copying the service to $LEGION"
rsync -a "$DIR/" "$LEGION:~/laya-judge/"

echo "[deploy] building $IMAGE (the first build downloads torch, which takes 5 to 20 minutes)"
ssh -n "$LEGION" "cd ~/laya-judge && podman build -q -f $FILE -t $IMAGE ."

echo "[deploy] starting the container on port $PORT"
ssh -n "$LEGION" "podman rm -f $IMAGE >/dev/null 2>&1 || true; \
  podman run -d --name $IMAGE $EXTRA -p $PORT:8082 -e LAYA_DEVICE=$DEVICE $IMAGE >/dev/null"

for _ in $(seq 1 60); do
  if ssh -n "$LEGION" "curl -sf http://127.0.0.1:$PORT/health" 2>/dev/null; then
    echo
    echo "[deploy] ready on port $PORT"
    exit 0
  fi
  sleep 2
done
echo "[deploy] the service did not answer. Read the log: ssh $LEGION podman logs $IMAGE" >&2
exit 1
