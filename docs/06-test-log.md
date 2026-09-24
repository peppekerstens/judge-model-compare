# Test log and overview (2026-09-22 and 2026-09-23)

Every test of this repo, with its result. The details are in the other documents in `docs/`. The raw output is in `../semif-test/runs/` and in `../poc/results/`.

Day 1, 2026-09-22: the SemIf accuracy test with 7 local GGUF models. Day 2, 2026-09-23: the proof of concept of the router, and 3 more judge candidates.

## Overview 1: the SemIf accuracy test of the models

Both tests measure the SemIf method: one forward pass, then softmax over the logits of the answer letters. Reasoning is off. All models ran in llama-server on legion-t5 (RTX 3060 Ti, 8 GB), with all layers on the GPU and a 16,384-token context.

| # | Model | GGUF file, size | VRAM | authored144 (144 items) | JevBench public (231 items) | Hard tier (111) | Hard ECE | Time per decision | SemIf reference (BF16) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **Qwen3.5-9B** Q4_K_M | `qwen3.5-9b-standard.gguf`, 6.2 GB | 5,932 MiB | **0.913** | **81.8 %** | 65.8 % | 0.134 | 0.40 s | none published |
| 2 | **Ternary Bonsai 2 27B** PTQ1_0 | `ternary-bonsai-2-27b-ptq1_0.gguf`, 5.95 GB | 6,930 MiB | **0.915** | 81.0 % | **66.7 %** | 0.143 | 1.22 s | 0.958 (Qwen3.8-27B, EXL3 5 bpw) |
| 3 | **Qwen3.5-4B** Q4_K_M | `qwen3.5-4b.gguf`, 3.0 GB | 3,568 MiB | 0.812 | 78.8 % | 59.5 % | **0.126** | 0.24 s | 0.813 |
| 4 | Qwen3.5-4B GSQ Q2_K_XL | `qwen3.5-4b-gsq-q2kxl.gguf`, 1.9 GB | 2,668 MiB | 0.773 | 74.9 % | 53.2 % | 0.137 | 0.20 s | 0.813 (the same model at BF16) |
| 5 | Qwen3.5-2B Q4_K_M | `qwen3.5-2b.gguf`, 1.4 GB | 1,712 MiB | 0.627 | 64.9 % | 43.2 % | 0.311 | 0.20 s | none published |
| 6 | MiniCPM5-2B Q4_K_M | `minicpm5-2b.gguf`, 1.6 GB | 2,260 MiB | 0.622 | 63.6 % | 45.9 % | 0.358 | 0.19 s | 0.686 |
| 7 | Qwen3-0.6B Q8_0 | `qwen3-0.6b-q8_0.gguf`, 0.6 GB | 2,620 MiB | 0.438 | 46.8 % | 30.6 % | 0.597 | 0.19 s | 0.440 |
| - | *Published: SemIf on Qwen3.5-4B BF16* | *no GGUF* | *about 9.3 GB* | *0.813* | *81.0 %* | *61.3 %* | - | - | - |
| - | *Published: Jev 1.13.0 (cloud API)* | *closed* | - | - | *86.6 %* | *73.0 %* | - | *0.65 s* | - |

The VRAM numbers come from `nvidia-smi` with one model on the GPU, after one request, with the 16,384-token context included. Qwen3-0.6B uses more memory than Qwen3.5-2B, because its key-value cache is larger. The time is the time for each decision through the harness, with the buildbox and the network included.

**Choice:** Qwen3.5-9B Q4_K_M. It has the best total, it runs on stock llama.cpp, and it is 3 times faster than Bonsai. The reasons and the limits are in `05-semif-accuracy-test.md`.

## Overview 2: the judge candidates for the router

The judge answers 2 questions for each request: sensitive data (yes or no), and the difficulty (simple, medium or hard). The set holds 24 cases with a known answer (`../poc/judge_cases.jsonl`). The full comparison is in `../poc/results/README.md`.

