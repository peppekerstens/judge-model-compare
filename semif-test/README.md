# SemIf accuracy test with local GGUF models

This folder holds everything to run the test again: the adapter, the container, the host scripts, and the results.
The report is in `../docs/05-semif-accuracy-test.md`.

## What the test does

SemIf ([TheoLeeCJ/SemIf](https://github.com/TheoLeeCJ/SemIf)) scores a decision with one forward pass. It applies softmax over the logits of the answer letters A, B, C and so on. Stock SemIf loads the model into its own process. Here the model runs in llama-server on the legion-t5 GPU, and a small adapter on the buildbox does the rest:

1. It builds the prompt with the SemIf code (`semif_phase1.direct.encode_prompt`, not changed).
2. It sends the exact token IDs to llama-server `/completion` with `n_probs: 200` and `post_sampling_probs: false`.
3. It takes the raw log-probabilities of the answer-letter tokens and applies softmax over them.

Step 3 gives the same numbers as the SemIf readout, because the log normalizer cancels. The only condition: each letter must be in the top 200 tokens. The adapter records the rows where a letter is missing (`missing_letters`). In all runs so far, no letter was missing.

The adapter checks the tokenizer before each run (`check_tokenizer`). When the Hugging Face tokenizer and the GGUF give the same IDs, it uses the Hugging Face IDs (mode `hf`, the exact SemIf path). When they differ, it tokenizes the SemIf prompt text with the GGUF tokenizer (mode `server`). All 7 models used mode `hf`.

## The 2 tests

| Test | Items | Harness | Public reference |
|---|---|---|---|
| SemIf authored144 | 144 labeled decisions | `SemIf/benchmarks/evaluate.py`, mean family balanced accuracy | `SemIf/results/raw/browser-model-ladder.json` (BF16 per model), README (Qwen3.8-27B EXL3) |
| JevBench public | 231 items: 48 easy, 72 standard, 111 hard | `jevbench` CLI with its `semif_direct` adapter, forward pass swapped | `jevbench/results/v1.2/jevbench-v1.2-per-task.json`: the outcome per item for SemIf and Jev |

JevBench has 534 decisions in total. The judge tier (146) and the held-out items (157) are not public, so the official composite score cannot be computed here.

## Files

| File | Where it runs | What it does |
|---|---|---|
| `install-legion.sh` | legion-t5, once | Installs the PrismML fork (CUDA 12.8) in `/opt/llama.cpp-prism`, and downloads Qwen3-0.6B Q8_0 and Qwen3.5-2B Q4_K_M. Checks each sha256 value. |
| `serve-model.sh` | legion-t5 | Stops every llama-server on port 11435, starts one model on the GPU, and checks that the right file loaded. |
| `Containerfile` | buildbox | Image `localhost/semif-remote`: Python 3.13 and `transformers==5.17.0`, the version that SemIf pins. No torch. |
| `remote_semif.py` | buildbox, in the container | The adapter. `score` for authored144, `jevbench` for the JevBench harness. |
| `run-model.sh` | buildbox | Runs both tests for one model into `runs/<label>/`. Stops if the server has the wrong model. |
| `compare.py` | buildbox | Makes the comparison tables against the public references. Standard library only. |
| `runs/` | - | The results, copied back from the buildbox. `runs/invalid/` holds 2 runs that tested the wrong model (see below). |

## Pinned versions

| Item | Version |
|---|---|
| SemIf | commit `1f2dea3` (2026-09-22) |
| jevbench | commit `51a8d73` (2026-09-22), results revision v1.3.0 |
| llama.cpp (stock) on legion-t5 | `/opt/llama.cpp`, 0.3.0-dev commit `0f3a71be1` |
| llama.cpp (PrismML fork) on legion-t5 | `/opt/llama.cpp-prism`, release `prism-b10709-9a9394a`, CUDA 12.8 |

| Run label | GGUF on legion-t5 | Tokenizer (HF ID, revision) |
|---|---|---|
| `qwen3.5-4b-q4km` | `/opt/models/qwen3.5-4b.gguf` (bartowski Q4_K_M, the SemIf file, sha256 `13c16f42…`) | `Qwen/Qwen3.5-4B` `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` |
| `minicpm5-2b-q4km` | `/opt/models/minicpm5-2b.gguf` (openbmb Q4_K_M, the SemIf file, sha256 `ec2d5801…`) | `openbmb/MiniCPM5-2B` `12a3808a956f869c767195e9266b59c4d21d92e2` |
| `qwen3-0.6b-q8` | `/opt/models/qwen3-0.6b-q8_0.gguf` (Qwen Q8_0, the SemIf file, sha256 `9465e63a…`) | `Qwen/Qwen3-0.6B` `c1899de289a04d12100db370d81485cdf75e47ca` |
| `qwen3.5-2b-q4km` | `/opt/models/qwen3.5-2b.gguf` (bartowski Q4_K_M, rev `7d26695`, sha256 `57a10858…`) | `Qwen/Qwen3.5-2B` `15852e8c16360a2fea060d615a32b45270f8a8fc` |
| `qwen3.5-9b-q4km` | `/opt/models/qwen3.5-9b-standard.gguf` (bartowski Q4_K_M, sha256 `d784ce9e…`) | `Qwen/Qwen3.5-9B` `c202236235762e1c871ad0ccb60c8ee5ba337b9a` |
| `qwen3.5-4b-gsq-q2kxl` | `/opt/models/qwen3.5-4b-gsq-q2kxl.gguf` (Unsloth GSQ Q2_K_XL) | `Qwen/Qwen3.5-4B` `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` |
| `ternary-bonsai-2-27b-ptq1_0` | `/opt/models/ternary-bonsai-2-27b-ptq1_0.gguf` (prism-ml PTQ1_0), prism build | `Qwen/Qwen3.8-27B` `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` |

## Rebuild the test

Time: about 30 minutes for the setup, then about 10 minutes for each small model. Bonsai 27B takes longer.

1. On legion-t5, stop the embed and rerank services. They use port 11435 and the GPU.
   `sudo systemctl stop llama-embed.service llama-rerank.service`
   LiteLLM then sends embed and rerank calls to the gaming-b650 CPU fallback, which is about 10x slower.
2. Copy the scripts to legion-t5 and run the one-time install.
   `scp install-legion.sh serve-model.sh legion:semif-test/ && ssh legion bash semif-test/install-legion.sh`
3. On the buildbox, get the 2 upstream repos at the pinned commits, then build the image.
   ```sh
   mkdir -p /srv/semif-test/runs/invalid && cd /srv/semif-test
   git clone https://github.com/TheoLeeCJ/SemIf && git -C SemIf checkout 1f2dea3
   git clone https://github.com/fstandhartinger/jevbench && git -C jevbench checkout 51a8d73
   # copy Containerfile, remote_semif.py, run-model.sh and compare.py from this folder to /srv/semif-test
   podman build --network host -t localhost/semif-remote .
   ```
   The buildbox is an LXC without `/dev/net/tun`. Use `--network host` for each Podman command.
4. For each model, start the server on legion-t5, then run the tests on the buildbox.
   ```sh
   ssh legion bash semif-test/serve-model.sh /opt/models/qwen3.5-4b.gguf qwen3.5-4b
   ssh root@<BUILDBOX_IP> 'cd /srv/semif-test && EXPECT_GGUF=/opt/models/qwen3.5-4b.gguf \
     ./run-model.sh qwen3.5-4b-q4km Qwen/Qwen3.5-4B 851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a'
   ```
   For Bonsai, give `/opt/llama.cpp-prism` as the third argument of `serve-model.sh`.
5. Make the comparison tables.
   `ssh root@<BUILDBOX_IP> 'cd /srv/semif-test && python3 compare.py runs/<label> ...'`

## Invalid runs

The first 2 MiniCPM5-2B runs tested qwen3.5-4b by mistake. The first qwen3.5-4b server started by hand, without a PID file. The first version of `serve-model.sh` did not stop it, the new server could not use the port, and the health check reached the old server. `runs/invalid/` keeps these runs as evidence. Both scripts now prevent this: `serve-model.sh` stops every server on the port and checks the loaded file, and `run-model.sh` stops when `EXPECT_GGUF` does not match.
