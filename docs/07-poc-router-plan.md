# Stage 1: proof of concept for a Jev-style router (2026-09-23)

Goal: show that a local judge model can route each request to the right model. Stage 1 stays separate from the gateway on LXC 109.

## Decisions

| Point | Choice | Why |
|---|---|---|
| Judge | The adapter `semif-test/remote_semif.py`, wrapped in a small HTTP service | It is measured (0.913 on authored144, 81.8 % on JevBench). SemIf has no server, and PR #27 is open |
| Judge model | Qwen3.5-4B Q4_K_M in llama-server on legion-t5, port 11434 | It wins the judge bench of 2026-09-23: 23 of 24 cases, and faster than the 9B model |
| Router | A standalone FastAPI proxy. It holds the decision code of prismhq/jev-router | The demo router is a LiteLLM hook without a web interface |
| Rules | The sensitivity check runs first. Sensitive data never goes to the cloud | The choice of peppe |
| Cloud tier | Only in the proof of concept | The gateway on LXC 109 stays untouched |

## Routing rules

1. The judge gets 2 questions for each request: a `noul` question for sensitive data, and a `choice` question for the difficulty.
2. Sensitive data (personal data, secrets, internal facts): the request goes to `qwen3.8-27b-local`.
3. No sensitive data, and the difficulty is:
   - simple: `qwen3.8-27b-nothink` (reasoning off, the fastest local tier)
   - medium: `qwen3.8-27b-local` (reasoning low)
   - hard: `qwen3.7-max` in the cloud (OpenCode Go)

## Parts

| Part | Where | Port | Content |
|---|---|---|---|
| Judge model | legion-t5, <LEGION_IP> | 11434 | llama-server with Qwen3.5-4B Q4_K_M, 3,568 MiB VRAM |
| LXC 110 `jev-poc` | pve2, <POC_IP> | - | Debian 13, Docker, 4 cores, 4 GB RAM, 20 GB disk |
| Container `semif-judge` | LXC 110 | 8080 | The judge service. It speaks the TypeSafe `/v1/systemone` shape |
| Container `jev-router` | LXC 110 | 8081 | The proxy: `/v1/chat/completions`, plus the web page with the decision log |

## Targets of the router

| Name | Backend | Note |
|---|---|---|
| `qwen3.8-27b-nothink` | gaming-b650, <GAMING_IP>:11434 | `reasoning_effort: none` |
| `qwen3.8-27b-local` | gaming-b650, <GAMING_IP>:11434 | `reasoning_effort: low` |
| `qwen3.7-max` | `https://opencode.ai/zen/go/v1` | Cloud. Key `OPENCODE_GO_API_KEY` from gopass |

The proof of concept calls the model backends directly. It does not use the gateway on LXC 109.

## Steps

| # | Step | State |
|---|---|---|
| a | Stop the reranker and the embedder on legion-t5, until the next reboot | done 2026-09-22, and again on 2026-09-23 after the reboot |
| b | Serve Qwen3.5-9B Q4_K_M on legion-t5 | done 2026-09-22, port 11434. Started again on 2026-09-23 after a reboot of legion-t5 |
| c | Create LXC 110 with Docker | done 2026-09-23 |
| d | Build and start the judge container | done 2026-09-23 |
| e | Build and start the router container, and publish the endpoints | done 2026-09-23 |
| f | Add the `qwen3.7-max` target with the OpenCode Go key | done 2026-09-23 |
| g | Run the test examples, one for each route | done 2026-09-23, 5 of 5 correct |

## Limits of stage 1

- Only one judge model. There is no fallback when legion-t5 stops.
- No authentication on the 2 endpoints. The proof of concept runs on the LAN only.
- The judge adds one call to each request. I measured 0.60 s for both questions with the 4B model.
- A request that goes to the cloud leaves your network. The sensitivity check is the only guard, and it is not perfect.

## Result of stage 1

The router runs. All 5 test examples take the right route. The numbers and the rebuild steps are in `../poc/README.md`.

The cloud target needs the header `x-opencode-session`. OpenCode Go refuses a request without it. The gateway on LXC 109 sends the same header.

Added on 2026-09-23, after the first test: `stream: true` works. The router passes every event through, and the route travels in the response headers. See `../poc/README.md`.

That file also holds 3 diagrams: the rules, a normal request, and a stream.

The judge changed to Qwen3.5-4B Q4_K_M on 2026-09-23, after the judge bench. See `../poc/results/README.md`.

## State on 2026-09-23, end of the day

| Part | State |
|---|---|
| The router with the judge, the rules and the log page | Runs. 7 of 7 route tests correct, and streaming works |
| Judge candidates measured | 4: Qwen3.5-2B, 4B and 9B with the letter method, and the same 4B on the llama.cpp fork |
| Laya multilingual | Measured on the CPU and on the GPU. 4 of 24 cases right, so it is not usable |
| Needle 3 | Tested on 2026-09-24 and closed. It reads 0 and 1 of 24 cases right |
| The judge of the router | Qwen3.5-4B with the letter method. It reads 23 of 24 cases right |

The next steps are in `06-test-log.md`, section "Work still to do".
