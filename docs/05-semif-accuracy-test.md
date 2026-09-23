# SemIf accuracy test with local GGUF models (2026-09-22)

Result: SemIf works with local GGUF models on the legion-t5 GPU. Our qwen3.5-4b run matches the published SemIf numbers, so the test method is sound. **Qwen3.5-9B Q4_K_M is the best choice**: it scores 81.8 % on the public JevBench items, above the published SemIf result (81.0 %), and it is 3 times faster than Ternary Bonsai 2 27B at the same quality.

Update: Qwen3.5-2B and Qwen3.5-9B were added later on 2026-09-22 (7 models in total).

The method, the scripts and the rebuild steps are in `../semif-test/README.md`. The raw results are in `../semif-test/runs/`.

## Setup

- The models ran in llama-server on legion-t5 (RTX 3060 Ti, 8 GB), one at a time, with all layers on the GPU and a 16,384-token context.
- The SemIf prompt code and the 2 test harnesses ran on the buildbox in a Podman container, without torch.
- The adapter reads the raw log-probabilities of the answer letters from llama-server and applies softmax over them. That is the same readout as SemIf.
- All 7 models: the Hugging Face tokenizer and the GGUF give the same token IDs. Every answer letter was in the top 200 tokens for every row.
- Quantization: the SemIf references use BF16. Our runs use the GGUF quants that are on legion-t5.

## Test 1: SemIf authored144

Metric: mean family balanced accuracy over 144 labeled decisions (`SemIf/benchmarks/evaluate.py`).

| Model | GGUF | Our score | SemIf reference | Difference |
|---|---|---|---|---|
| Ternary Bonsai 2 27B | PTQ1_0, 5.95 GB | **0.915** | 0.958 (Qwen3.8-27B, EXL3 5 bpw) | -0.043 |
| Qwen3.5-9B | Q4_K_M, 6.2 GB (bartowski) | **0.913** | none published | - |
| Qwen3.5-4B | Q4_K_M, 3.0 GB (the SemIf file) | **0.812** | 0.813 (BF16) | -0.002 |
| Qwen3.5-4B GSQ | Q2_K_XL, 1.9 GB | 0.773 | 0.813 (BF16) | -0.040 |
| Qwen3.5-2B | Q4_K_M, 1.4 GB (bartowski) | 0.627 | none published | - |
| MiniCPM5-2B | Q4_K_M, 1.6 GB (the SemIf file) | 0.622 | 0.686 (BF16) | -0.064 |
| Qwen3-0.6B | Q8_0, 0.6 GB (the SemIf file) | 0.438 | 0.440 (BF16) | -0.003 |

## Test 2: JevBench public items

Metric: accuracy on the 231 public items, through the JevBench harness and its `semif_direct` adapter. "Same outcome" counts the items where our run and the published SemIf run are both right or both wrong. Hard ECE is the top-label calibration error on the hard tier (lower is better).

| Model | Easy (48) | Standard (72) | Hard (111) | All 231 | Hard ECE | Same outcome as published SemIf | p50 latency |
|---|---|---|---|---|---|---|---|
| Qwen3.5-9B Q4_K_M | 100.0 % | 94.4 % | 65.8 % | **81.8 %** | 0.134 | 201/231 | 0.40 s |
| Ternary Bonsai 2 27B | 100.0 % | 90.3 % | **66.7 %** | 81.0 % | 0.143 | 199/231 | 1.22 s |
| Qwen3.5-4B Q4_K_M | 97.9 % | 95.8 % | 59.5 % | 78.8 % | **0.126** | **224/231** | 0.24 s |
| Qwen3.5-4B GSQ Q2 | 100.0 % | 91.7 % | 53.2 % | 74.9 % | 0.137 | 205/231 | 0.20 s |
| Qwen3.5-2B Q4_K_M | 100.0 % | 75.0 % | 43.2 % | 64.9 % | 0.311 | 174/231 | 0.20 s |
| MiniCPM5-2B Q4_K_M | 95.8 % | 69.4 % | 45.9 % | 63.6 % | 0.358 | 165/231 | 0.19 s |
| Qwen3-0.6B Q8_0 | 87.5 % | 44.4 % | 30.6 % | 46.8 % | 0.597 | 124/231 | 0.19 s |
| Published: SemIf Qwen3.5-4B BF16 | 100.0 % | 98.6 % | 61.3 % | 81.0 % | - | - | - |
| Published: Jev 1.13.0 | 100.0 % | 98.6 % | 73.0 % | 86.6 % | - | - | - |

