# Upstream

| Field | Value |
|---|---|
| Source | https://github.com/prismhq/jev-router |
| Commit | `583f0a1d1e0534cda3b6bbfa4b19aa1ec25d73a7` (2026-09-16T18:51:29-07:00) |
| Copied | 2026-09-22, from a `git clone --depth 1`. The `.git` folder is not copied. |
| License | MIT, Copyright (c) 2026 Prism Technologies Inc. See `LICENSE`. |
| Changes | None. The files are identical to the upstream commit. Only this file is new. |

The 11 upstream unit tests pass offline (`python3 -m unittest tests.test_deciders`). They use a fake fetch and make no network call.

## Why this one

The video router is a small Python API server. It asks Jev a set of typed questions and then sends the request to an OpenAI-compatible backend.
prismhq/jev-router is the closest open match:

- It is small: 4 Python files, about 340 lines.
- It is Python, like the FastAPI server in the video.
- It runs as a LiteLLM proxy hook. Clients send `model: "jev-router"` to an OpenAI-compatible endpoint. The user already runs LiteLLM as the gateway.
- It asks Jev one `choice` question over the candidate models, reads the answer, and falls back to a fixed model on any error.
- It runs without a TypeSafe key. Then a local rule picks the cheapest eligible model, and no request data leaves the process.

The other candidates, and why they lost:

| Repo | Stars | Code | Why not |
|---|---:|---:|---|
| rajdhakad9826/jev-router | 8 | ~180 lines TS | A TypeScript library. It returns a model name only. No proxy, no backend call. |
| BillionsBobby/JevRouter | 163 | ~4,300 lines TS | Routes agent capabilities (tools, skills, subagents). Much larger scope than the video. |
| gargpratyush/jev-router | 329 | ~2,300 lines JS | Wraps the Claude Code and Codex CLIs. Not an API router. |
| reallygood83/jev-router | 7 | ~5,200 lines Python | A gate in front of OpenCodex, with a Korean GUI. Needs OpenCodex. |
| Pinutss/jev-model-router | 4 | ~2,700 lines Python | A model catalog ranker with MCP and a demo UI. It picks a model but does not proxy the call. |

All five have an MIT license. None of the six supports SemIf or another open Jev-style model.

## Security read

Read of every file at the commit above.

### Outbound network calls

| Where | Host | Key | When |
|---|---|---|---|
| `jev_router/deciders.py`, `JevDecider` | `https://api.typesafe.ai/v1/systemone` (hardcoded constant `TYPESAFE_URL`) | `TYPESAFE_API_KEY`, sent as `Authorization: Bearer` | Only when `TYPESAFE_API_KEY` is set. One POST per routed request. Timeout 5 s. |
| LiteLLM proxy (not this code) | The `api_base` of each `model_list` entry in `config.yaml`. The default is OpenRouter. | `OPENROUTER_API_KEY`, or the key set per model | Every request, to the chosen model. |

What goes to TypeSafe: the last 8 messages, each cut to 2,000 characters, with their roles. This includes `system` messages. It also sends 3 flags: image present, tools present, message count. Images are replaced by the text `[image]`. Tool definitions are not sent.

### Telemetry

- The router code has no telemetry, no analytics, and no logging calls.
- LiteLLM itself is a dependency. By default it can fetch its model price map from GitHub at startup. Set `LITELLM_LOCAL_MODEL_COST_MAP=True` to stop that. Check the other LiteLLM settings for the installed version before you run it. This read does not cover LiteLLM.

### Install scripts and hooks

- `pyproject.toml` uses plain setuptools. There is no `setup.py`, no build hook, and no postinstall script.
- Dependencies: `litellm[proxy]>=1.60.0`, `pyyaml>=6.0`. The LiteLLM version is not pinned.
- No shell scripts, no Dockerfile, no CI files.

### Other findings

- `config.yaml` sets `master_key: sk-jev-router`. This is a public, weak default. Replace it before you expose the proxy on a network.
- `load_config` uses `yaml.safe_load`. Good.
- The hook catches every exception and sends the request to the fallback model. A broken Jev call does not block traffic. It also hides errors, because nothing is logged.
- The Jev endpoint is a code constant. To use a local Jev-style model such as SemIf, you must change code (a new decider). Config alone cannot do it.
