# Laya judge

Laya ([NandhaKishorM/laya](https://github.com/NandhaKishorM/laya)) as a fourth judge, next to the 3 Qwen judges. It runs in Podman on legion-t5. This folder holds the service, the 2 images and the deploy script.

Result of 2026-09-23: **Laya is not usable as a judge without a fine-tune.** It reads 4 of 24 bench cases right, against 23 of 24 for Qwen3.5-4B. The numbers are in `../results/README.md`.

## What it is

- Laya is an encoder model, not a language model. It answers typed questions (`choice`, `score`, `noul`) in one forward pass.
- Checkpoint: `convaiinnovations/laya-multilingual`, mmBERT-base, 322M parameters, 644 MB, 1024 tokens of context, Apache-2.0.
- `app.py` wraps it in the TypeSafe `/v1/systemone` shape. The judge bench and the router therefore need no change.

## Endpoints

| URL | What |
|---|---|
| `http://<LEGION_IP>:8082/v1/systemone` | The judge, CPU. The same request shape as `semif-judge` |
| `http://<LEGION_IP>:8082/health` | The model and the device |

The firewall on legion-t5 allows only 11434, 11435, 11436 and 8080. Port 8082 is therefore reachable on the host itself, or over an SSH tunnel:

```sh
ssh -f -N -L 18082:127.0.0.1:8082 legion
curl -s http://127.0.0.1:18082/health
```

Use `127.0.0.1`, not `localhost`. On legion-t5 the name `localhost` resolves to IPv6 first, and rootless Podman publishes on IPv4.

## Files

| File | What |
|---|---|
| `app.py` | The service. It loads one checkpoint with `laya.Agent` and answers `/v1/systemone` |
| `Containerfile` | The CPU image: python 3.13, torch CPU, laya 0.3.5. The checkpoint is baked in, so the container needs no internet |
| `Containerfile.gpu` | The same image with the CUDA 12.8 build of torch, for the legion GPU |
| `deploy-legion.sh` | It copies this folder to legion-t5, builds the image, and starts the container |

## Deploy or rebuild

```sh
./deploy-legion.sh cpu     # port 8082, CPU only
./deploy-legion.sh gpu     # port 8083, GPU, needs the NVIDIA container toolkit
```

The GPU variant needs 2 things on legion-t5, installed on 2026-09-23:
1. `nvidia-container-toolkit` from the NVIDIA repository (version 1.20.1).
2. A CDI spec: `sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml`.

The GPU is shared with the judge model. The 4B judge uses 3,568 MiB of 8,192 MiB, so about 4.6 GB stays free.

## Measure it

```sh
cd ..                                      # the poc folder
ssh -f -N -L 18082:127.0.0.1:8082 legion
python3 judge_bench.py --judge http://127.0.0.1:18082 --label laya-multilingual
python3 results_table.py > results/tables.md
```

## CPU against GPU (2026-09-23)

The GPU changes no answer. All 24 cases give the same result. Only the time differs.

| Point | CPU (port 8082) | GPU (port 8083) |
|---|---|---|
| Image | 1.97 GB `localhost/laya-judge` | 3.9 GB `localhost/laya-judge-gpu` |
| Torch | 2.14.0+cpu | CUDA 12.8 build |
| Median answer time | 0.48 s | **0.20 s** |
| Warm mean, both questions | 0.58 s | **0.18 s** |
| First call, with the model load | 19.2 s | 10.0 s |
| VRAM | none | 1,715 MiB |
| Host memory | 1,787 MB RSS | not measured |
| Both answers right | 4 of 24 | 4 of 24 |

Laya on the GPU is faster than every Qwen judge (0.20 s against 0.51 s for the 4B model). The quality stays the blocker.

## Limits

- The base checkpoint scores near random on typed decisions. The author writes that in the README: "Treat Laya as a fast base to specialise, not as a zero-shot decision engine."
- The context is 1024 tokens. A long hard-tier request is cut.
- The service loads one checkpoint. The Laya `Router`, which picks a checkpoint per language, is not used here.