| Judge | Method | Where | VRAM | Sensitive | Difficulty | Both | Median time |
|---|---|---|---|---|---|---|---|
| **Qwen3.5-4B** | Letter logprobs, 2 calls | legion GPU | 3,568 MiB | 24/24 | 23/24 | **23/24** | 0.51 s |
| Qwen3.5-9B | Letter logprobs, 2 calls | legion GPU | 5,932 MiB | 24/24 | 22/24 | 22/24 | 0.80 s |
| Qwen3.5-4B on the fork | `/v1/decision`, 1 call | legion GPU | 3,452 MiB | 22/24 | 23/24 | 21/24 | **0.28 s** |
| Qwen3.5-2B | Letter logprobs, 2 calls | legion GPU | 1,712 MiB | 24/24 | 12/24 | 12/24 | 0.41 s |
| Laya multilingual, GPU | Encoder, 1 pass | legion GPU | 1,715 MiB | 14/24 | 6/24 | 4/24 | 0.20 s |
| Laya multilingual, CPU | Encoder, 1 pass | legion CPU | none | 14/24 | 6/24 | 4/24 | 0.48 s |
| Needle 3, `record_decision` | Label and 1 confidence | legion CPU | none | 1/24 | 0/24 | 0/24 | 0.20 s |
| Needle 3, `options_as_tools` | Label and 1 confidence | legion CPU | none | 1/24 | 6/24 | 1/24 | 0.21 s |

**The choice today: Qwen3.5-4B with the letter method.** It reads the most cases right, and the router uses it.

**The fork: faster, and 2 sensitivity cases wrong.** The same model on the fork endpoint answers both questions in 1 call at 0.28 s. A wording test with 3 variants ran on 2026-09-23, and it did not fix those 2 cases. More text in the field description made the score worse. The cause is still open, and the letter method stays the judge of the router.

## The tests, in order