For context, from the JevBench table (hard tier, all 220 items, other methods on Qwen3.8-27B): reflex-27b 75.9 %, SimpleJev Qwen3.8-27B 75.0 %.

## Do the tests align with the public results?

Yes, for the models where an exact reference exists.

- **Qwen3.5-4B Q4_K_M** is the reference setup. authored144 differs by 0.002. On JevBench, 224 of 231 items have the same outcome as the published SemIf run. The total is 2.2 points lower (78.8 % against 81.0 %). The difference is in 7 items. It comes from Q4_K_M against BF16.
- **Qwen3-0.6B** differs by 0.003 on authored144. Q8_0 is almost lossless.
- **MiniCPM5-2B** is 0.064 lower than BF16. A small model loses more in Q4_K_M. SemIf publishes no GGUF quality number for it, so this gap is not verified against a second source.
- **Ternary Bonsai** is 0.043 below the Qwen3.8-27B EXL3 reference. That reference uses 5 bits per weight. Bonsai uses 1.75 bits per weight. The vendor claims 98.2 % of FP16 quality, and we measured 95.5 % of the EXL3 score.

The JevBench composite score (74.4 for Jev, 73.1 for SemIf) cannot be computed here. The judge tier and the held-out items are not public, and the speed and cost axes depend on the hardware.

## What this means

- **Best choice:** Qwen3.5-9B Q4_K_M. It has the best total (81.8 %), almost the same hard tier as Bonsai (65.8 % against 66.7 %), and the same authored144 score (0.913 against 0.915). It runs on stock llama.cpp, uses 5.9 GB of VRAM, and takes 0.40 s for each decision.
- **Ternary Bonsai 2 27B** gives no gain over the 9B model. It needs the PrismML fork and is 3 times slower (1.22 s).
- **Fastest usable model:** Qwen3.5-4B Q4_K_M. It needs 3 GB, takes 0.24 s, and has the best calibration. It loses 3 points against the 9B model.
- **Do not use** a 2B model or smaller as a SemIf judge. Qwen3.5-2B, MiniCPM5-2B and Qwen3-0.6B fail too many standard items.
- The GSQ Q2 file saves 1.1 GB, but it loses 4 points on JevBench.

## Limits

- One run per model. There are no repeat draws and no confidence intervals.
- Only legion-t5 (CUDA). gaming-b650 (Vulkan) was not tested.
- The latency is the time for each decision through the harness, with the buildbox and the network included. It is not a llama-server benchmark.
- The Bonsai tokenizer comes from `Qwen/Qwen3.8-27B`. The Bonsai chat template in the GGUF adds a reasoning-effort sentence. SemIf uses the Hugging Face template, so that sentence is not in the test prompts.

## State of legion-t5 after the test

- `llama-embed.service` and `llama-rerank.service` are stopped and still enabled. They start again at the next reboot. LiteLLM sends embed and rerank calls to the gaming-b650 CPU fallback until then.
- No test server runs. The GPU uses 14 MiB.
- New on the host: `/opt/llama.cpp-prism` (PrismML fork, CUDA 12.8), `/opt/models/qwen3-0.6b-q8_0.gguf`, `/opt/models/qwen3.5-2b.gguf`, and `~/semif-test/` (scripts and server logs).
