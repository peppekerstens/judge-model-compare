# The llama.cpp fork with Jev support (`parallel-decision`)

A fork of llama.cpp by Codacus adds a Jev-style decision endpoint to llama-server. This folder holds the container build, the deploy script and the live security test. The full code audit is in `../../docs/08-codacus-llama-fork.md`.

Source: [thecodacus/llama.cpp, branch `parallel-decision`](https://github.com/thecodacus/llama.cpp/tree/parallel-decision). Video: [Can You Run Any LLM in Jev Mode Using llama.cpp?](https://www.youtube.com/watch?v=bcGO7xre46o) (Codacus, 2026-09-21).

State on 2026-09-23: the build works, and the live network test is clean. The endpoint answers. The judge service and the quality test are open.

## What the fork adds

| Point | Detail |
|---|---|
| Endpoint | `POST /decision` and `POST /v1/decision` on llama-server |
| Request | `instructions`, a `schema` of 1 to 32 typed fields, and `contexts` of 1 to 256 strings |
| Field types | `boolean`, `enum` (1 to 255 choices), `integer`, `number` |
| Answer | A value for each field, plus a probability normalized over the allowed values of that field only |
| Method | It prefills the schema once and caches it, then scores every allowed value as a token path from the same KV cells, in one `llama_decode` |
| New CLI | `llama-parallel-decision` |
| Switch | `--decision-seqs N`, with N of 3 or more. The endpoint answers HTTP 400 without it |
| Model | Any GGUF works. The fork needs no special model |
| Diff size | 2 commits on upstream master, 14 files, 1,332 added lines |

## Why it beats our method

Our judge asks 2 questions in 2 calls. It reads the log-probabilities of the letters A, B and C from the stock `/completion` endpoint, and it renormalizes them by hand.

| Point | Our method | The fork |
|---|---|---|
| Calls per request | 2 | 1 |
| Prefills | 2 of the same instructions | 1, and the result stays in the cache |
| Answer values | Letters, because a word spans several tokens | The real words, through a token trie |
| Probabilities | Over the letters that reach the top 200 tokens | Over the allowed values only, always complete |
| Missing option | Possible, when a letter falls outside the top 200 | Not possible |

## Security audit

Static audit of 2026-09-23, on commit `14d04e75`. The result: **the diff adds no outbound network call.**

| Check | Result |
|---|---|
| All 1,526 diff lines read | 6 network-shaped hits: 2 inbound route registrations, 1 handler declaration, 1 handler body, 1 `curl` example against localhost in the README, and 1 documentation link |
| New dependency | None. All 17 new includes are standard C++ or existing llama.cpp headers |
| Binary blob, CI change, install script | None |
| New inbound surface | 2 POST routes, off unless you pass `--decision-seqs N` |
| Provenance | 1 author, unsigned commits, no pull request to upstream, 98 commits behind master, issues disabled, 313 stars. This is the weak point |
| Side effect | `--decision-seqs N` forces the unified KV cache for the whole server, and it raises `n_seq_max` |
| Model repository | `harshatheg/Qwen-2.5-1B-RLCD` holds no weights, only 132 KB of code, Apache-2.0. We do not use it |

Our build closes 1 more path: `-DLLAMA_CURL=OFF` removes the model download code, so the binary cannot fetch a model over the network.

### The live network test, 2026-09-23

`security-test.sh` ran all 3 parts against the built image. The result is clean.

| Part | Result |
|---|---|
| 1. No network at all (`--network none`) | The server started and answered inside the container: `difficulty "simple"`, probability 0.9978, total 150 ms |
| 2. Host network, with `strace` on every network call and file open | 0 `connect()` calls, and 0 opens of `/etc/resolv.conf` or `/etc/hosts`. The answer came back correctly |
| 3. Packet capture on the host during a call | 0 DNS packets, and 0 outgoing TCP handshakes |

The evidence stays in `~/decision-fork/audit/` on legion-t5: `no-network.json`, `host-network.json`, `strace.log` and `capture.pcap`.

The runtime test matches the static audit: the fork makes no outbound call.

## Install and run

Everything happens in Podman on legion-t5. No toolchain lands on the host.

```sh
./build-legion.sh build    # copy, then build the image (30 to 60 minutes)
./security-test.sh         # the live network test. Run this before any real use
./build-legion.sh run      # serve qwen3.5-4b on port 11436 with the GPU
./build-legion.sh test     # one /v1/decision call, to prove the endpoint answers
./build-legion.sh stop     # stop and remove the container
```

| Point | Value |
|---|---|
| Image | 2 stages. The build stage uses `nvidia/cuda:12.8.1-devel-ubuntu24.04` and is about 6 GB. The final image keeps the CUDA runtime and the binaries |
| CUDA flags | `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=86` for the RTX 3060 Ti (Ampere) |
| Pinned commit | `14d04e755fa28653e87b9a07072892265bdc0fad`, 2026-09-20. A rebuild gives the same code |
| Model mount | `/opt/models` from the host, read only |
| Port | 11436 on legion-t5. That port belongs to `llama-rerank.service`, which is stopped. The firewall already allows it |
| Server flags | `--decision-seqs 3 --n-gpu-layers 99 --ctx-size 8192 --parallel 1 --flash-attn on` |
| VRAM limit | Qwen3.5 is a hybrid attention model. Its recurrent-state cache scales with the sequence count. With 24 sequences and 16,384 tokens the 8 GB card fails with `failed to allocate buffer for rs cache`. 3 sequences and 8,192 tokens work next to the 4B judge |

The container writes the fork commit into `/opt/llama-decision/BUILD_COMMIT.txt`, and `build-legion.sh build` prints it.

## Example call

```sh
curl -s http://<LEGION_IP>:11436/v1/decision -H 'Content-Type: application/json' -d '{
  "instructions": "Answer both questions about the request.",
  "schema": {
    "difficulty": {"type": "enum", "choices": ["simple", "medium", "hard"]},
    "sensitive": {"type": "boolean"}
  },
  "contexts": ["What is the capital of France?"]
}'
```

## Files

| File | What |
|---|---|
| `Containerfile` | The 2-stage CUDA build of the fork, with the commit pinned and `LLAMA_CURL=OFF` |
| `build-legion.sh` | `build`, `run`, `stop` and `test` on legion-t5 |
| `security-test.sh` | The live network test in 3 parts. The evidence lands in `~/decision-fork/audit/` on legion-t5 |
| `audit-privileged.sh` | Part 2 and part 3 of that test. They need root on legion-t5, so this file runs there |

## What the build taught us

1. The CUDA devel image ships the driver API as a stub only. The link fails with `undefined reference to cuMemCreate` until the stub folder sits on the link line. The Containerfile adds `LIBRARY_PATH`, a `libcuda.so.1` symbolic link, and the linker flags.
2. The CUDA runtime image has no OpenMP. Without `libgomp1` the server stops with `error while loading shared libraries: libgomp.so.1`.
3. Every field of the schema needs a `description`. Without it the server answers HTTP 400 with `field "x" needs a description`.
4. `--decision-seqs 24` does not fit the 8 GB card with this model. The default is 3 sequences and 8,192 tokens.

## Speed of one call, 2026-09-23

| Step | Time |
|---|---|
| Prefill | 129 ms |
| Scoring | 20 ms |
| Total for 1 field and 1 context | 150 ms |

Our letter method needs 2 calls and about 500 ms for the same 2 questions. The fork answers both fields in 1 call. The quality test must confirm that.

## Open points

1. The judge service for `/v1/decision` does not exist yet. It must speak the same `/v1/systemone` shape as the other judges.
2. The quality test with qwen3.5-4b, against our letter method, is open. The same 24 bench cases apply.
3. `--decision-seqs` changes the KV cache of the whole server. Do not put this build under the production tiers before the test finishes.
4. The Vulkan path for gaming-b650 is not tested.
5. The port 11436 belongs to `llama-rerank.service`. At a reboot of legion-t5 that service takes the port back.