| # | Date | Test | Result | Where |
|---|---|---|---|---|
| 1 | 2026-09-21 | Network audit of the PrismML llama.cpp fork, release `prism-b10709-9a9394a`: source diff, release provenance, live `strace` and packet capture | Clean. 0 outgoing connections, no DNS. The audit holds for that release only | `ai-stack/docs/ternary-bonsai-2-27b.md` |
| 2 | 2026-09-22 | Research: the Jev API, JevBench v1.3.0, and 12 open Jev-style models | Jev 74.4 (#1), SemIf 73.1 (#2). No open model has an OpenAI-compatible endpoint | `01`, `02`, `03`, `00-summary.md` |
| 3 | 2026-09-22 | Router: the video code is not published. 10 community routers compared, 1 copied and read for security | prismhq/jev-router (MIT). 1 outbound call, to api.typesafe.ai, only with a key | `04-router.md`, `../router/UPSTREAM.md` |
| 4 | 2026-09-22 | Method check: the adapter prompt against the SemIf reference predictions | The prompt hashes are identical. 5 of 5 sample rows give the same answer | `../semif-test/README.md` |
| 5 | 2026-09-22 | Tokenizer check for each model: Hugging Face IDs against the GGUF vocabulary | All 7 models are equal. Mode `hf` for every run | `runs/*/authored144.log` |
| 6 | 2026-09-22 | Accuracy: 7 models, 2 tests each (144 + 231 items), 2,625 decisions in total | See the overview table. 0 failed calls. No missing answer letter | `05-semif-accuracy-test.md` |
| 7 | 2026-09-22 | Alignment with the public results, on Qwen3.5-4B Q4 against the published SemIf BF16 run | authored144: 0.812 against 0.813. JevBench: 224 of 231 items have the same outcome | `05-semif-accuracy-test.md` |

| 8 | 2026-09-23 | Proof of concept on LXC 110: a local judge, 2 questions, and 5 test examples | Each example took the right route. The judge takes 0.77 to 0.97 s | `07-poc-router-plan.md`, `../poc/README.md` |
| 9 | 2026-09-23 | Streaming through the router, on a local target and on the cloud target | 11 and 2,427 events. Both streams carried the route headers | `../poc/README.md` |

| 10 | 2026-09-23 | Judge bench: 2B, 4B and 9B on 24 cases, both questions | Sensitivity 24/24 for every model. Difficulty: 4B 23/24, 9B 22/24, 2B 12/24 | `../poc/results/README.md` |

| 11 | 2026-09-23 | Laya multilingual as a fourth judge, in a Podman container on the legion-t5 CPU | Sensitivity 14/24, difficulty 6/24, both 4/24. It needs a fine-tune | `../poc/results/README.md`, `../poc/laya/` |

| 12 | 2026-09-23 | Laya on the GPU of legion-t5, with the NVIDIA container toolkit | The same 4/24 answers as on the CPU. The median time drops from 0.48 s to 0.20 s. VRAM 1,715 MiB | `../poc/laya/README.md` |
| 13 | 2026-09-23 | Static security audit of the Codacus llama.cpp fork, branch `parallel-decision` | The diff of 1,526 lines adds no outbound call. 2 opt-in inbound routes. Provenance risk: 1 author, no upstream pull request | `08-codacus-llama-fork.md` |

| 14 | 2026-09-23 | Live network test of the fork build: no network, strace, and a packet capture | Clean. 0 outgoing connections, 0 DNS packets, and the endpoint answered in 150 ms | `../poc/decision-fork/README.md` |
| 15 | 2026-09-23 | Research and plan for Needle 3 (Cactus Compute), the next candidate | Weights open, 35 MB, 121M parameters. It gives a label and 1 confidence value, and no probability per option | `../poc/needle/README.md` |

| 16 | 2026-09-23 | The same Qwen3.5-4B as a judge through the fork endpoint `/v1/decision`, on the 24 cases | 21/24 against 23/24 for the letter method, at 0.28 s against 0.51 s. It misses 2 sensitivity cases | `../poc/decision-judge/README.md` |

| 17 | 2026-09-23 | Wording test of the sensitivity question on the fork: 3 variants over the 24 cases | The first variant stays the best at 21/24. More text gives 19/24, and an enum gives 17/24 | `../poc/decision-judge/README.md` |

| 18 | 2026-09-24 | Needle 3 on the 24 cases, in both modes, in a container on the model host CPU | 0 and 1 of 24 right. It abstains on 47 of 48 questions in the default mode | `../poc/needle/README.md` |

## What each test says

1. **The method is sound.** The adapter builds the same prompt as SemIf, byte for byte, and reads the same answer logits. The 4B reference run lands within 0.002 of the published score.
2. **Quantization costs little at Q4_K_M for a 4B model**, and more for a 2B model. Q8_0 for the 0.6B model is almost lossless. The GSQ Q2 file loses 4 points on JevBench.
3. **Model size wins.** The step from 4B to 9B gives 3 points on JevBench and 6 points on the hard tier.
4. **The 27B ternary model gives no gain over the 9B model**, and it costs the PrismML fork plus 3 times the time.
5. **A 2B model is too weak as a judge.** It fails 25 % of the standard items.
6. **One call beats two on speed, and it costs 2 sensitivity answers.** The fork answers both questions in 1 call at 0.28 s. The letter method needs 2 calls and 0.51 s. A wording test with 3 variants did not fix the 2 misses, so the field description is not the cause.
7. **An encoder model is not a judge out of the box.** Laya multilingual answers in 0.5 to 0.8 s on the CPU and costs no VRAM, but it reads 4 of 24 bench cases right. The author says the same: the base checkpoints score near random zero-shot.
8. **The gap to Jev 1.13.0 is on the hard tier**: 65.8 % for the 9B model against 73.0 % for Jev.

## Failures during the work, and the fix

| Problem | Cause | Fix |
|---|---|---|
| `pip install cactus-needle` stopped with HTTP 404 | Version 3.0.5 asks Hugging Face for an engine wheel 3.0.2, and that file does not exist | Pin `cactus-needle==3.0.1` in the `Containerfile` |
| `results_table.py` stopped with a `None` error on the Needle rows | A judge that abstains gives no value, and the header was fixed to the Qwen judges | A dynamic header from `ORDER`, and the text "abstained" for an empty answer |
| The CUDA build of the fork failed with `undefined reference to cuMemCreate` | The CUDA devel image ships the driver API as a stub only | The stub folder on the link line, a `libcuda.so.1` link, and the linker flags |
| The fork binary stopped with `libgomp.so.1: cannot open shared object file` | The CUDA runtime image has no OpenMP | `libgomp1` in the runtime stage |
| The fork server stopped with `failed to allocate buffer for rs cache` | Qwen3.5 is hybrid attention, so the recurrent-state cache scales with `--decision-seqs` | 3 sequences and a context of 8,192 |
| The decision endpoint answered HTTP 400 | Every schema field needs a `description` | The payloads carry one for each field |
| The security test could not use `strace` | `ptrace_scope` is 1 on legion-t5, and the password pipe collided with the heredoc | `audit-privileged.sh`, copied to the host and started as root |
| `docker build` on LXC 110 found no Dockerfile | Docker reads only `Dockerfile`, not `Containerfile` | `docker build -f Containerfile` |
| 2 MiniCPM5 runs tested qwen3.5-4b | A server started by hand kept port 11435. The health check reached the old server | `serve-model.sh` stops every server on the port and checks `/props`. `run-model.sh` needs `EXPECT_GGUF`. The runs stay in `runs/invalid/` |
| `podman build` failed with "Failed to open() /dev/net/tun" | The buildbox is an unprivileged LXC | `--network host` for each Podman command |
| The prism binary did not start: `libcudart.so.12` not found | The prism tarball has no CUDA runtime | `LD_LIBRARY_PATH=/opt/llama.cpp-prism:/opt/llama.cpp/cuda_v12` (the same CUDA 12.8) |
| `curl` missing on the buildbox | The base image has no curl | The container reads `/props` with Python |
| Port 11437 not reachable from the workstation | `ufw` on legion-t5 allows only 11434, 11435 and 11436 | The server moved to port 11434 |

## State of the hosts after the tests

Checked live on 2026-09-24, after the cleanup.

**legion-t5**

- `llama-embed` (port 11435) and `llama-rerank` (port 11436) run again, after the reboot. They hold 7,402 MiB of the 8,192 MiB card. LiteLLM uses legion as the primary again.
- The judge model of the router stopped at the reboot. It has no systemd unit. The GPU has 753 MiB free, so the model does not fit next to the 2 tiers. The router falls back on every request.
- The llama.cpp fork stays on the host as the image `localhost/decision-fork` and the stopped container `decision-fork`. It cannot start now: `llama-rerank` holds its port 11436, and the GPU has no room. To use it, stop `llama-rerank` first, or map another port.
- The Laya containers and images are removed. The Needle image is removed. The build folders `~/needle-cache`, `~/needle-smoke` and `~/semif-test` are removed.
- Still on the host: `/opt/llama.cpp-prism` (197 MB), and the GGUF files of the test in `/opt/models/`. The prism fork runs the Bonsai model, so both stay.

**LXC 110**

- `semif-judge` (8080), `jev-router` (8081) and `decision-judge` (8085) run. They stay.

**buildbox (LXC 103)**

- `/srv/semif-test`, the image `semif-remote` and the image `prism-audit` are removed. Every script to rebuild them is in this repository.

## Work still to do

| # | Work | Estimate | Where |
|---|---|---|---|
| 1 | ~~Needle 3: install and test~~ **Done on 2026-09-24. It is not usable: 0 and 1 of 24 cases right** | done | `../poc/needle/README.md` |
| 2 | Find why the fork misses 2 sensitivity cases. The wording is not the cause, so the prompt template of the fork is the next place to look | 1 hour | `../poc/decision-judge/README.md` |
| 3 | Decide on the fork: keep the letter method, or take the speed win for the difficulty question only | 30 minutes | `../poc/results/README.md` |
| 4 | Stage 2 of the router: authentication, and a rate limit | not planned | `07-poc-router-plan.md` |

## Open items

- Why the fork misses 2 sensitivity cases. The wording is not the cause. The next idea is the prompt template of the fork.
- Needle 3 is tested and closed. It abstains on our questions, because it looks for a tool that serves the request.
- The 9B model has no LiteLLM tier.
- gaming-b650 (Vulkan, 32 GB) is not tested. Qwen3.5-27B Q4 fits there, but SemIf has no published number for it.
- One run per model. There are no repeat draws and no confidence intervals.
- The JevBench composite score cannot be computed here. The judge tier and the held-out items are not public.
