#!/usr/bin/env bash
# Provision the hosts of the proof of concept. Every step is idempotent, and every step
# runs again without harm.
#
# Usage: ./provision-hosts.sh lxc110 | legion-gpu | check
#   lxc110      create LXC 110 jev-poc on pve2 and install Docker (about 10 minutes)
#   legion-gpu  install the NVIDIA container toolkit on legion-t5, for Podman with a GPU
#   check       report the state of both hosts
#
# The model hosts need no provisioning here. legion-t5 already runs llama.cpp, and
# semif-test/install-legion.sh installs the PrismML fork and the extra GGUF files.
set -euo pipefail

. "$(cd "$(dirname "$0")" && pwd)/../scripts-lib.sh"

need PVE_SSH LEGION_SSH POC_SSH POC_VMID POC_CIDR POC_GATEWAY POC_DNS PVE_TEMPLATE PVE_STORAGE
PVE=$PVE_SSH
LEGION=$LEGION_SSH
POC=$POC_SSH
VMID=$POC_VMID
IP=$POC_CIDR
GW=$POC_GATEWAY
DNS=$POC_DNS
TEMPLATE=$PVE_TEMPLATE

sudo_legion() {  # the password lives in ~/.env, the one plain-text copy. gopass is the source.
  set -a; . "$HOME/.env"; set +a
  : "${HOMELAB_PEPPE_SUDO_PASSWORD:?HOMELAB_PEPPE_SUDO_PASSWORD is missing from ~/.env}"
  printf '%s\n' "$HOMELAB_PEPPE_SUDO_PASSWORD" | ssh "$LEGION" "sudo -S -p '' bash -c \"$1\""
}

case ${1:-check} in
lxc110)
  if ssh -n "$PVE" "pct status $VMID" >/dev/null 2>&1; then
    echo "[lxc110] container $VMID exists"
  else
    echo "[lxc110] creating container $VMID"
    ssh -n "$PVE" "pct create $VMID $TEMPLATE --hostname jev-poc --cores 4 --memory 4096 \
      --swap 1024 --rootfs $PVE_STORAGE:20 --net0 name=eth0,bridge=vmbr0,ip=$IP,gw=$GW \
      --nameserver $DNS --features nesting=1,keyctl=1 --onboot 1 --unprivileged 1 --start 1"
    sleep 12
  fi
  key=$(cat "$HOME/.ssh/id_ed25519.pub" 2>/dev/null || cat "$HOME/.ssh/id_rsa.pub")
  ssh -n "$PVE" "pct exec $VMID -- bash -c 'mkdir -p /root/.ssh && chmod 700 /root/.ssh && \
    grep -qxF \"$key\" /root/.ssh/authorized_keys 2>/dev/null || echo \"$key\" >> /root/.ssh/authorized_keys'"
  echo "[lxc110] installing Docker"
  ssh -n -o StrictHostKeyChecking=accept-new "$POC" 'set -e
    command -v docker >/dev/null && { docker --version; exit 0; }
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl git rsync >/dev/null
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian trixie stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin >/dev/null
    docker --version && docker compose version'
  echo "[lxc110] ready. Copy poc/ and semif-test/remote_semif.py to /opt/jev-poc-src/ next."
  ;;
legion-gpu)
  if ssh -n "$LEGION" 'test -f /etc/cdi/nvidia.yaml' 2>/dev/null; then
    echo "[legion-gpu] the CDI spec exists"
  else
    echo "[legion-gpu] installing the NVIDIA container toolkit"
    sudo_legion "curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
      gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg && \
      curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
      sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
      > /etc/apt/sources.list.d/nvidia-container-toolkit.list"
    sudo_legion "apt-get update -qq -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/nvidia-container-toolkit.list \
      -o Dir::Etc::sourceparts=/dev/null; apt-get install -y -qq nvidia-container-toolkit"
    sudo_legion "nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml"
  fi
  ssh -n "$LEGION" 'nvidia-ctk --version | head -1; grep -c "name:" /etc/cdi/nvidia.yaml'
  echo "[legion-gpu] ready. A container reaches the GPU with: podman run --device nvidia.com/gpu=all"
  ;;
check)
  echo "== LXC 110 ($POC)"
  ssh -n "$POC" 'hostname; docker --version; docker ps --format "{{.Names}} {{.Status}}"' 2>&1 | head -8
  echo "== legion-t5 ($LEGION)"
  ssh -n "$LEGION" 'hostname; podman --version; test -f /etc/cdi/nvidia.yaml && echo "CDI spec present"; \
    podman ps --format "{{.Names}} {{.Status}}"; nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader' 2>&1 | head -10
  ;;
*) echo "usage: $0 lxc110|legion-gpu|check" >&2; exit 2 ;;
esac
