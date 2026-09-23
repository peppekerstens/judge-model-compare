# Summary: Jev model options (2026-09-22)

Scores come from JevBench v1.3.0, scored on 2026-09-21. The score is the geometric mean of Intelligence, Calibration, Speed and Cost. "Hard" is the accuracy on the hard tier. Details and sources: `01` to `03` in this folder.

| Model | Base, size | Weights and file size | License | JevBench (rank) | Hard | gaming-b650 (R9700, Vulkan) | legion-t5 (3060 Ti 8 GB) | Main blocker |
|---|---|---|---|---|---|---|---|---|
| Jev 1.13.0 (TypeSafe) | Closed, size not published | API only, $0.042 per 1M input tokens | Contract forbids distillation | 74.4 (#1) | 74.1 % | n/a (cloud) | n/a (cloud) | Cloud service. Prompts leave the network |
| SemIf | Stock Qwen3.5-4B, no training | GGUF Q4_K_M 3.0 GB | MIT (code) | 73.1 (#2) | 59.5 % | Yes, CPU only | Probably (3.0 GB) | GPU offload is in PR #26 (not merged). No HTTP server |
| djev (Maisa) | DiffusionGemma 26B-A4B | BF16 51.6 GB, NVFP4 18.8 GB, GGUF Q4 16.8 GB | Apache-2.0 | 73.0 (#3) | 69.5 % | No | No | Diffusion LM: vLLM PR open, llama.cpp has CLI only. Too large next to the 27B chat model |
| Winnow-12B | 12B | GGUF Q8_0 12.7 GB | Not verified | 71.2 (#4) | 70.9 % | Not verified | No (too large) | Its server is a llama.cpp patch for CUDA and Metal only |
| reflex 4B | 4B | Not researched | Not verified | 70.3 (#5) | 63.2 % | Not verified | Not verified | Found late in JevBench. Not researched |
| decider-35b-a3b | Qwen 35B-A3B MoE | Third-party GGUF | Apache-2.0 | 67.6 (#8) | 65.5 % | No (VRAM) | No | Too large |
| decider-2b | 2B | Third-party GGUF Q8 2.0 GB | Apache-2.0 | 61.7 (#23) | 47.3 % | Yes, with a C shim and Vulkan libllama | Yes, with a C shim and CUDA | Plain llama-server cannot return the answer logits. The shim is not validated |
| Bespoke Nimble 9B | 9B, LoRA adapter 173 MB | No merged weights, no GGUF | Apache-2.0 | 60.5 (#24) | 65.5 % | No (CUDA BF16 only) | No (about 18 GB) | CUDA only |
| OpenJev (Wortega) | 0.8B / 4B / 35B-A3B NLI | Safetensors, no GGUF | MIT | Not ranked | - | Not verified | Maybe, 0.8B (1.7 GB) | NLI labels only. Cannot pick from own labels |
| Laya | ModernBERT-large 421M | 843 MB | Apache-2.0 | 54.4 (#33) | 34.1 % | Yes, CPU | Yes, CPU or CUDA | Needs a fine-tune on own data. No server |
| NanoJev | Qwen3-0.6B plus heads | 2.39 GB FP32 | MIT | Not ranked | - | Not verified | Probably | Trained on 4 games only. Not a general classifier |
| OpenSourceJev | Stock Qwen3-1.7B or Qwen3.5-4B GGUF | 1.83 / 2.74 GB | MIT | Not listed | - | No, as shipped | No, as shipped | Windows only (`llama.dll` through ctypes) |
| Jev-Style-Qwen3.5-2B | 2B | GGUF Q4_K_M 1.3 GB | Not verified | Not listed | - | Not verified | On paper yes | No benchmark. Not verified |

## Common blockers

- No open model has an OpenAI-compatible endpoint. They use `/v1/systemone`, `/classify`, or a Python API.
- Jev-style answers need the probability of each option. Stock `llama-server` does not give the answer-slot logits in the form these projects need.
- No source confirms a Vulkan or ROCm path for any open model.
- VRAM: the 27B chat model on gaming-b650 leaves about 2 to 6 GB free. The RAM on legion-t5 is almost full.

## Router

`router/` holds prismhq/jev-router (MIT, commit 583f0a1d). It is a LiteLLM proxy hook. See `04-router.md` and `router/UPSTREAM.md`.
