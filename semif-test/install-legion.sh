#!/usr/bin/env bash
# One-time setup on legion-t5 for the SemIf test. Run as user peppe with sudo rights.
#  1. The PrismML llama.cpp fork (CUDA 12.8 build) in /opt/llama.cpp-prism. Ternary Bonsai needs it.
#     Release prism-b10709-9a9394a passed the network audit of 2026-09-21
#     (ai-stack/docs/ternary-bonsai-2-27b.md). /opt/llama.cpp stays unchanged.
#  2. Qwen3-0.6B Q8_0 GGUF, the exact file that SemIf lists (manifests/models.json).
#  3. Qwen3.5-2B Q4_K_M GGUF from bartowski, the same maker and quant as the Qwen3.5-4B and 9B files.
# Each download is checked against its published sha256. A mismatch stops the script.
set -euo pipefail

TAG=prism-b10709-9a9394a
TARBALL=llama-$TAG-bin-linux-cuda-12.8-x64.tar.gz
TARBALL_SHA=8aec67eb023b251712c7e6490f367b5671bf587eced1436a9b85f4a90c3b7d3d

Q06_URL=https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/23749fefcc72300e3a2ad315e1317431b06b590a/Qwen3-0.6B-Q8_0.gguf
Q06_SHA=9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031
Q06_FILE=/opt/models/qwen3-0.6b-q8_0.gguf

Q2B_URL=https://huggingface.co/bartowski/Qwen_Qwen3.5-2B-GGUF/resolve/7d26695454df6de5fbcce2e58681e62dae06ce43/Qwen_Qwen3.5-2B-Q4_K_M.gguf
Q2B_SHA=57a1085840f497d764a7fc5d346922dbde961efb54cc792ea81d694fd846a1d8
Q2B_FILE=/opt/models/qwen3.5-2b.gguf

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

if [ ! -x /opt/llama.cpp-prism/llama-server ]; then
  curl -fL --retry 3 -o "$tmp/$TARBALL" \
    "https://github.com/PrismML-Eng/llama.cpp/releases/download/$TAG/$TARBALL"
  echo "$TARBALL_SHA  $tmp/$TARBALL" | sha256sum -c -
  mkdir "$tmp/x"
  tar -xzf "$tmp/$TARBALL" -C "$tmp/x"
  # The tarball has one top-level folder. Its content goes to /opt/llama.cpp-prism.
  src=$(find "$tmp/x" -name llama-server -type f -printf '%h\n' | head -1)
  sudo mkdir -p /opt/llama.cpp-prism
  sudo cp -a "$src"/. /opt/llama.cpp-prism/
  sudo chown -R peppe:peppe /opt/llama.cpp-prism
fi
# The prism tarball has no CUDA runtime. It uses the CUDA 12.8 runtime of the stock build (read only).
LD_LIBRARY_PATH=/opt/llama.cpp-prism:/opt/llama.cpp/cuda_v12 /opt/llama.cpp-prism/llama-server --version 2>&1 | tail -2

if [ ! -f "$Q06_FILE" ]; then
  curl -fL --retry 3 -o "$tmp/q06.gguf" "$Q06_URL"
  echo "$Q06_SHA  $tmp/q06.gguf" | sha256sum -c -
  mv "$tmp/q06.gguf" "$Q06_FILE"
fi
ls -l "$Q06_FILE"

if [ ! -f "$Q2B_FILE" ]; then
  curl -fL --retry 3 -o "$tmp/q2b.gguf" "$Q2B_URL"
  echo "$Q2B_SHA  $tmp/q2b.gguf" | sha256sum -c -
  mv "$tmp/q2b.gguf" "$Q2B_FILE"
fi
ls -l "$Q2B_FILE"
