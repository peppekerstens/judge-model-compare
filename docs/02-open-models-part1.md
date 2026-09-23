# Open Jev-style models, part 1

Research date: 2026-09-22. Scope: SemIf, Bespoke Nimble, decider, and Alex Wortega's openjev.
All data comes from the live repositories, the Hugging Face API and the JevBench page on this date.
Nothing was downloaded, installed or run on the local hosts. "Not verified" means that no source confirms the fact.

Context sources:

- Video "Open Jev Models Are Here!!" by Sam Witteveen: https://www.youtube.com/watch?v=53wDOI_7x8I (title from YouTube oEmbed. The video content was not watched.)
- JevBench v1.3.0, scored 2026-09-21, 52 systems, 534 decisions, 220 of them hard: https://benchmarkheaven.com/jev-models. Raw data: https://benchmarkheaven.com/api/jevbench/v1.2. Harness: https://github.com/fstandhartinger/jevbench.
- JevBench score = geometric mean of Intelligence, Calibration, Speed and Cost (25 % each). Jev 1.13.0 is rank 1 with 74.4 (https://benchmarkheaven.com/jev-models).

Host assumptions used in the fit sections:

- gaming-b650: Radeon AI PRO R9700, 32 GB VRAM, Vulkan/ROCm, llama.cpp. A 27B chat model uses about 26-30 GB, so only about 2-6 GB VRAM is free.
- legion-t5: RTX 3060 Ti, 8 GB VRAM, CUDA. 14 GB RAM, nearly full. The GPU already runs llama.cpp embed and rerank. The free VRAM on legion is not verified.

## Summary table

| | SemIf | Bespoke Nimble 9B | decider | openjev (Alex Wortega) |
|---|---|---|---|---|
| Own weights | No. It uses stock Qwen3.5-4B | Yes. LoRA adapter, 173 MB | Yes. 0.8B, 2B, 2B-vision, 4B, 35B-A3B | Yes. 0.8B, 4B v1, 4B v2, 35B-A3B |
| Base | Qwen3.5-4B (4.66B params) | Qwen3.5-9B (9.65B params) | Qwen3.5 Base models | Qwen3.5 (0.8B, 4B, 35B-A3B) |
| License | MIT code, Apache-2.0 weights | Apache-2.0 adapter. GitHub repo has no license file | Apache-2.0 | MIT |
| Output | Probability per option | Probability per enum/boolean choice | Choice, Score, Noul (yes-probability) | 3 NLI labels only |
| GGUF | Stock Qwen3.5-4B GGUF (bartowski) | None | Third-party: 0.8B, 2B, 2B-vision, 35B | None |
| Server | None merged (PR #27 open) | SGLang + `/v1/systemone` (Modal code) | `/v1/systemone` + `/decide`, CUDA only | SGLang `/classify` |
| OpenAI-compatible | No | No | No | No |
| JevBench v1.3.0 | Rank 2, 73.1 | Rank 24, 60.5 | 35B: rank 8, 67.6. 2B: rank 23, 61.7 | Not ranked (no arbitrary label set) |
| GitHub stars | 3,688 | 1,592 | 306 | n/a (HF only, 468 likes) |
| Last commit | 2026-09-21 | 2026-09-20 | 2026-09-22 | 2026-09-21 |
| Runs on gaming-b650 | Yes, CPU path now. GPU needs PR #26 + Vulkan llama-cpp-python (not verified) | No, not beside the 27B. ROCm path not verified | Yes, 2B/0.8B GGUF through llama.cpp shim (Vulkan not verified) | Not verified. No GGUF, ROCm torch only |
| Runs on legion-t5 | Maybe. 4B Q4_K_M is 3.0 GB, free VRAM not verified | No. 9B BF16 is about 18 GB | Yes, decider-2b Q8_0 (2.0 GB) or 0.8B | Maybe, 0.8B (1.7 GB BF16) with transformers CUDA |

## 1. SemIf (formerly OpenJev, TheoLeeCJ)

Repository: https://github.com/TheoLeeCJ/SemIf

What it is:

- SemIf is a scoring harness, not a trained model. It reads option logits from a frozen stock model in one forward pass (https://github.com/TheoLeeCJ/SemIf README, "How it works").
- The main model is `Qwen/Qwen3.5-4B` at revision `851bf6e8`, BF16. The repo also lists Qwen3-0.6B, MiniCPM5-2B and Qwen3-Reranker-4B (https://github.com/TheoLeeCJ/SemIf/blob/main/manifests/models.json).
- Qwen3.5-4B has 4,659,865,088 parameters, Apache-2.0 (https://huggingface.co/api/models/Qwen/Qwen3.5-4B). BF16 weights are therefore about 9.3 GB.
- The repo ships no weights. "Model weights and third-party source records are not included" (README, last section).

Weight files it uses:

- BF16 safetensors from `Qwen/Qwen3.5-4B` (manifests/models.json).
- GGUF `bartowski/Qwen_Qwen3.5-4B-GGUF`, Q4_K_M, 3,013,027,808 bytes (manifests/models.json).
- Browser ladder: Qwen3-0.6B Q8_0 639 MB, MiniCPM5-2B Q4_K_M 1.56 GB (manifests/models.json).
- A community EXL3 bridge runs Qwen3.8-27B at 5 bpw (https://github.com/TheoLeeCJ/SemIf/tree/main/exl3-bridge).

License: MIT for the code (https://github.com/TheoLeeCJ/SemIf/blob/main/LICENSE). The upstream weights keep their own licenses (README).

Tasks and output:

- Input is JSONL with `state`, `question` and `options` (id + description). `state` can be text or JSON (README, "Input").
- Output is typed option scores, timing, the model revision and a prompt hash per row (README, "Quick start").
- Modes: `direct`, `serial`, `shared` (prefill state once, then branch the criteria), `reranker` (https://github.com/TheoLeeCJ/SemIf/blob/main/src/semif_phase1/cli.py).

Quality:

- Own numbers, 4B BF16 direct logits: authored decisions 0.813 balanced accuracy, WANLI 0.637, TypeSafe 102-row subset 0.845 agreement against 0.883 for published Jev (README, "Quality").
- The 27B EXL3 bridge scores 0.958 on the authored set (README).
- Speed on one RTX 3090: 21 decisions in 1.023 s with direct logits, 20.03 decisions/s with parallel suffixes (README, "Speed").
- JevBench v1.3.0: rank 2, score 73.1. Intelligence 79.0, Calibration 72.6, Speed 83.7, Cost 59.5. Run on a RunPod RTX PRO 4500 32 GB. Hard tier 0.595 (https://benchmarkheaven.com/api/jevbench/v1.2).

How to run:

- Python package `semif-phase1`, CLI `semif-score`. It pins torch 2.10.0 and transformers 5.17.0 (https://github.com/TheoLeeCJ/SemIf/blob/main/pyproject.toml).
- Backends: `torch` (CUDA, MPS), `mlx`, `llamacpp` (cli.py).
- The llama.cpp backend uses `llama-cpp-python==0.3.35` (pyproject.toml). It sets `n_gpu_layers = 0`, so it is CPU only today (https://github.com/TheoLeeCJ/SemIf/blob/main/src/semif_phase1/llamacpp_backend.py).
- PR #26 "Add --llama-gpu-layers to the llama.cpp backend" is open, not merged (https://github.com/TheoLeeCJ/SemIf/pull/26).
- The llama.cpp backend still needs the reference transformers tokenizer (llamacpp_backend.py header).
- No vLLM path (not found in the repo tree).

Server: none merged. PR #27 "Add semif-serve: a Jev-compatible HTTP layer" is open (https://github.com/TheoLeeCJ/SemIf/pull/27). It speaks the TypeSafe wire format, not the OpenAI format.

Hardware:

- Torch path: "CUDA, and a GPU that can hold a 4B BF16 model" (README, "Quick start"). That is about 9.3 GB plus activations.
- CPU path: GGUF through llama.cpp, "no CUDA device" (README). RAM need for Q4_K_M is about 3 GB plus context (estimate, not verified).
- A browser WebGPU demo also exists (https://github.com/TheoLeeCJ/SemIf/tree/main/webgpu-demo).

Activity: 3,688 stars, 240 forks, 20 open issues and PRs, last commit 2026-09-21, created 2026-09-16 (https://api.github.com/repos/TheoLeeCJ/SemIf).

Fit:

- gaming-b650: yes on CPU with the llamacpp backend and the 3.0 GB Q4_K_M GGUF. GPU use needs PR #26 plus a Vulkan or ROCm build of llama-cpp-python (not verified). The torch path on ROCm is not verified. The code checks for `cuda` or `mps` devices only (cli.py `--device` choices).
- legion-t5: maybe. The 4B BF16 torch path does not fit in 8 GB beside embed and rerank. The Q4_K_M GGUF (3.0 GB) needs PR #26 for GPU. CPU mode needs about 3 GB RAM, and the RAM is nearly full.
- Blockers: no GPU offload in the merged llama.cpp backend, no server yet, large pinned Python stack (torch + transformers) even for the GGUF path.

## 2. Bespoke-Nimble-9B (Bespoke Labs)

Model: https://huggingface.co/bespokelabs/Bespoke-Nimble-9B. Code: https://github.com/bespokelabsai/nimble

What it is:

- A LoRA adapter (rank 16, alpha 32) on `Qwen/Qwen3.5-9B` at revision `c2022362` (https://huggingface.co/bespokelabs/Bespoke-Nimble-9B/blob/main/adapter_config.json).
- Qwen3.5-9B has 9,653,104,368 parameters (https://huggingface.co/api/models/Qwen/Qwen3.5-9B).
- Training: 2,676 synthetic examples labeled by GPT-5.6 and Claude Sonnet 5, not human-reviewed (https://huggingface.co/bespokelabs/Bespoke-Nimble-9B/blob/main/training_summary.json).

Weight files:

- `adapter_model.safetensors`, 173,188,512 bytes. No base weights, no merged weights, no GGUF, no quants (https://huggingface.co/api/models/bespokelabs/Bespoke-Nimble-9B).
- The HF search finds no quantized derivative (https://huggingface.co/api/models?search=Nimble-9B).
- The user must merge the adapter into the base on CPU. "the 9B weights alone take about 18 GB" (https://github.com/bespokelabsai/nimble README, "Quickstart").

License: Apache-2.0 on HF (model card). The GitHub repo has no LICENSE file (GitHub API returns 404 for LICENSE. JevBench notes the same, https://benchmarkheaven.com/api/jevbench/v1.2).

Tasks and output:

- Context plus a flat schema. Each field is an enum (1 to 26 choices) or a boolean. Integer enums work as rubric scores (HF model card).
- Output: chosen value per field, plus probabilities and logits per choice. Score fields also return an expected score (https://huggingface.co/bespokelabs/Bespoke-Nimble-9B/blob/main/inference.py).
- Text only, English. Prompt limit was 2,048 tokens. The GitHub code raised it to 8,192 tokens in PR #4 (https://github.com/bespokelabsai/nimble/commits).

Quality:

- Own 324-example holdout: 90.1 % for Nimble, 66.4 % for base Qwen3.5-9B, 93.2 % for Jev 1.13.0 (GitHub README infographic, https://huggingface.co/bespokelabs/Bespoke-Nimble-9B/blob/main/evaluation_summary.json).
- Own public suite of 13 human-labeled subsets against Jev 1.13.0. Examples: BoolQ 86.0 % against 89.7 %, MASSIVE en-US 86.9 % against 87.4 %, civil_comments 70.3 % against 81.0 %, MultiNLI 85.3 % against 82.9 % (https://github.com/bespokelabsai/nimble/blob/main/docs/PUBLIC_BENCHMARKS.md).
- JevBench v1.3.0: rank 24, score 60.5. Intelligence 77.9, Calibration 65.3, Speed 78.7, Cost 33.4. Hard tier 0.655. Run on a RunPod A40 48 GB with SGLang (https://benchmarkheaven.com/api/jevbench/v1.2).

How to run:

- Reference runner: transformers 5.17.0 + peft 0.21.0 + torch 2.8.0 (https://huggingface.co/bespokelabs/Bespoke-Nimble-9B/blob/main/requirements.txt).
- `inference.py` raises an error unless `torch.cuda.is_available()` and BF16 are true. It scores one field per full forward pass (inference.py).
- Apple Silicon: MLX runner on the merged folder. It does not load quantized weights (GitHub README, "Mac with Apple Silicon").
- Serving: SGLang 0.5.19 with the openjev-sglang client, deployed on Modal (https://github.com/bespokelabsai/nimble/blob/main/docs/MODAL_SERVING.md).
- llama.cpp: no path from the authors. A self-made GGUF of the merged model could work, because scoring reads the last-token logits of one-letter codes. Not verified.
- Open issue #6 asks for ROCm/AMD support (https://github.com/bespokelabsai/nimble/issues/6).

Server: `POST /v1/systemone` in TypeSafe format on SGLang (MODAL_SERVING.md). Not OpenAI-compatible. SGLang itself has an OpenAI API, but that path does not return the typed scores (not verified).

Hardware: NVIDIA GPU with BF16, or Apple Silicon (GitHub README). BF16 weights about 18-19 GB, plus activations. The CPU merge step needs extra RAM and disk (GitHub README). CPU-only inference: not supported by the reference code.

Activity: GitHub 1,592 stars, 3 open issues, last commit 2026-09-20. HF: 5 commits, last 2026-09-18, 158 likes, 1,924 downloads (GitHub API, HF API).

Fit:

- gaming-b650: no, not beside the 27B model. BF16 needs about 18+ GB. The runner needs CUDA. ROCm torch may pass the `torch.cuda` check, but that is not verified (issue #6 is open). A self-made Q4 GGUF (about 5-6 GB, estimate) through llama.cpp is possible in theory, not verified.
- legion-t5: no. 18 GB BF16 does not fit in 8 GB VRAM or 14 GB RAM.
- Blockers: adapter only (merge needed), no GGUF, CUDA/BF16 check in code, 9B size.

## 3. decider (Mapika)

Code: https://github.com/Mapika/decider. Weights: https://huggingface.co/Mapika

What it is:

- Full fine-tunes of Qwen3.5 Base models. The model reads hidden states at answer slots and projects them on option-letter tokens. All questions come out of one forward pass (https://github.com/Mapika/decider README, "How it works". Code: https://github.com/Mapika/decider/blob/main/decider/model.py).
- It uses the stock `AutoModelForCausalLM` class plus a letter projection. No new layers (model.py).

Models and weight files (https://huggingface.co/api/models/Mapika/...):

| Model                       | Base                           | Params           | File              | Size        |
| --------------------------- | ------------------------------ | ---------------- | ----------------- | ----------- |
| decider-0.8b                | Qwen3.5-0.8B-Base              | 0.8B             | model.safetensors | 1.51 GB     |
| decider-2b (v10)            | Qwen3.5-2B-Base                | 1.9B             | model.safetensors | 3.76 GB     |
| decider-2b-vision           | Qwen3.5-2B VL, v5 text weights | 1.9B             | model.safetensors | 4.43 GB     |
| decider-4b (v1, 2026-09-22) | Qwen3.5-4B-Base                | 4.2B             | model.safetensors | 8.41 GB     |
| decider-35b-a3b             | Qwen3.5-35B-A3B-Base           | 34.7B, 3B active | 15 shards         | about 69 GB |
| decider-35b-a3b-nvfp4       | same, NVFP4                    | 34.7B            | 5 shards          | about 21 GB |

Third-party GGUF:

- `cosetoenor/decider-2b-GGUF` (v10): F16 3.78 GB, Q8_0 2.01 GB, IQ4_NL 1.24 GB (https://huggingface.co/cosetoenor/decider-2b-GGUF).
- `mradermacher/decider-0.8b-GGUF`: Q2_K 0.42 GB to F16 1.52 GB. Q4_K_M 0.53 GB, Q8_0 0.81 GB (https://huggingface.co/mradermacher/decider-0.8b-GGUF).
- `mradermacher/decider-2b-vision-GGUF`: Q4_K_M 1.27 GB, Q8_0 2.01 GB, mmproj 0.37-0.67 GB (https://huggingface.co/mradermacher/decider-2b-vision-GGUF).
- `mradermacher/decider-35b-a3b-GGUF`: Q2_K 12.9 GB, Q4_K_M 21.2 GB, Q8_0 36.9 GB (https://huggingface.co/mradermacher/decider-35b-a3b-GGUF).
- No GGUF for decider-4b (HF search, 2026-09-22).

License: Apache-2.0 (https://github.com/Mapika/decider/blob/main/LICENSE, HF cards).

Tasks and output:

- Choice (2 to 255 options), Score (2 to 10 levels), Noul (probability of yes) (README).
- Output per question: choice, confidence, certainty, probabilities. English only (README, "Quick start" and "Limits").
- Context 32k tokens (README, "Models").

Quality:

- Own held-out regression set: 2B 0.755, 4B 0.788, 35B 0.810. 0.8B 0.71 on the 94-task set (README, "Models").
- JevBench v1.3.0: decider-35b-a3b rank 8, score 67.6 (I 79.6, C 71.5, S 80.8, K 45.3, hard tier 0.655). decider-2b rank 23, score 61.7 (I 61.2, C 46.6, S 83.2, K 61.0, hard tier 0.473) (https://benchmarkheaven.com/api/jevbench/v1.2). decider-4b is not on JevBench yet.
- The authors report the 4B at 0.541 on the JevBench hard tier (README, "What's new"). Not verified by JevBench.
- Decision Index v0.1: 35B NVFP4 rank 4 of 32 with 54.3, 2B rank 14 with 44.0 (README, "Standing").
- Third-party GGUF check (v8 weights, RTX 3070 Ti 8 GB): Q8_0 BoolQ 83.55 %, CLINC-11 96.5 %, P50 18-24 ms. Q8_0 agrees with BF16 on 70 of 71 picks (cosetoenor README). The v10 GGUF files have no runtime validation yet (same source).

How to run:

- `pip install decider-ai`. `Decider(...)` picks CUDA, then MPS, then CPU (https://github.com/Mapika/decider/blob/main/decider/infer.py).
- CUDA path: bf16, torch.compile, CUDA graphs, optional FP8 (README, "Runs on").
- CPU works for the library. Issue #5 reports tests and the quick start pass on CPU (https://github.com/Mapika/decider/issues/5).
- vLLM: used only to check the NVFP4 build (`vllm_check.py` in https://huggingface.co/Mapika/decider-35b-a3b-nvfp4). NVFP4 needs Blackwell hardware (general NVFP4 fact, not verified in the repo).
- llama.cpp: plain `llama-server` does not give option probabilities. The cosetoenor repo has `dz_shim.c` (C wrapper over libllama) and `decider_llama_serve.py`, a FastAPI `/v1/systemone` server. It builds the prompt with the original Python repo and reads logits at the answer slots (cosetoenor README, "Use").

Server:

- `scripts/serve.sh` gives `POST /v1/systemone` (TypeSafe format) and `POST /decide` (README, "HTTP server").
- The server is CUDA only. On a host without CUDA it fails with "Torch not compiled with CUDA enabled" (issue #5, open).
- Not OpenAI-compatible.

Hardware: 2B about 4 GB, 4B 8.4 GB, 35B 65 GB in bf16 or 19.6 GB in NVFP4 (README, "Runs on").

Activity: 306 stars, 12 forks, 2 open issues, last commit 2026-09-22 15:20 UTC. decider-2b has 72,354 downloads (GitHub API, HF API).

Fit:

- gaming-b650: yes for decider-2b (Q8_0 2.0 GB) or decider-0.8b through llama.cpp and the cosetoenor shim. Build libllama with Vulkan instead of CPU. Vulkan with the Qwen3.5 hybrid (Gated DeltaNet) state save/restore is not verified. It fits in the 2-6 GB free VRAM. The torch server path needs CUDA. ROCm torch is not verified.
- legion-t5: yes for decider-2b Q8_0 (2.0 GB) or IQ4_NL (1.2 GB) through the llama.cpp shim with CUDA. The same file ran on an 8 GB RTX 3070 Ti (cosetoenor README). The torch server path also works on CUDA, but it needs about 4 GB VRAM for the 2B plus a full Python torch stack. decider-4b (8.4 GB BF16) does not fit.
- Blockers: the official server is CUDA only. The GGUF path is third-party code, needs a C shim build, and v10 GGUF runtime is not validated. No GGUF for 4B.

## 4. openjev (Alex Wortega)

Model: https://huggingface.co/AlexWortega/openjev (no GitHub repo. Code is in the `code/` folder of the HF repo.)

What it is:

- Qwen3.5 fine-tuned as an NLI cross-encoder. `Qwen3_5ForSequenceClassification`, 3 labels: contradiction, entailment, neutral. Last-token pooling (https://huggingface.co/AlexWortega/openjev README, "What's inside". Config: https://huggingface.co/AlexWortega/openjev/blob/main/qwen3.5-4b-nli-v2/config.json).
- It answers "does the premise entail the hypothesis". Choice tasks are built by scoring one hypothesis per option (`rerank`, `predict_hypotheses`) (README, "Use it").

Weight files (https://huggingface.co/api/models/AlexWortega/openjev):

| Folder | Base | Size |
|---|---|---|
| qwen3.5-0.8b-nli-v2s-long (4k context) | Qwen3.5-0.8B | 1.71 GB |
| qwen3.5-4b-nli-v2 (recommended, text + images) | Qwen3.5-4B | 9.08 GB |
| qwen3.5-4b-nli (v1, text) | Qwen3.5-4B | 9.08 GB |
| qwen3.5-35b-a3b-nli | Qwen3.5-35B-A3B | 69.2 GB (2 shards) |
| mlp_heads_35b/ (9 task heads) | on 35B latents | 4.2 MB each |

- No GGUF, no quants. The HF search finds no quantized derivative (https://huggingface.co/api/models?filter=base_model:quantized:AlexWortega/openjev).
- Note: other repos on HF also use the name "openjev" (for example `openjev/openjev`, `ZefanCai/Open-Jev-9B`). They are different projects (https://huggingface.co/api/models?search=openjev).

License: MIT (model card).

Tasks and output:

- Output: 3 NLI probabilities per (premise, hypothesis) pair. Also rerank, grade, latents (README).
- Images work in the 4B v2 model through the Qwen3.5 image processor (README).

Quality (own numbers):

- 0.8B v2s: MNLI 86.2/87.1, ANLI r1 65.1, SciTail 93.2, RAGTruth AUROC 0.90 (README).
- 4B v2: ANLI r3 0.63, WANLI 0.77, image claims 0.84, ARC-Challenge 0.72, MMLU 0.53, MNLI 0.91 (README).
- JevBench: not ranked. "Its released NLI and task-specific heads do not define a distribution over an arbitrary supplied label set" (https://benchmarkheaven.com/jev-models, availability list). The "OpenJev" rows at rank 11 and 26 on JevBench are other projects (razorback16 and an unnamed entry). Which project the rank 26 row is: not verified.

How to run:

- transformers with `AutoModelForSequenceClassification` and a `subfolder`, or the custom `modeling_openjev.py` (`OpenJevCrossEncoder`) (README).
- The 35B needs the custom `modeling_qwen35_moe_seqcls.py` (README).
- SGLang 0.5.19 with an external model package `code/sglang_openjev`. It uses the triton attention backend by default (https://huggingface.co/AlexWortega/openjev/blob/main/code/serve_sglang.sh).
- llama.cpp: no GGUF. Conversion of a Qwen3.5 sequence-classification head to GGUF is not verified.
- vLLM: not mentioned.

Server: SGLang `/classify`, returns 3 raw logits (README, "Serve it with SGLang"). Not OpenAI-compatible.

Hardware: not stated in the card. BF16 file sizes give the floor: 1.7 GB (0.8B), 9.1 GB (4B), 69 GB (35B). CPU-only with transformers is possible in principle for the 0.8B. Not verified.

Activity: 40 HF commits, last 2026-09-21, 468 likes, 2 discussions (1 open) (https://huggingface.co/api/models/AlexWortega/openjev/commits/main). The HF API shows 0 downloads, which is probably a counter artifact (not verified).

Fit:

- gaming-b650: not verified. No GGUF, so llama.cpp does not apply. transformers or SGLang on ROCm torch is needed. The 0.8B (1.7 GB) fits the free VRAM. The 4B (9.1 GB) does not fit beside the 27B.
- legion-t5: maybe, only the 0.8B with transformers on CUDA (1.7 GB BF16). It needs a full Python torch stack on the host. The 4B does not fit in 8 GB beside embed and rerank.
- Blockers: NLI output only (no arbitrary label set), no GGUF, custom code for the 35B and SGLang, no Jev wire format.

## Blockers, short list

- No model has an OpenAI-compatible endpoint. decider and Nimble speak the TypeSafe `/v1/systemone` format. SemIf has only an open PR for that. openjev speaks SGLang `/classify`.
- Only decider has ready GGUF files, and they are third-party. They need the cosetoenor C shim, because plain llama-server cannot return per-slot option logits.
- The Vulkan and ROCm paths are not verified for any of the four models.
- gaming-b650 has only about 2-6 GB free VRAM while the 27B runs. Only decider-2b/0.8B GGUF and SemIf Q4_K_M (3.0 GB) fit.
- legion-t5 RAM is nearly full, so the CPU paths are not practical there. The free VRAM beside embed and rerank is not verified.
