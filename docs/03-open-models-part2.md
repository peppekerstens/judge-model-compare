# Open Jev-style models, part 2

Research date: 2026-09-22. All facts come from the source URL next to them.
"not verified" means that no source confirms the fact, or that nobody ran it on our hosts.
Nothing in this file has been tested on gaming-b650 or legion-t5.

Context source: Sam Witteveen, "Open Jev Models Are Here!!", published 2026-09-20
(https://www.youtube.com/watch?v=53wDOI_7x8I, description read through the YouTube page).
Benchmark source: JevBench v1.3.0, scored 2026-09-21, 534 decisions per system
(https://benchmarkheaven.com/jev-models). The JevBench Score is a geometric mean of
Intelligence, Calibration, Speed and Cost. Jev 1.13.0 scores 74.4.

Host facts used below (from the task brief):

- gaming-b650: Radeon AI PRO R9700, 32 GB VRAM, Vulkan/ROCm, no CUDA. A 27B chat model uses about 26-30 GB VRAM.
- legion-t5: RTX 3060 Ti, 8 GB VRAM, CUDA. 14 GB RAM, nearly full. llama.cpp runs embed + rerank.

## Summary table

| Model | Base, params | Weights | License | JevBench v1.3.0 | Runtime | gaming-b650 | legion-t5 |
|---|---|---|---|---|---|---|---|
| DiffusionGemma via vLLM PR #57250 | google/diffusiongemma-26B-A4B-it, 25.2B MoE, 4B active | BF16 ~51.6 GB, NVFP4 18.8 GB, FP8 27.2 GB, GGUF Q4_K_M 16.8 GB to BF16 50.5 GB | Apache-2.0 | PR itself: not benchmarked. Rebuilds on the same weights: djev 73.0, OpenJev (razorback16) 66.4 | vLLM with an open (unmerged) PR, CUDA | No, in practice. See blockers | No. Model does not fit |
| NanoJev | Qwen3-0.6B + decision heads | best.safetensors 2.39 GB (FP32) | MIT (code). HF card: no license field | Not run ("different schema") | Custom PyTorch, CUDA-only check | Not verified. Needs ROCm PyTorch | Yes, probably. Custom code |
| Laya | ModernBERT-large 421M / mmBERT-base 322M | 842.6 MB / 643.8 MB safetensors | Apache-2.0 | 54.4 (rank 33) | `pip install laya` (PyTorch + transformers), CPU or GPU | Yes, on CPU. GPU needs ROCm PyTorch | Yes, on CPU or CUDA |
| OpenSourceJev | No own weights. Stock Qwen3-1.7B Q8_0 or Qwen3.5-4B Q4_K_M GGUF | 1.83 GB / 2.74 GB (upstream GGUF) | MIT | Not listed | Windows-only, ctypes on llama.dll | No, as shipped. Method is portable | No, as shipped. Method is portable |

## Blockers, short

- DiffusionGemma: vLLM PR #57250 is open, not merged. The tested path is NVIDIA (DGX Spark). NVFP4 needs an NVIDIA GPU. BF16 does not fit in 32 GB. llama.cpp support is only in an open PR (#24423), with `llama-diffusion-cli` only, no `llama-server`, and no seeded-canvas logprob read. The 26-30 GB chat model already uses the R9700.
- NanoJev: the code raises an error when no CUDA device exists. The model is trained on four games (Maze, Snake, two ViZDoom tasks), not general classification.
- Laya: base checkpoints are near chance zero-shot on typed decisions (author claim). Fine-tuning is the intended use. No OpenAI-compatible server in the package.
- OpenSourceJev: Windows only. It loads `llama.dll` through ctypes. The README says Linux is not supported.

---

## 1. DiffusionGemma (vLLM PR #57250)

### What it is

- The PR adds seeded-canvas, one-step, read-only requests to vLLM for DiffusionGemma. A client reads logprobs at fixed canvas slots and computes entropy as a confidence value. Source: https://github.com/vllm-project/vllm/pull/57250
- The PR includes a prototype interposer server with a `/v1/systemone` endpoint (`examples/features/structured_diffusion/structured_server.py`). It does not add a standard vLLM endpoint. Source: same PR.
- Each answer option must be a single token. The client maps multi-token labels to single tokens. Source: same PR.
- Supported question types: yes/no ("noul"), scale, multiple choice. The PR also shows image questions through the vision tower. Source: same PR.
- PR state on 2026-09-22: open, not merged. Created 2026-09-16 by mmastrac. 13 files, +2,760 lines. Source: `gh api repos/vllm-project/vllm/pulls/57250`.

### Weights the PR uses

- Test command: `vllm serve nvidia/diffusiongemma-26B-A4B-it-NVFP4 --diffusion-config '{"canvas_length": 32}' ...`. Source: PR #57250.
- Base: google/diffusiongemma-26B-A4B-it. 25.2B total parameters, MoE with 8 of 128 experts active ("A4B"). Block-diffusion encoder-decoder, multimodal input (text, image, video). Source: https://huggingface.co/unsloth/diffusiongemma-26B-A4B-it-GGUF (copy of Google card).
- License: Apache-2.0. Source: https://huggingface.co/api/models/google/diffusiongemma-26B-A4B-it

| Repo | Files | Size | Source |
|---|---|---|---|
| google/diffusiongemma-26B-A4B-it | 11 BF16 safetensors shards | ~51.6 GB | https://huggingface.co/api/models/google/diffusiongemma-26B-A4B-it/tree/main |
| nvidia/diffusiongemma-26B-A4B-it-NVFP4 | NVFP4 safetensors (ModelOpt) | 18.8 GB | https://huggingface.co/api/models/nvidia/diffusiongemma-26B-A4B-it-NVFP4 |
| RedHatAI/diffusiongemma-26B-A4B-it-FP8-dynamic | FP8 safetensors | 27.2 GB | https://huggingface.co/api/models/RedHatAI/diffusiongemma-26B-A4B-it-FP8-dynamic |
| unsloth/diffusiongemma-26B-A4B-it-GGUF | Q4_K_M 16.81, Q5_K_M 19.15, Q6_K 22.65, Q8_0 26.88, BF16 50.54 GB | see left | https://huggingface.co/api/models/unsloth/diffusiongemma-26B-A4B-it-GGUF/tree/main |

Many more quants and MLX builds exist (search `diffusiongemma` on https://huggingface.co/api/models).

### Quality

- PR author claims (DGX Spark, not independent): programming language 10/10, human language 9/10, unit comparison 10/12. 1-way 8.7 req/s at 0.12 s. 32-way 54.0 req/s at 0.58 s. Source: PR #57250.
- JevBench v1.3.0 did not test the PR itself. Two rebuilds on the same Google weights were tested. Source: https://benchmarkheaven.com/jev-models
  - djev (Maisa, hosted API): 73.0, rank 3. Tiers: easy 100%, standard 97.9%, judge 93.2%, hard 69.5%. p50 0.24 s. The djev-dev runtime adds no weights and uses PR #57250 (https://github.com/Davipar/djev-dev).
  - OpenJev (razorback16, NVFP4 on RunPod GPU): 66.4, rank 11. Hard tier 65.5%. p50 0.24 s raw.

### How to run

- vLLM: needs the PR branch. djev-dev says "stock vLLM alone does not provide all the required structured-read and image fixes" and recommends one NVIDIA B200, CUDA 13. Source: https://github.com/Davipar/djev-dev
- razorback16/openjev: NVIDIA GPU with 24 GB or more for NVFP4, tested on RTX PRO 6000 Blackwell (sm_120). Also runs on Apple silicon through MLX (about 16 GB). Source: https://github.com/razorback16/openjev
- llama.cpp: only in open PR ggml-org/llama.cpp#24423 (open on 2026-09-22). Only `llama-diffusion-cli` works. "The standard `llama-cli` / `llama-server` cannot generate from it yet." Source: https://huggingface.co/unsloth/diffusiongemma-26B-A4B-it-GGUF and `gh api repos/ggml-org/llama.cpp/pulls/24423`.
- OpenAI-compatible server: yes through vLLM (`/v1/chat/completions` with `vllm_xargs`). The `/v1/systemone` part is a separate example server. Source: PR #57250.

### Resource needs

- VRAM: NVFP4 18.8 GB weights plus KV cache. FP8 27.2 GB. BF16 ~51.6 GB. GGUF Q4_K_M 16.8 GB ("fits a single 24 GB GPU"). Sources: tables above.
- CPU-only: the llama.cpp PR allows `-ngl 0`, but only for chat generation. It does not provide the seeded one-step logprob read. The Jev-style read on CPU: not verified.

### Repo activity

- PR #57250: open, split into prerequisite PRs #57414, #57416, #57417, #57462, #57589. Source: PR #57250.

### Fit

- gaming-b650: No, in practice.
  - NVFP4 is an NVIDIA format (ModelOpt). R9700 support: not verified, and unlikely.
  - vLLM on ROCm with RDNA4 (R9700) plus this PR: not verified.
  - The GGUF route (Vulkan build of llama.cpp PR #24423) gives chat only, no seeded canvas read. The PR build instructions show CUDA only. A Vulkan build of that branch: not verified.
  - VRAM: Q4_K_M 16.8 GB does not fit next to the 26-30 GB chat model. It fits only if the chat model is unloaded.
- legion-t5: No. The smallest weight file (Q4_K_M 16.8 GB) is larger than 8 GB VRAM and larger than the free RAM.

## 2. NanoJev

### What it is

- "A 0.6B parallel decision model: states and questions in, complete probability distributions out." Choice over 2-255 candidates, Boolean, ordered Score. No output-token decoding. Source: https://github.com/TianyuCodings/NanoJev
- Base: Qwen/Qwen3-0.6B plus decision heads (set attention + softmax for Choice, sigmoid for Boolean). Source: https://huggingface.co/C-Tianyu/NanoJev
- Training data: 18,760 decision questions per variant, from Maze, Snake, ViZDoom Basic, ViZDoom Predict Position. The model is a game policy, not a general text classifier. Source: GitHub README.

### Weights

- HF repo C-Tianyu/NanoJev, tag `unified-games-v1`. Root `best.safetensors` 2,385 MB. The repo also holds `stage1/`, `training_initialization/` and seven `variants/*` checkpoints, each 2,385 MB. No GGUF. No quantized files. Source: https://huggingface.co/api/models/C-Tianyu/NanoJev/tree/main?recursive=true
- 2,385 MB for 0.6B parameters means FP32 storage. The loader keeps parameters in FP32 and uses BF16 autocast. Source: `scripts/predict_toy_decisions.py` line 228, 257.
- License: code MIT (https://github.com/TianyuCodings/NanoJev, `LICENSE`). The HF model card has no license field (https://huggingface.co/api/models/C-Tianyu/NanoJev). Weight license: not verified.

### Quality

- Own claims, 274-case test set: NanoJev Maze 4/10, Snake 8/8, Basic 128/128, Predict Position 27/128. Jev: 7/10, 8/8, 56/128, 11/128. Source: GitHub README.
- JevBench v1.3.0: not run. Reason given: "Public weights exist, but the server exposes a different schema (including boolean rather than Noul) and lacks the full structured/null contract." Source: https://benchmarkheaven.com/jev-models

### How to run

- Custom code only: `DecisionPredictor` from `scripts/predict_toy_decisions.py`, served by `scripts/serve_decisions.py` on `POST /api/evaluate`. Source: GitHub README.
- The code raises an error when the device is not CUDA: "此原型推理入口需要可用CUDA设备；本命令未启用CPU或远程回退" (this prototype needs a CUDA device, no CPU fallback). It also needs BF16 support. Source: `scripts/predict_toy_decisions.py` lines 200-204.
- Tested stack: Python 3.14.4, torch 2.14.0, transformers 5.17.0, A100 80GB. Source: `requirements-toy.txt`.
- No vLLM, no llama.cpp, no OpenAI-compatible server, no `/v1/systemone`.

### Resource needs

- VRAM: about 2.4 GB for FP32 weights plus activations (estimate from file size, not verified).
- CPU-only: blocked by the code check. A patch could remove it. Not verified.

### Repo activity

- 1,963 stars, 209 forks. Created 2026-09-17. Last push 2026-09-21. Source: `gh api repos/TianyuCodings/NanoJev`.

### Fit

- gaming-b650: Not verified. ROCm PyTorch reports the GPU as a `cuda` device, so the check may pass. BF16 on RDNA4 under ROCm: not verified. A PyTorch ROCm install is a new stack on this host.
- legion-t5: Yes, probably. RTX 3060 Ti is Ampere with BF16. About 2.4 GB VRAM next to the embed + rerank models: free VRAM not verified. RAM is nearly full, and a PyTorch process adds RAM.
- Use-case blocker on both: the model knows four games only. It is a demo, not a general classifier.

## 3. Laya

### What it is

- "Multilingual, non-autoregressive System 1 decision engine." Typed questions `choice`, `score`, `noul` over a text or JSON state, in one forward pass. A `Router` picks the checkpoint by script and language. Source: https://github.com/NandhaKishorM/laya
- Encoder models, not LLMs. Source: GitHub README table.

| Checkpoint | Encoder | Params | Context | File | Source |
|---|---|---|---|---|---|
| convaiinnovations/laya | ModernBERT-large | 421M | 512 | model.safetensors 842.6 MB | https://huggingface.co/api/models/convaiinnovations/laya/tree/main |
| convaiinnovations/laya-multilingual | mmBERT-base | 322M | 1024 | model.safetensors 643.8 MB | https://huggingface.co/api/models/convaiinnovations/laya-multilingual/tree/main |
| convaiinnovations/laya-typed-decisions | ModernBERT-large | 421M | 1024 | model.safetensors 842.6 MB | https://huggingface.co/api/models/convaiinnovations/laya-typed-decisions/tree/main |

- The `laya` repo also holds `multilingual/` and `typed-decisions/` subfolders with the same files. No GGUF, no quants. Source: HF tree listing.
- License: Apache-2.0 (code and HF cards). Sources: `gh api repos/NandhaKishorM/laya`, HF API `cardData.license`.

### Quality

- Own claims (T4 GPU): MASSIVE English 0.783, XNLI English 0.860. 45 of 51 languages usable with the router. Latency 32.8 ms per question on T4, 193-464 ms on CPU. Source: GitHub README.
- Own claim vs Jev: typed-decisions 0.766 vs 0.727, but only with the checkpoint fine-tuned on that benchmark's training split. Banking77 0.425 vs Jev 0.870. Source: GitHub README.
- Own "honest limits": base checkpoints score 0.362 and 0.352 zero-shot on typed decisions, against 0.318 random. "Treat Laya as a fast base to specialise, not as a zero-shot decision engine." `score` is the weakest primitive (SST-5 0.372). Source: GitHub README.
- JevBench v1.3.0: 54.4, rank 33. Intelligence 45.8, Calibration 62.5, Speed 71.1, Cost 86.2. Tiers: easy 94.4%, standard 72.9%, judge 69.2%, hard 34.1%. p50 0.79 s raw on the benchmark's CPU. English checkpoint, 512-token budget, long hard-tier states cut. Source: https://benchmarkheaven.com/jev-models

### How to run

- `pip install laya`. Python 3.10 or newer. Dependencies: torch, transformers, safetensors, huggingface_hub, numpy. Source: `pyproject.toml`.
- Python API only (`laya.load`, `Router`, `predict`, `predict_shortlist`). No server in the package. Source: GitHub README.
- featherless-ai/simple-jev can serve the Laya typed-decisions checkpoint behind its own HTTP server (`/v1/classifier`). Source: https://github.com/featherless-ai/simple-jev
- Fine-tuning notebook for 2x T4 (about 4-5 hours for 4 epochs over ~30k questions). Source: GitHub README.
- No vLLM, no llama.cpp. OpenAI-compatible server: no.

### Resource needs

- RAM: about 0.9 GB for weights, plus PyTorch. Exact RAM: not verified.
- CPU-only: yes. JevBench ran it on CPU. Source: benchmarkheaven.com.

### Repo activity

- 15,205 stars, 1,248 forks. Created 2026-09-18. Last push 2026-09-21 (release 0.3.5). Source: `gh api repos/NandhaKishorM/laya`.

### Fit

- gaming-b650: Yes, on CPU (Ryzen 7 7800X3D). GPU needs ROCm PyTorch: not verified. No VRAM conflict on CPU.
- legion-t5: Yes, on CPU or CUDA. The weights are small. RAM is the risk: PyTorch plus the model can take 1.5-2 GB (estimate, not verified), and RAM is nearly full.
- Quality blocker: weak zero-shot. It needs a fine-tune on our own decisions to be useful.

## 4. OpenSourceJev (sabeel111)

### What it is

- A FastAPI server that reads next-token logits from a stock GGUF model and does a softmax over the candidate tokens. Primitives: `noul`, `choice`, `score`, `text`. Source: https://github.com/sabeel111/OpenSourceJev
- No own weights. No Hugging Face repo from sabeel111 (the HF API returns an empty list for `author=sabeel111` and for search `OpenSourceJev`). The repo has an upload script and a draft model card (`docs/HUGGINGFACE_MODEL_CARD.md`). Source: HF API, repo tree.
- Profiles: `fast` = Qwen3-1.7B-Q8_0.gguf, `accuracy` = Qwen3.5-4B-Q4_K_M.gguf. Source: GitHub README.
- Upstream GGUF sizes: Qwen/Qwen3-1.7B-GGUF Q8_0 1.83 GB. unsloth/Qwen3.5-4B-GGUF Q4_K_M 2.74 GB. Sources: https://huggingface.co/api/models/Qwen/Qwen3-1.7B-GGUF/tree/main, https://huggingface.co/api/models/unsloth/Qwen3.5-4B-GGUF/tree/main
- Calibration: temperature scaling fitted on BoolQ. T = 9.4705 for 1.7B, T = 1.2364 for 4B. Source: GitHub README.
- License: MIT. Source: `gh api repos/sabeel111/OpenSourceJev`.

### Quality

- Own claims: "JevBench Original" 69.44% (fast) and 93.06% (accuracy), Easy 95.83% / 100%, Hard 39.64% / 59.46%. p50 ~312 ms / ~436 ms on an RTX 3050 Laptop 4 GB. Source: GitHub README.
- Which "JevBench" these files are (`original.jsonl`, `easy.jsonl`, `hard.jsonl`): not verified. They are not the Benchmark Heaven v1.3.0 numbers.
- JevBench v1.3.0: not listed. Source: https://benchmarkheaven.com/jev-models (no match for "OpenSourceJev" or "sabeel").

### How to run

- Windows 10/11 only. "Linux is currently NOT supported." It loads `runtime/llama.cpp/bin/llama.dll` through Python ctypes and reads `llama_get_logits_ith`. Source: README, `app/llama_ctypes.py`.
- Setup script `install_native_cuda.ps1` fetches CUDA 12.4 DLLs. CPU inference "is also supported". Source: README.
- Second mode: calls Ollama at `http://127.0.0.1:11434` and parses JSON output (not the logit method). Source: `app/engine.py` lines 154, 266-279.
- Endpoints: `POST /v1/systemone` (TypeSafe style), `POST /api/run`, `GET /v1/models`. No `/v1/chat/completions`. Source: `app/main.py`.

### Resource needs

- ~2.2 GB VRAM (fast), ~3.1 GB VRAM (accuracy). 8 GB+ RAM. Source: README.

### Repo activity

- 27 stars, 8 forks. Created 2026-09-19. Last push 2026-09-22 (UI and branding commits). Source: `gh api repos/sabeel111/OpenSourceJev`.

### Fit

- gaming-b650: No, as shipped (Windows DLL loader). The method itself (candidate-token logits from a GGUF) fits llama.cpp with Vulkan. A port needs the loader changed to `libllama.so`. Not verified.
- legion-t5: No, as shipped. With a port, Qwen3-1.7B Q8_0 (1.83 GB) or Qwen3.5-4B Q4_K_M (2.74 GB) may fit next to embed + rerank. Free VRAM: not verified.
- Note: the same method also works through `llama-server` logprobs on a model that already runs. That path is not part of this repo.

## 5. Extra open Jev-style models (released 2026-09-18 or later)

Not in the task list and not SemIf, Bespoke-Nimble-9B, Mapika/decider, AlexWortega/openjev.

1. **Winnow-12B** (EldanRing, HF created 2026-09-20). Gemma-4-12B-it fine-tune. GGUF Q8_0 12.67 GB, BF16 23.83 GB, Apache-2.0. JevBench 71.2 (rank 4, Q8). Own server is patched llama.cpp with `/v1/systemone` and `/v1/chat/completions`, CUDA and Metal only. Sources: https://huggingface.co/EldanRing/Winnow-12B, https://github.com/EldanRing/winnow-inference, benchmarkheaven.com. Most interesting for gaming-b650 if the patches build with Vulkan (not verified).
2. **razorback16/openjev** (created 2026-09-18, 305 stars, Apache-2.0). `/v1/systemone` server on DiffusionGemma NVFP4 through vLLM (NVIDIA 24 GB+) or MLX. JevBench 66.4. Source: https://github.com/razorback16/openjev
3. **Davipar/djev-dev** (created 2026-09-19, 109 stars, Apache-2.0). Typed-decision layer on DiffusionGemma BF16 + patched vLLM (PR #57250), reference hardware one B200. Hosted djev scores 73.0. Source: https://github.com/Davipar/djev-dev
4. **featherless-ai/simple-jev** (created 2026-09-18, 475 stars, Apache-2.0). Turns any HF model into a classifier endpoint by reading next-token logits. Transformers server, CPU, CUDA or ROCm PyTorch. SimpleJev Qwen3.8-27B scores 66.3 on JevBench. Source: https://github.com/featherless-ai/simple-jev
5. **chaoliangUNSW/Jev-Style-Qwen3.5-2B-Decision-GGUF** (HF created 2026-09-21). Qwen3.5-2B-Base fine-tune. GGUF Q4_K_M 1.31 GB, Q8_0 2.08 GB, BF16 3.9 GB, Apache-2.0. Own claim 82.3% on 5 tasks (1,500 held-out). Runs in stock llama.cpp and LM Studio. Not on JevBench. Source: https://huggingface.co/chaoliangUNSW/Jev-Style-Qwen3.5-2B-Decision-GGUF. Fits legion-t5 VRAM on paper (not verified).
