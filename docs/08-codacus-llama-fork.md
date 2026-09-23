# 08 - Codacus llama.cpp fork: `parallel-decision`

Research date: 2026-09-23. Read-only. Nothing was built, run, or installed.

Subject: the llama.cpp fork shown in "Can You Run Any LLM in Jev Mode Using llama.cpp?"
(Codacus, 2026-09-21, <https://www.youtube.com/watch?v=bcGO7xre46o>).

The video transcript was fetched with `youtube-transcript-api` and is quoted where it adds facts
the code does not state.

Sources used:

| What | URL |
|---|---|
| Fork branch | <https://github.com/thecodacus/llama.cpp/tree/parallel-decision> |
| Diff (2 commits) | <https://github.com/thecodacus/llama.cpp/compare/60b06ab9a9eeec26f8125c9316ccbf4ee4713d1f...14d04e755fa28653e87b9a07072892265bdc0fad> |
| Branch README | <https://github.com/thecodacus/llama.cpp/blob/parallel-decision/tools/parallel-decision/README.md> |
| Playground | <https://github.com/thecodacus/decision-playground> |
| HF repo `Qwen-2.5-1B-RLCD` | <https://huggingface.co/harshatheg/Qwen-2.5-1B-RLCD> |
| Video | <https://www.youtube.com/watch?v=bcGO7xre46o> |

---

## 1. What it adds

### Scope of the diff

The fork's default branch is `perf` and carries other experimental work. The `parallel-decision`
branch does **not** sit on `perf`. It sits directly on upstream `ggml-org/llama.cpp` master.

| Fact | Value | Source |
|---|---|---|
| Merge base with upstream master | `60b06ab9` ("metal : fix FA support checks (#29122)", Georgi Gerganov, 2026-09-19) | `gh api repos/ggml-org/llama.cpp/compare/master...thecodacus:llama.cpp:parallel-decision` |
| Commits ahead of the merge base | 2 | same |
| Commits behind upstream master (2026-09-23) | 98 | same |
| Files changed | 14 (9 modified, 5 new) | `gh api .../compare/60b06ab9...14d04e75` |
| Diff size | 1,526 lines, +1,332 / -2 | downloaded `.diff` |
| Head commit | `14d04e75`, 2026-09-20 10:28 UTC, "parallel-decision : add README" | <https://github.com/thecodacus/llama.cpp/commits/parallel-decision> |
| Other commit | `b9244f89`, 2026-09-19, "server : add /v1/decision for parallel constrained decisions" | same |

Both commits carry `Assisted-by: Claude Opus 5` in the message.

### Changed files

| File | Change | What it does |
|---|---|---|
| `common/arg.cpp` | +10 | New flag `--decision-seqs N` (env `LLAMA_ARG_DECISION_SEQS`), server only, minimum 3, default 0 = off |
| `common/common.h` | +1 | New field `int32_t n_seq_decision` |
| `common/common.cpp` | +1 / -1 | `cparams.n_seq_max = params.n_parallel + params.n_seq_decision` |
| `tools/CMakeLists.txt` | +1 | `add_subdirectory(parallel-decision)` |
| `tools/parallel-decision/CMakeLists.txt` | new, 15 | Static lib `llama-decision`, binary `llama-parallel-decision` |
| `tools/parallel-decision/decision-engine.h` | new, 142 | Engine and schema-compiler API |
| `tools/parallel-decision/decision-engine.cpp` | new, 729 | The whole algorithm |
| `tools/parallel-decision/parallel-decision.cpp` | new, 161 | Standalone CLI / stdin-stdout worker |
| `tools/parallel-decision/README.md` | new, 132 | Documentation |
| `tools/server/CMakeLists.txt` | +1 / -1 | Link `llama-decision` into llama-server |
| `tools/server/server-task.h` | +12 | New task type and result type |
| `tools/server/server-context.h` | +1 | New route handler field |
| `tools/server/server-context.cpp` | +116 | `handle_decision()`, task dispatch, route lambda |
| `tools/server/server.cpp` | +10 | Route registration, unified-KV switch, router proxy entry |

No CI workflow, no shell script, no Python file, no binary blob, and no new third-party dependency
change. Verified: the compare API file list contains no `.github/`, `.yml`, `.sh`, `.py`, or binary
file, and the diff contains no `Binary files` or `GIT binary patch` marker.

### The new API

It provides **three** entry points, all on the same engine.

**1. llama-server HTTP endpoint** — `POST /decision` and `POST /v1/decision`
(`tools/server/server.cpp`, added lines ~280-281).
It is off by default. It returns HTTP 400 unless the server starts with `--decision-seqs N`, N >= 3
(`tools/server/server-context.cpp`, added lines ~2381-2383).

Request shape (`tools/server/server-context.cpp` ~2380-2454, and the branch README):

```json
{
  "model": "gemma-4-12b",
  "instructions": "Answer each question about this support request from its state.",
  "schema": {
    "category": {"type": "enum", "choices": ["billing","technical"], "description": "..."},
    "urgent":   {"type": "boolean", "description": "..."}
  },
  "contexts": ["I was charged twice and need this fixed today."],
  "mode": "auto",
  "tree_max": 128,
  "cache_prompt": true
}
```

- `contexts` is an array of 1 to 256 non-empty strings. Results come back in the same order.
- `schema` accepts compact field specs, or a JSON Schema object with `properties`. 1 to 32 fields.
- Field types: `boolean`, `enum` (1-255 string choices), `integer` (min/max, 1-255 values),
  `number` (min/max/step, fixed-width decimals, 1-255 values). Numeric fields accept
  `aggregate: mode | median | mean`.

Response shape (branch README, and `assemble()` in `decision-engine.cpp`):

```json
{
  "object": "decision",
  "results": [{
    "decision": {"category": "billing", "urgent": true},
    "fields": {
      "category": {"value": "billing", "probability": 1.0, "scored_nodes": 1, "tree": true},
      "urgent":   {"value": true, "probability": 1.0, "scored_nodes": 1, "tree": true}
    },
    "usage": {"context_tokens": 21, "scored_rows": 14}
  }],
  "usage": {"prompt_tokens": 137, "cached_tokens": 116, "context_tokens": 21, "scored_rows": 14},
  "timings": {"prefill_ms": 50.7, "scoring_ms": 50.0, "total_ms": 100.7, "rounds": 1,
              "per_decision_ms": 100.7}
}
```

**Yes, it returns a probability per field.** `probability` is the probability of the winning value,
normalised over the field's allowed values only. Numeric fields also get `interval_p10_p90`
(`decision-engine.cpp`, `assemble()`).

Caveat: the HTTP response returns only the **winner's** probability, not the full vector over all
choices, even though the engine computes the full vector in tree mode
(`field_result::probs` in `decision-engine.h`). An open PR inside the fork,
[#13 "parallel-decision: expose exact tree distributions"](https://github.com/thecodacus/llama.cpp/pull/13)
(opened 2026-09-22, base `parallel-decision`, 8 files, +171/-7), adds the full per-choice map.
That PR is **not merged** into `parallel-decision` as of 2026-09-23.

**2. CLI binary** — `llama-parallel-decision`
(`tools/parallel-decision/parallel-decision.cpp`). It reads one tab-separated request per line on
stdin and writes a result plus `WORKER_DONE` on stdout. Its protocol is deliberately compatible
with "llama-mojo's decide-worker" (file header comment). It reads plain files named on the request
line, so the caller must place the schema and the context on disk first. Tuned by environment
variables `DECIDE_TREE`, `DECIDE_TREE_MAX`, `DECIDE_NSEQ`, `DECIDE_SPLIT_BOUNDARY`.

**3. Library** — the static library `llama-decision` exports
`llama_decision::engine`, `compile_schema()`, `render_prompt()`, and `assemble()`
(`decision-engine.h`). The server links it. Any C++ caller can link it too.

### How it builds the prompt

`compile_schema()` in `decision-engine.cpp` builds one system text:

```
Select the requested field value from its allowed values, based on the context.
Respond with the JSON value only.

Fields:
"category": What type of support request is this?
Allowed values: "billing", "technical"
...
<instructions>
```

`render_prompt()` then applies the model's own chat template with thinking disabled, using a
sentinel string to split the rendered prompt into two parts:

- **static prefix** — everything up to the user message. This is cached on its own sequence
  (`seq_snap`) and reused across requests.
- **per-request part** — the context, the generation prompt tail, and the literal `{\n` that opens
  the JSON answer.

If no chat template exists, it falls back to `system_text + "\nContext:\n"` and
`context + "\nOutput:\n{\n"`.

For each field it then appends a suffix like `  "category": ` and scores the allowed values as token
paths that fork from the same KV cells. Each branch gets its own sequence id via
`llama_memory_seq_cp()`, so all fields are scored in **one** batched `llama_decode`
(`engine::score_branches`, `decision-engine.cpp`).

Two scoring modes:

| Mode | What it does |
|---|---|
| `tree` | Scores every divergence node of the field's token trie at once, then sums log-softmax along each candidate path. Gives the exact constrained distribution. |
| `greedy` | Walks the trie one divergence at a time. More rounds, no exact distribution. |
| `auto` (default) | `tree` when the field has <= `tree_max` (128) values, else `greedy`. |

One tokenisation detail matters, and the video calls it the bug that skewed the first version:
the code tokenises the whole `suffix + value + "\n"` string and splits at the longest token prefix
common to every candidate, so the value's first token is exactly the token the model would write
itself (comment in `decide_batch`, `decision-engine.cpp`). The old behaviour is still reachable
with `DECIDE_SPLIT_BOUNDARY=1` and is labelled "legacy".

**Limitation, stated by the author:** the fields cannot see each other. Every field is scored from
the same context, so no field can condition on another field's answer. The video says the plain
autoregressive model beat decision mode on a 30-field schema where rules depended on other answers,
and that Typesafe give the same advice for Jev ("use this for questions that do not depend on each
other").

---

## 2. How to build it

### CMake

Nothing new. The branch README says the build is the same as stock llama.cpp:

```bash
cmake -B build -DGGML_CUDA=ON        # or plain `cmake -B build` for CPU / Metal
cmake --build build --config Release -j
```

The new `tools/parallel-decision/CMakeLists.txt` adds a static library and one executable and links
only `llama-common` and `llama`. It requires C++17, which stock llama.cpp already uses. It sets
`POSITION_INDEPENDENT_CODE ON` so llama-server can link it into `libllama-server-impl`.

No `find_package`, no `FetchContent`, no `ExternalProject`, no `GIT_REPOSITORY`, no vendored
third-party source. Verified by grepping the added lines of the diff.

### Binaries

| Binary | Notes |
|---|---|
| `llama-server` | Gains `/decision` and `/v1/decision`. Everything else is unchanged. |
| `llama-parallel-decision` | New. Installed when `LLAMA_TOOLS_INSTALL` is on. |

### Runtime flags

| Flag | Meaning |
|---|---|
| `--decision-seqs N` | Sequences reserved above the slots. N = 0 disables the endpoint. Minimum 3 (cached prefix, trunk, one branch). README suggests 24, or 12 for a sliding-window model on a 12 GB card. |

Two side effects, both important for a shared server:

1. `--decision-seqs N` **forces the unified KV cache on** for the whole server process:
   `params.kv_unified = true` in `tools/server/server.cpp`, added lines ~160-166. The server logs
   `--decision-seqs N: enabling the unified KV cache`. This changes KV behaviour for the chat slots
   too.
2. `n_seq_max` becomes `n_parallel + n_seq_decision` (`common/common.cpp`, line ~1722), so the
   context allocates more sequences.

The README states the memory cost depends on attention type: a plain-attention model shares the
context cells so 128 sequences cost almost nothing, while a sliding-window model (Gemma) allocates
its window per sequence.

### Does it need a custom model?

**No.** Any GGUF that llama.cpp can load works. The branch README example uses
`gemma-4-12b-it-UD-Q4_K_XL.gguf`. The video says the same: "Anything llama.cpp can load will work
here. So grab a gguf you already like."

The engine only calls `llama_decode`, `llama_memory_seq_cp`, `llama_memory_seq_rm`, and
`llama_get_logits_ith`. It never touches a backend directly, so CUDA, Vulkan, ROCm, Metal, and CPU
should all work. Not verified by running.

### What `harshatheg/Qwen-2.5-1B-RLCD` adds

Nothing to the llama.cpp fork. It is a **different, earlier project**, and it is the project the
video credits as the origin of the idea.

| Fact | Value | Source |
|---|---|---|
| License | Apache-2.0 | <https://huggingface.co/api/models/harshatheg/Qwen-2.5-1B-RLCD> |
| `library_name` | `mlx` (Apple Silicon) | same |
| Last modified | 2026-09-16 | same |
| Likes / downloads | 558 / 0 | same |
| Total repo size | **132 KB across 26 files** | HF tree API, `?recursive=true` |
| Model weights present | **None.** No `.safetensors`, no `.gguf`, no `.bin`. | same |
| What it actually contains | `app.py`, `Dockerfile`, `run.sh`, `core/engine_mlx.py`, `core/engine_torch.py`, `core/schema.py`, `core/prompt_builder.py`, 4 JSON presets, a small web UI | same |
| Base model it loads at runtime | `mlx-community/Qwen2.5-1.5B-Instruct-4bit` (stock Qwen 2.5 1.5B Instruct) | model README |

So despite the name, this repository is a Python implementation of parallel constrained decoding,
not a fine-tune and not a weight file. Its README claims 5.6x to 7.0x latency reduction against
autoregressive decoding on an M4 Max, with 100% schema validity. Those numbers are the author's own
and are **not verified** here.

The video confirms the reading: "What he put up was not a new model. It was an ordinary Qwen 2.5,
the 1.5 billion parameter one, the same weights anybody can download. No retraining, no special
architecture, just a different way of running it on his Mac."

The "RLCD" in the name refers to Typesafe's published training method (reinforcement learning for
calibrated decisions). The video says that method only teaches calibrated confidence and does not
explain the speed claims. No RLCD training is present in this HF repo.

---

## 3. Security

### Summary

**The diff adds no outbound network call. None.**

Every network-looking string in the added lines is one of three things: an inbound HTTP route
registration, a `curl` example against `localhost` in the README, or a documentation hyperlink.

### Evidence

Grep over the added (`^+`) lines of the full 1,526-line diff for
`socket|http|https?://|curl|wget|fetch|dns|getaddrinfo|connect(|bind(|popen|system(|exec[lv]|fork(|download|upload|telemetry|analytics|api_key|token=`
returns exactly 6 hits:

| Diff line | File and approximate new line | Content | Verdict |
|---|---|---|---|
| 151 | `tools/parallel-decision/README.md` ~28 | `curl http://localhost:8096/v1/decision ...` | Documentation example, loopback only |
| 215 | `tools/parallel-decision/README.md` ~130 | Markdown link to the decision-playground repo | Documentation link |
| 1419 | `tools/server/server-context.cpp` ~5242 | `this->post_decision = [this](const server_http_req & req) {` | **Inbound** request handler |
| 1451 | `tools/server/server-context.h` ~155 | `server_http_context::handler_t post_decision;` | Handler declaration |
| 1522 | `tools/server/server.cpp` ~280 | `ctx_http.post("/decision", ex_wrapper(routes.post_decision));` | **Inbound** route |
| 1523 | `tools/server/server.cpp` ~281 | `ctx_http.post("/v1/decision", ex_wrapper(routes.post_decision));` | **Inbound** route |

Further checks, all negative:

| Check | Result |
|---|---|
| New `#include` lines | 17 unique, all standard C++ headers or existing llama.cpp headers: `<algorithm> <chrono> <cmath> <cstdio> <cstdlib> <fstream> <iostream> <sstream> <stdexcept> <string> <utility> <vector>`, `"chat.h" "common.h" "decision-engine.h" "json.h" "llama.h"`. No socket, no curl, no network header. |
| New third-party dependency | None. No `FetchContent`, no `ExternalProject`, no `find_package`, no `GIT_REPOSITORY`, no submodule change. |
| Binary blob | None. The diff contains no `GIT binary patch` and no `Binary files` marker. |
| CI workflow change | None. No file under `.github/` is touched. |
| Install script | None. No `.sh`, `.ps1`, or `.py` file is added or changed. |
| `exec*` / `system()` / `popen()` | None. |
| `getenv()` | One wrapper, `env_str()` in `tools/parallel-decision/parallel-decision.cpp` ~1133 of the diff, used only for the four `DECIDE_*` tuning variables. |

**File read outside the request:** `llama-parallel-decision` (the CLI only, not the server) opens
file paths given on its stdin request line (`read_file()` in `parallel-decision.cpp`). This is a
local-file read from a process whose input you control. It is not a network call, but it does mean
you should not expose that worker's stdin to untrusted input. The server endpoint does not read
files.

### Upstream network features the fork inherits

The fork does not change any of these. They are stock llama.cpp behaviour and they are the real
outbound surface of the binary:

| Feature | What it does | Status in this fork |
|---|---|---|
| `-hf` / `--hf-repo` | Downloads a GGUF from huggingface.co. Uses `HF_TOKEN`. (`common/arg.cpp` ~3066-3088) | Unchanged upstream code |
| `-dr` / `--docker-repo` | Resolves a model through a Docker/OCI registry (`common/arg.cpp` ~482-484, ~3057) | Unchanged upstream code |
| RPC backend | `ggml_backend_rpc_add_server(endpoint)` (`common/arg.cpp` ~1173) | Unchanged upstream code |
| llama-server web UI | Served from the local binary | Unchanged |
| Metrics / props / slots endpoints | Inbound only, opt-in | Unchanged |

There is **no** `llama update` command in the merge-base tree. Grep for
`"update"`, `llama update`, `LLAMA_EXAMPLE_UPDATE`, `check_for_update` in `common/arg.cpp` at commit
`14d04e75` returns nothing. Not verified beyond `common/arg.cpp`.

If you build and run this fork exactly as you run your current llama.cpp, with a local `-m`
model path and no `-hf` and no `-dr`, the binary makes no outbound connection that the stock build
would not make.

### Playground repo (separate, optional, not needed for the fork)

<https://github.com/thecodacus/decision-playground>

| Fact | Value |
|---|---|
| Created / pushed | 2026-09-19, one push |
| Stars / forks | 16 / 7 |
| License | **None declared** |
| Runtime dependencies | `react`, `react-dom` only (`package.json`) |
| Dev dependencies | vite, typescript, oxlint, @vitejs/plugin-react, @types/* |
| Backend | None. Browser-only. |
| Outbound calls | `fetch()` to the llama-server URL the user types. Default `http://localhost:8080`, overridable with `VITE_DEFAULT_SERVER`. (`src/lib/api.ts`, `README.md`) |

`src/lib/api.ts` contains three `fetch()` calls: `/v1/models`, the decision URL, and the chat
completion URL. All three take the server base URL from the app's setting. No telemetry endpoint,
no analytics import, no hard-coded remote host. It needs an `npm install` of the vite toolchain,
which is a much larger supply-chain surface than the C++ fork. **You do not need it to use the
endpoint.** A `curl` call is enough.

### Repo activity and provenance

| Fact | Value | Source |
|---|---|---|
| Fork | `thecodacus/llama.cpp`, fork of `ggml-org/llama.cpp` | GitHub API |
| Author | Anirban Kar (`thecodacus`), 447 followers, 87 public repos, account since 2017, blog codacus.com | <https://api.github.com/users/thecodacus> |
| Fork stars / forks | 313 / 87 | GitHub API, 2026-09-23 |
| Last push to the repo | 2026-09-20 10:28 UTC | GitHub API |
| Last commit on `parallel-decision` | 2026-09-20 10:28 UTC | GitHub API |
| Releases / tags | 0 | GitHub API |
| License | MIT, inherited from upstream | GitHub API |
| Commits signed | No. `verification.verified = false`, reason `unsigned`. | GitHub API |
| Issues | Disabled on the fork (`has_issues: false`) | GitHub API |

**Is it a pull request to upstream llama.cpp? No.**

- `search/issues?q=repo:ggml-org/llama.cpp+author:thecodacus+type:pr` returns `total_count: 0`.
- A scan of `repos/ggml-org/llama.cpp/pulls?state=all` for any PR whose head repo owner is
  `thecodacus` returns 0.
- The only open PRs are inside the fork itself (#7, #10, #11, #12, #13), all with a base branch in
  `thecodacus/llama.cpp`.

So there has been no upstream review of this code. It is one person's branch, unsigned, two days
old at the time of writing, and 98 commits behind upstream master.

### Security verdict

| Risk | Level | Note |
|---|---|---|
| New outbound network call in the diff | **None found** | 1,526 diff lines read in full |
| New third-party dependency | **None** | |
| Binary blob or changed CI | **None** | |
| New inbound attack surface | Low, opt-in | Two POST routes, off unless `--decision-seqs N >= 3`. The handler validates types and sizes before use. |
| Code quality risk | Medium | The handler runs `llama_decode` synchronously on the server's task thread, so a large `contexts` batch blocks the chat slots for its duration (`process_single_task`, `SERVER_TASK_TYPE_DECISION` case). |
| Provenance risk | Medium | Unreviewed, unsigned, single author, no upstream PR, 98 commits behind master. |
| Supply-chain risk of the playground | Medium, avoidable | A full vite/npm tree, no license. Skip it and use `curl`. |

The code is worth reading before use, but nothing in it reaches the network.

---

## 4. Fit for our setup

### Our current approach

We run llama.cpp on legion-t5 (RTX 3060 Ti, CUDA 12.8, `/opt/llama.cpp`) and on gaming-b650 (AMD,
Vulkan). Our judge sends 2 typed questions per request and reads answer-letter logprobs from the
stock `/completion` endpoint with `n_probs`.

### Difference table

| Aspect | Our `/completion` + `n_probs` | Fork `/v1/decision` |
|---|---|---|
| Questions per HTTP call | 1 field per call, so 2 calls per request (or 1 call per letter position) | All fields of the schema in one call, up to 32 fields |
| Forward passes | 1 prefill per call. 2 calls = 2 prefills of the same instructions, unless the prefix cache saves the second. | 1 prefill of the shared prefix (cached across requests), 1 prefill per context, then **1** batched decode for all fields |
| Contexts per call | 1 | 1 to 256, all sharing the schema and the cached prefix |
| Probability source | Raw top-`n_probs` logprobs over the **full** vocabulary. We must find our letters in the list and renormalise ourselves. A letter can fall outside the top-N and disappear. | Exact softmax over **only** the allowed values. Every option is always scored. No missing-option case. |
| Multi-token options | We must use letters (A/B/C) because words span several tokens. | The engine tokenises the real words and walks the token trie, so it scores `"billing"` directly. Letters are unnecessary. |
| Answer validity | We map a letter back to a value in our code and must handle a letter that is not in the list. | The server assembles the JSON from the schema, so the answer is always a legal value. |
| Prompt building | We build the letter prompt ourselves and must keep it in sync with the judge. | `compile_schema()` builds the field catalogue and `render_prompt()` applies the model's chat template with thinking disabled. |
| Calibration cost | Free, we already read logprobs. | Free, same mechanism, just normalised for us. |
| Numeric fields | Not supported by our letter trick without an enum of letters. | `integer` and `number` grids with `median`/`mean` aggregates and a p10-p90 interval. |
| Server impact | None beyond a normal request. | Forces unified KV for the whole server and raises `n_seq_max`. Blocks the task thread during a decision. |

### Would it give a better path? Yes, with four conditions.

**The wins that matter to us:**

1. **One call instead of two.** Our 2 typed questions become a 2-field schema in a single
   `/v1/decision` call. The instructions prefill once and stay cached, and both fields are scored in
   the same `llama_decode`. Our second question stops costing a second round trip and a second
   prefill.
2. **No more letter mapping.** We can put the real answer strings in the schema. The engine handles
   multi-token values with its token trie. That removes a class of bug in our judge: a letter that
   does not appear in `n_probs`, or a letter the model writes with different surrounding
   whitespace. The video names this exact tokenisation trap as the bug that skewed the author's
   first version.
3. **Probabilities normalised over the allowed set only.** We currently renormalise by hand over
   whichever letters made it into the top-N. The fork returns the exact constrained distribution
   from the trie, which is what a calibrated judge threshold needs.
4. **Batching.** `contexts` takes up to 256 items sharing one cached prefix. If we ever score a
   backlog, this is a large win. The video claims 8 requests in one call landed about 12 times
   faster than writing the 8 answers as JSON, and that batching roughly doubles GPU throughput
   against sending the same 8 one at a time. **Not verified.**

**The conditions:**

1. **Our 2 questions must be independent.** Fields cannot see each other. If our second question
   depends on the first answer, this fork is the wrong tool and we keep two sequential calls.
   This is a hard property of the design, not a bug.
2. **A full rebuild on both hosts.** The branch base is upstream master of 2026-09-19. Our
   `/opt/llama.cpp` CUDA 12.8 build on legion-t5 would have to be rebuilt from this branch, and it
   is 98 commits behind current upstream. Buildbox LXC 103 is the right place to build, not the LLM
   hosts. That is a real maintenance cost for a branch with no upstream PR.
3. **The unified KV side effect.** `--decision-seqs` flips the whole server to a unified KV cache.
   On legion-t5 RAM is already nearly full (see `rerank-embed-tiers-2026-09-20`), so the extra
   sequences need a measurement before we enable this on a shared server. A separate judge server
   process would avoid touching the chat/embed tiers.
4. **Vulkan is untested.** The engine is backend-agnostic in source. Nobody has reported it on
   Vulkan or ROCm. The video only shows CUDA and Metal. **Not verified for gaming-b650.**

### Speed expectation for our case

Our judge asks 2 fields, not 30. The fork's advantage grows with field count, so a 2-field schema
captures much less of the claimed 5x to 7x. What we would gain is mostly:

- one round trip instead of two,
- one prefill of the shared instructions instead of two,
- correct normalisation without our own letter bookkeeping.

The raw per-decision latency for 2 boolean-ish fields is probably close to what we see today.
**Not verified. This needs a measurement, not an estimate.**

### Recommendation

Test it, but as a side-by-side experiment on one host, not as a replacement.

1. Build the branch on buildbox LXC 103 (podman), not on legion-t5 or gaming-b650.
2. Run a **second** llama-server on legion-t5 on a spare port with `--decision-seqs 8`, so the
   existing tiers keep their KV behaviour.
3. Replay the 18 judge questions we already have answers for
   (`05-semif-accuracy-test.md`, `06-test-log.md`) through both paths and compare the winner,
   the probability, and the wall time.
4. If the probabilities track our current logprob path and the latency is equal or better, the
   cleaner API alone justifies the switch.
5. Watch fork PR #13. Without it we get only the winner's probability, and we currently read the
   full distribution.

Do not adopt the playground. A `curl` call covers the same ground with no npm tree.

---

## Open items / not verified

- Any performance number in this document. Nothing was built or run.
- Vulkan and ROCm behaviour of the decision engine.
- Whether `llama update` exists anywhere in the merge-base tree. Only `common/arg.cpp` was checked.
- The `Qwen-2.5-1B-RLCD` README's 5.6x-7.0x benchmark table.
- The video's 12x batching claim and its 300 ms vs 3.5 s playground comparison.
- Whether our two judge questions are truly independent. That is a question about our own judge,
  and it decides whether this fork fits at all.
