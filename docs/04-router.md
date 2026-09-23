# 04 - The Jev model router

Sources:

- Video: [How to Build Things with Jev & OpenJevs](https://www.youtube.com/watch?v=ZR7anrL50xs), Sam Witteveen, 2026-09-21. The auto-generated transcript was fetched on 2026-09-22 with `youtube-transcript-api`.
- Copied router: `router/`, from prismhq/jev-router. See `router/UPSTREAM.md`.

## Status of the video code

On 2026-09-22 Sam Witteveen had not published the code.
The newest repo of GitHub user `samwit` is `tinker-cookbook` (2026-07-31). The last commit to `samwit/llm-tutorials` is from 2023-06-13.
In the video he says that he will record a code walkthrough on a second channel and then put the code on GitHub.

## The router in the video

### Parts

| Part | What |
|---|---|
| UI | A simple Next.js chat app. You can pick one model, or "auto". |
| Server | A local FastAPI server. One call decides, routes, and streams the answer back from the chosen model. |
| Judge | The Jev API (cloud), or SemIf (local, "open Jev"). You can switch between them in the UI. |
| Backends | All OpenAI-compatible endpoints. Jev is also called through this interface. |
| Storage | SQLite: messages, Jev decisions, and generated images. |
| Other | A fallback, health checks, a tool registry, editable routing thresholds, a system prompt field. |

### Models

| Model | Where | Role |
|---|---|---|
| MiniCPM5 2B | Local, on SGLang | Small model: chitchat, simple requests, all private requests. Also rewrites image prompts. |
| Qwen Image 2.1 | Local | Image generation and editing. Registered as a tool. Non-commercial license. |
| DeepSeek V4.1 Flash | Cloud, OpenRouter | Code and harder tasks. |
| DeepSeek Flash with web | Cloud, OpenRouter | Requests that need a web search. |
| Claude Opus 5 | Cloud, optional | "Hard" requests, when you turn it on. |

He says that you can also use LM Studio or Ollama for the local models.

### What Jev classifies

All questions go in one request against the same state. Jev answers them in parallel, so more questions cost about the same time as one.
The state is the conversation. The instruction is "judge the latest message in the context of the conversation".

| Question | Type | Options | Use |
|---|---|---|---|
| Lane | `choice` | chitchat, simple question, rewrite/summarize, code, reasoning/analysis, image | Picks the lane (the model group). |
| Difficulty | `score` | trivial, easy, moderate, hard (up to frontier) | "How much model capability does a good answer need?" Moves the request up a tier inside a lane. |
| Private | `null` (yes/no) | true / false | Personal, confidential, client, financial, medical, or credential data (API keys, passwords). |
| Web | `null` (yes/no) | true / false | The request needs web data. |

Each answer comes back with probabilities and a confidence value.

### How a model is picked

1. The server asks the judge the 4 questions.
2. The lane answer selects a lane. Each lane has a fixed, ordered list of preferred models.
3. Rules then change the choice. The video shows these:
   - Private probability above 0.5: use a local model, always.
   - Web above a threshold: use the web-enabled model.
   - Prompt over 16,000 tokens: use a general model.
   - Difficulty "hard" and Opus is on: use Opus first, else DeepSeek.
4. Low confidence: do not guess. Use a safe default.
5. Stream the answer from the chosen model. On error, use the fallback.

Image requests go to Qwen Image, after MiniCPM rewrites the prompt.

Measured in the demo: the Jev call took 331 ms. SemIf took 88 ms, local.

### Privacy

With the cloud Jev, the prompt goes to TypeSafe before the router decides that it is private. The prompt has already left the machine.
With SemIf as the judge, the whole router runs locally.

### Stats

The UI shows: request count (53 in the demo), share answered locally (75%), money spent on Jev and DeepSeek, money saved by the local share, judge response times (Jev or SemIf), and the count of private prompts.

## Community routers compared

Checked 2026-09-22 with `gh api` and a shallow clone of each.

| Repo | Lang | Stars | Code | Last commit | License | Shape |
|---|---|---:|---:|---|---|---|
| **prismhq/jev-router** (copied) | Python | 8 | ~340 lines | 2026-09-16 | MIT | LiteLLM proxy hook. One `choice` question picks a model. |
| rajdhakad9826/jev-router | TypeScript | 8 | ~180 lines | 2026-09-21 | MIT | Library. Picks one of 2 or 3 tiers. Does not call the model. |
| BillionsBobby/JevRouter | TypeScript | 163 | ~4,300 lines | 2026-09-21 | MIT | Routes agent capabilities: models, tools, skills, subagents. |
| gargpratyush/jev-router | JavaScript | 329 | ~2,300 lines | 2026-09-19 | MIT | Per-turn model pick inside Claude Code and Codex CLIs. |
| reallygood83/jev-router | Python | 7 | ~5,200 lines | 2026-09-21 | MIT | Gate in front of OpenCodex, with a GUI. |
| Pinutss/jev-model-router | Python | 4 | ~2,700 lines | 2026-09-18 | MIT | Catalog ranker with a local heuristic, HTTP and MCP. Does not proxy. |

Other Jev routers exist, but they target one agent (Pi, Codex, Hermes, Hono). They are not general API routers.

No router supports SemIf or another open Jev-style model. SemIf is a CLI scorer (`semif-score`). It has no HTTP server, and its input shape (`state`, `question`, `options`) differs from the Jev API.

### Why prismhq/jev-router

- It is the smallest router that also forwards the call.
- It is Python and OpenAI-compatible, like the video.
- It is built on LiteLLM, which is already the local gateway.
- It works without a TypeSafe key, with a local cheapest-model rule.

## Gap: video router vs the copied router

| Feature | Video | prismhq/jev-router |
|---|---|---|
| Lane (`choice`) | Yes, 6 task classes | Yes, but the options are the model names |
| Difficulty (`score`) | Yes | No |
| Private gate (`null`) | Yes, forces local | No |
| Web gate (`null`) | Yes | No |
| Confidence threshold | Yes | No. It uses only the top choice. |
| Capability filter | Not shown | Yes: vision, tools, max output |
| Fallback | Yes | Yes, on any error or unknown choice |
| Local judge (SemIf) | Yes | No. The Jev URL is a code constant. |
| Stats, SQLite log | Yes | No. LiteLLM spend logs can cover part of this. |
| UI | Next.js | None. Use any OpenAI client. |

To match the video, the router needs a new decider that asks the 4 questions, applies the rules, and can call a local SemIf service. That is a code change. It is not done here.

## How to run it against the LiteLLM gateway

Do this as config only. Do not change the router code.

Recommended: run the router as its own small LiteLLM instance. Its pool entries point at the gateway at `http://<LITELLM_IP>:4000`. The gateway then serves the local models.

1. Create a LiteLLM virtual key on the gateway for this consumer, with `key_alias: jev-router`. Do not use the master key.
2. Put the key in gopass, and export it in the shell as `JEV_ROUTER_GATEWAY_KEY`. Do not write it into a repo file.
3. List the model names that the gateway serves:
   ```bash
   curl -s http://<LITELLM_IP>:4000/v1/models -H "Authorization: Bearer $JEV_ROUTER_GATEWAY_KEY"
   ```
4. Replace `model_list` in `router/config.yaml`. Each entry forwards to the gateway:
   ```yaml
   model_list:
     - model_name: jev-router          # the id clients send; points at the fallback
       litellm_params:
         model: openai/<gateway-model-small>
         api_base: http://<LITELLM_IP>:4000/v1
         api_key: os.environ/JEV_ROUTER_GATEWAY_KEY
     - model_name: local-small
       litellm_params:
         model: openai/<gateway-model-small>
         api_base: http://<LITELLM_IP>:4000/v1
         api_key: os.environ/JEV_ROUTER_GATEWAY_KEY
     - model_name: local-large
       litellm_params:
         model: openai/<gateway-model-large>
         api_base: http://<LITELLM_IP>:4000/v1
         api_key: os.environ/JEV_ROUTER_GATEWAY_KEY

   litellm_settings:
     callbacks: jev_router.hook.proxy_handler_instance
     drop_params: true

   general_settings:
     master_key: os.environ/LITELLM_MASTER_KEY
   ```
5. Replace `candidates` in `router/router.yaml`. Each `name` must match a `model_name` above. Set `fallback` to one of them, for example `local-small`. The `description` text is what Jev reads, so describe what each model is good at. Set `price_in` and `price_out` (EUR or USD per 1M tokens). The no-key rule picks the lowest sum.
6. Set `LITELLM_LOCAL_MODEL_COST_MAP=True` to stop the price map fetch from GitHub.
7. Start it on another port, for example `litellm --config config.yaml --port 4100`, from the `router/` folder. Clients call `model: "jev-router"`.

Alternative: load the hook into the gateway itself. Add `jev_router.hook.proxy_handler_instance` to the gateway `callbacks`, and put `router.yaml` on the gateway host. This needs the package on the gateway host. It changes a live service, so it is not the first choice.

## Environment variables and keys

| Variable | Needed | Use |
|---|---|---|
| `TYPESAFE_API_KEY` | Optional | Turns on Jev. Without it, the cheapest-eligible rule picks, and no data goes to TypeSafe. |
| `JEV_ROUTER_GATEWAY_KEY` | Yes, with the gateway setup | Virtual key for the LiteLLM gateway. Name it in `config.yaml`. The upstream `config.yaml` uses `OPENROUTER_API_KEY` instead. |
| `LITELLM_MASTER_KEY` | Yes | The key that clients send to this router. The upstream file hardcodes `sk-jev-router`. Replace it. |
| `JEV_ROUTER_CONFIG` | Optional | Path to the routing policy. Default `router.yaml` in the working folder. |
| `LITELLM_LOCAL_MODEL_COST_MAP` | Recommended | `True` stops LiteLLM from fetching its price map. |

Privacy: with `TYPESAFE_API_KEY` set, the last 8 messages (up to 2,000 characters each, system messages too) go to `api.typesafe.ai` on every routed request. Do not set it for private data.
