# Needle 3 as a judge: the survey and the plan

**State on 2026-09-24: tested, and not usable.** Needle 3 ran the same 24 bench cases in both modes, in a Podman container on the CPU of the model host.

| Mode | Sensitive | Difficulty | Both | Abstentions | Mean time |
|---|---|---|---|---|---|
| `record_decision` | 1/24 | 0/24 | 0/24 | 47 of 48 | 0.20 s |
| `options_as_tools` | 1/24 | 6/24 | 1/24 | 31 of 48 | 0.23 s |

**The cause.** Needle looks for a tool that serves the request. Our judge asks a question about the request. The engine answers "No tool available for geography or factual lookup", and that counts as an abstention. JevBench reports the same: 0 of 16 on the ordinal topic.

**What ran.** `needle_bench.py` in this folder, with `cactus-needle==3.0.1`. The result files are `../results/judge-needle3-*.json`. The engine is fast: 0.20 s for both questions, and 100 MB of RAM.

**One install trap.** Version 3.0.5 of the package asks Hugging Face for an engine wheel 3.0.2, and that file does not exist. The model repository holds 3.0.0 and 3.0.1 only. Pin `cactus-needle==3.0.1`.

`app.py` and `Containerfile` in this folder stay drafts. A service adds nothing while the engine abstains.

Research of 2026-09-23. Needle 3 by Cactus Compute is a candidate for a fifth judge, next to the 3 Qwen
judges and Laya. Nothing is installed and nothing is built. This folder holds the facts, the plan, and an
untested draft of the service.

**Short answer: the weights are open, but the published numbers say Needle 3 cannot answer our difficulty
question.** On the JevBench topics that match our 2 router questions it scores 0 of 16 on `ordinal` and
0 of 78 on `routing`. It also returns a label with 1 confidence number, not a probability per option, so the
`noul` question loses its probability and the calibration column of the bench stays empty.

Recommendation: install it on LXC 110 `jev-poc`, next to the other judge, on the CPU. Run the bench first,
before any router change.

## 1. What Needle 3 is

| Point | Value | Source |
|---|---|---|
| Author | Cactus Compute, Inc. | [model card](https://huggingface.co/Cactus-Compute/needle3) |
| Type | Foundation model for tool calls, structured extraction and text embedding. Not a chat model | [model card](https://huggingface.co/Cactus-Compute/needle3) |
| Architecture | Laddered Simple Attention Network: Monarch Hadamard MLP in place of the FFN, GQA attention with causal conv taps, engram n-gram memory, multi-lane hyper-connections | [model card](https://huggingface.co/Cactus-Compute/needle3) |
| Size | 121M parameters. "Most of its parameters sit in the engram, so the 121M model does the arithmetic of a 50M one" | [model card](https://huggingface.co/Cactus-Compute/needle3) |
| Depth | 20 layers. Every depth from 2 to 20 layers is a usable model on its own | [model card](https://huggingface.co/Cactus-Compute/needle3) |
| Quantization | CQ2-bit, about 2.125 bits per weight, format `.cact` | [model card](https://huggingface.co/Cactus-Compute/needle3) |
| File size | The product page says 8 to 29 MB over the depth ladder. The 20-layer file `needle3.cact` on Hugging Face is 35.3 MB | [product page](https://cactuscompute.com/needle), [HF file list](https://huggingface.co/api/models/Cactus-Compute/needle3?blobs=true) |
| Licence | Apache-2.0, for the model and for the package | [HF API](https://huggingface.co/api/models/Cactus-Compute/needle3), [GitHub](https://github.com/cactus-compute/needle) |
| Weights | Open. `Cactus-Compute/needle3` on Hugging Face, 62,025 downloads, 200 likes | [HF API](https://huggingface.co/api/models?author=Cactus-Compute) |
| Code | `cactus-compute/needle` on GitHub, Apache-2.0, 12,398 stars | [GitHub API](https://api.github.com/orgs/cactus-compute/repos) |
| API only | No. The engine and the weights run on the device | [model card](https://huggingface.co/Cactus-Compute/needle3) |
| Training data | "360B tokens of proprietary structured dataset" | [product page](https://cactuscompute.com/needle) |

### The repository files that matter

| File | Size | What |
|---|---|---|
| `needle3.cact` | 35.3 MB | The 20-layer model, CQ2-bit. The engine maps it and reads it in place |
| `checkpoints/needle3.safetensors` | 242.0 MB | The float checkpoint, for a fine-tune |
| `linux-x86_64/needle` | 1.25 MB | The CLI runner for our hosts |
| `linux-x86_64/libneedle.a` | 1.68 MB | The static engine library, with `needle.h` |
| `python/cactus_needle-3.0.1-py3-none-manylinux2014_x86_64.whl` | 0.54 MB | The Python wheel in the repository |
| `tokenizer/tokenizer.model` | 0.13 MB | SentencePiece tokenizer |

The whole repository is 325.9 MB, because it carries an engine for 17 platform folders and the float
checkpoint. A judge needs about 37 MB of it: `needle3.cact`, the `linux-x86_64` folder and the tokenizer.
Source: [HF file list](https://huggingface.co/api/models/Cactus-Compute/needle3?blobs=true).

### What it answers

| Question | Answer | Source |
|---|---|---|
| Function calling? | Yes. This is the main job. It picks the tools and fills every argument | [model card](https://huggingface.co/Cactus-Compute/needle3) |
| Structured extraction? | Yes. A declared shape gives typed fields back. A byte-level grammar compiled from the schema constrains every token, so the output always parses | [model card](https://huggingface.co/Cactus-Compute/needle3) |
| Classification? | Only through extraction with an enum. "extraction generalises to classification" | [model card](https://huggingface.co/Cactus-Compute/needle3) |
| Typed questions like Jev? | No native shape. A question must become a tool | [needle_local.py](https://github.com/fstandhartinger/jevbench/blob/main/jevbench/adapters/needle_local.py) |
| Embedding? | Yes, `embed(text)` returns a vector | [python docs](https://cactuscompute.com/blog/needle-python-docs) |
| Probability per option? | **No.** One calibrated scalar for the whole call | [confidence guide](https://cactuscompute.com/blog/needle-confidence) |

The confidence score is "the minimum of two signals. A calibrated post-hoc head scores the full prompt
together with the call the model just produced", and the second signal is the decode probability of the call
tokens. The guide gives 3 bands: act at 0.7 or higher, confirm between 0.1 and 0.7, refuse below 0.1. The
head is calibrated on the base model only. A fine-tuned archive reports `confidence` as `None`.
Source: [confidence guide](https://cactuscompute.com/blog/needle-confidence).

An off-topic request returns an empty list of calls, not a guess. The video shows this with "What is the
capital of France?": with no matching tool the model writes nothing.
Sources: [model card](https://huggingface.co/Cactus-Compute/needle3),
[video transcript](https://www.youtube.com/watch?v=qbN559fQn7k).

### The JevBench numbers

JevBench runs Needle 3 in 2 modes and never merges them. Both are partial runs and neither carries a rank.

| Mode | Easy | Standard | Judge | Hard | Public accuracy 534 | p50 raw | Cost / 1,000 |
|---|---|---|---|---|---|---|---|
| `needle-3` (record_decision, 2-bit, local CPU) | 47.2 % | 16.7 % | 31.5 % | 7.7 % | 22.5 % | 1.69 s | ~ $0.024 est. |
| `needle-3-tools` (options as tools) | 66.7 % | 31.3 % | 34.3 % | not run | 22.1 % | 3.78 s | ~ $0.014 est. |

Sources: [`results/v1.2/jevbench-v1.2-per-task.json`](https://github.com/fstandhartinger/jevbench/blob/main/results/v1.2/jevbench-v1.2-per-task.json)
(the file carries `revision: v1.3.0`, `status: final`),
[`results/v1.4/jevbench-v1.4-results.json`](https://github.com/fstandhartinger/jevbench/blob/main/results/v1.4/jevbench-v1.4-results.json),
[benchmarkheaven.com/jev-models](https://benchmarkheaven.com/jev-models).

For comparison, the JevBench leaders reach 74.4 (Jev 1.13.0) and 73.1 (SemIf on Qwen3.5-4B, the method of
our own judge). Source: [jevbench README](https://github.com/fstandhartinger/jevbench).

#### The topic scores that decide this case

Our router asks 2 questions. The sensitivity question is a `noul`, close to the JevBench `policy` topic. The
difficulty question is a 3-way `choice` between simple, medium and hard, which is the JevBench `ordinal` and
`routing` topic. Those are the 2 topics where Needle 3 fails hardest.

| Topic | Tier | `needle-3` | `needle-3-tools` |
|---|---|---|---|
| `ordinal` | standard | 0 of 16 (0.0 %) | 1 of 16 (6.3 %) |
| `routing` | standard | 0 of 16 (0.0 %) | 7 of 16 (43.8 %) |
| `routing` | judge | 0 of 78 (0.0 %) | 4 of 78 (5.1 %) |
| `policy` | standard | 2 of 16 (12.5 %) | 1 of 16 (6.3 %) |
| `extraction` | easy | 18 of 18 (100 %) | 8 of 18 (44.4 %) |
| `tool_selection` | easy | 3 of 18 (16.7 %) | 17 of 18 (94.4 %) |
| `intent` | easy | 4 of 18 (22.2 %) | 14 of 18 (77.8 %) |
| `adequacy` | judge | 46 of 68 (67.7 %) | 46 of 68 (67.7 %) |

Source: [`results/v1.2/jevbench-v1.2-per-task.json`](https://github.com/fstandhartinger/jevbench/blob/main/results/v1.2/jevbench-v1.2-per-task.json).

Read this table as a shape, not as a score. Needle 3 is excellent at what it was built for: extraction
(18 of 18) and tool selection in the tools mode (17 of 18). It is near zero on the ordinal and routing
questions that a model router asks. Laya failed our bench for a different reason, a base checkpoint near
random. Needle 3 would fail for a structural reason: the task is not a tool call.

#### Calibration

JevBench records for both Needle rows:

- `has_distribution: false`
- `probability_source: ["label_only_no_calibrated_distribution"]`
- `calibration.note`: "returns a label, not a probability distribution: no calibration score (counts as 0 in
  the JevBench Score)"

Source: [`results/v1.4/jevbench-v1.4-results.json`](https://github.com/fstandhartinger/jevbench/blob/main/results/v1.4/jevbench-v1.4-results.json).

The JevBench adapter states the rule in words: "we never turn a single confidence into a distribution, so
Brier and ECE are not computed for Needle".
Source: [needle_local.py](https://github.com/fstandhartinger/jevbench/blob/main/jevbench/adapters/needle_local.py).

#### Why the run stayed partial

JevBench v1.4 kept both rows unranked. The reason for `needle-3`: "Not re-measured: ~100-250 s per item on a
rented CPU pod (19 s on Sandy); needs a dedicated CPU host." The reason for `needle-3-tools`: "Not
re-measured: same as needle-3." The measured p50 of 1.69 s comes from 2 CPU threads of a Ryzen 5 3600.
Source: [`results/v1.4/jevbench-v1.4-results.json`](https://github.com/fstandhartinger/jevbench/blob/main/results/v1.4/jevbench-v1.4-results.json).

The spread from 1.69 s to 250 s per item on different CPUs is the reason to measure the time on our own host
before anything else.

### Numbers that disagree between the sources

| Point | Video, 2026-09-18 | Model card and Hugging Face |
|---|---|---|
| Parameters | 53 million | 121M |
| File size | 35 MB | 8 to 29 MB on the product page, 35.3 MB for the 20-layer `.cact` file |
| Architecture name | "simple attention network" | "Laddered Simple Attention Network" |

The model card and the file list are the primary sources, so use 121M parameters and 35.3 MB for the
20-layer model. The video probably quotes a subnetwork. Not verified which one.

### What the video adds

The transcript of [Needle 3: You Don't Need an LLM for Function Calling](https://www.youtube.com/watch?v=qbN559fQn7k)
(Prompt Engineering, 2026-09-18) was read with `youtube-transcript-api`. It was not blocked. 11,774
characters. The useful parts are 4 warnings from the author of the video:

1. **It keeps the conversation history.** Without a `reset()` between calls it produces wrong calls. The
   video shows a false schema for "order me a pizza" when the state is not reset.
2. **Every function argument needs a good default.** Without defaults the call comes back without values.
3. **It refuses when no tool fits.** A factual question gives no output at all.
4. **It is not an intent classifier.** "it's not as good as direct intent classification. So I won't use it
   for something like this." The video compares it with the Jev system-one model, which is trained for
   classification.

Point 4 is the same conclusion as the JevBench topic table, from an independent test.

## 2. How to run it

| Point | Value | Source |
|---|---|---|
| Package | `cactus-needle` on PyPI, version 3.0.5, `py3-none-any`, 99 KB | [PyPI](https://pypi.org/pypi/cactus-needle/json) |
| Python | 3.9 or newer | [PyPI](https://pypi.org/pypi/cactus-needle/json) |
| Hard dependency | `huggingface_hub` only | [PyPI](https://pypi.org/pypi/cactus-needle/json) |
| Optional extras | `train` needs numpy, jax, jaxlib, flax, optax, safetensors, sentencepiece. `gpu` needs `jax[cuda12]`. A judge needs neither | [PyPI](https://pypi.org/pypi/cactus-needle/json) |
| Import name | `needle` | [model card](https://huggingface.co/Cactus-Compute/needle3) |
| CPU or GPU | CPU. No GPU is needed for inference. The `gpu` extra exists for the fine-tune only | [product page](https://cactuscompute.com/needle), [PyPI](https://pypi.org/pypi/cactus-needle/json) |
| RAM | The response reports `peak_ram_mb`. The python docs example shows 88.5 MB, the product page shows 28.5 MB | [python docs](https://cactuscompute.com/blog/needle-python-docs), [product page](https://cactuscompute.com/needle) |
| Disk | 35.3 MB for the weights, 1.3 MB for the engine. Add 242 MB only for a fine-tune | [HF file list](https://huggingface.co/api/models/Cactus-Compute/needle3?blobs=true) |
| Speed claim | 400 to 4,000 tokens/s decode on a Raspberry Pi 5, from 20 layers down to 2 layers | [devices guide](https://cactuscompute.com/blog/needle-supported-devices) |
| HTTP API | Yes, in the native runner: `--serve` opens an HTTP server on localhost with `POST /complete` and a body `{"input": "..."}`. The Python package has no server | [devices guide](https://cactuscompute.com/blog/needle-supported-devices) |
| Runtime format | `.cact`, a Cactus format the engine maps and reads in place. No GGUF, no ONNX. An MLX build exists for other Cactus models, not for Needle | [model card](https://huggingface.co/Cactus-Compute/needle3), [HF API](https://huggingface.co/api/models?author=Cactus-Compute) |

### The exact install

```sh
pip install cactus-needle
```

**Warning: do not run `pip install needle`.** That name belongs to an unrelated project, "Automated testing
for your CSS", version 0.5.0. Source: [PyPI needle](https://pypi.org/pypi/needle/json).

The package downloads the engine and the weights from Hugging Face on the first use and caches them in
`~/.cache/cactus-needle/v3/`. Source: [python docs](https://cactuscompute.com/blog/needle-python-docs).

### The exact call

```python
import needle

tools = [{
    "name": "record_decision",
    "description": "Record the answer to this question about the text: ...",
    "parameters": {"type": "object",
                   "properties": {"decision": {"type": "string",
                                               "enum": ["simple", "medium", "hard"],
                                               "description": "How hard is this request? Options: ..."}},
                   "required": ["decision"]},
}]
agent = needle.Needle(tools=tools, system="How hard is this request?")
out = agent.complete("What is the capital of France?", max_new_tokens=128)
agent.close()
# out = {"type": "call", "success": true, "function_calls": [...], "suppressed_calls": [],
#        "reasoning": "...", "confidence": 0.94,
#        "prefill_tps": 4300.0, "decode_tps": 850.0, "peak_ram_mb": 88.5}
```

The constructor is
`needle.Needle(tools=None, system=None, weights=None, tool_index_path=None, buffer_size=65536, auto_date=True, generation=3)`.
It takes decorated functions, Pydantic models, JSON-schema dicts or JSON strings. The methods are
`run(query, max_steps=8, max_new_tokens=512, strict=True)`, `complete(text="", max_new_tokens=512)`,
`embed(text)` and `reset()`. `suppressed_calls` holds the calls the engine withheld below confidence 0.1.
Sources: [python docs](https://cactuscompute.com/blog/needle-python-docs),
[needle_local.py](https://github.com/fstandhartinger/jevbench/blob/main/jevbench/adapters/needle_local.py).

The same shape works from the native runner:

```sh
./needle --model needle3.cact --tools tools.json --prompt "dim the living room to 30"
./needle --model needle3.cact --tools tools.json --serve
```

Source: [model card](https://huggingface.co/Cactus-Compute/needle3),
[devices guide](https://cactuscompute.com/blog/needle-supported-devices).

### Environment and privacy

| Variable | Why |
|---|---|
| `NEEDLE_TELEMETRY=0` | It turns the telemetry off. The JevBench adapter sets it with the comment "no benchmark data leaves the box" |
| `DO_NOT_TRACK=1` | The second way to turn the telemetry off |
| `HF_HUB_OFFLINE=1` | No network call at runtime. It fails fast when the engine is missing |
| `NEEDLE3_LIB_PATH` | The path of the engine, when the cache is somewhere else |

Sources: [python docs](https://cactuscompute.com/blog/needle-python-docs),
[needle_local.py](https://github.com/fstandhartinger/jevbench/blob/main/jevbench/adapters/needle_local.py).

Telemetry is on by default. Turn it off in the image, the same way the JevBench adapter does. The repo rule
for the decision fork applies here too: prove that nothing leaves the box before any real use.

### The air-gapped route, for the container

1. Run `needle fetch` and `needle download needle3` on a machine with internet.
2. Copy the engine and `needle3.cact` to `~/.cache/cactus-needle/v3/` on the target.
3. Or set `NEEDLE3_LIB_PATH` to the engine.
4. Use `pip download cactus-needle`, then `pip install --no-index --find-links <dir> cactus-needle`.
5. Set `HF_HUB_OFFLINE=1`.

Source: [devices guide](https://cactuscompute.com/blog/needle-supported-devices).

This maps to the pattern of `../laya/Containerfile`: bake the model into the image, so the container needs no
internet at runtime.

### The one global model

The C API "maintains one process-global model and conversation; use separate worker processes for multiple
fine-tuned models."
Source: [devices guide](https://cactuscompute.com/blog/needle-supported-devices).

That has 2 consequences for a judge service:

1. The service must serialise the requests with a lock, or 2 concurrent requests mix their conversations.
2. The service must call `reset()`, or build a new agent, between every question. The video shows wrong calls
   without a reset.

## 3. Where to install it

| Host | Fits? | Facts |
|---|---|---|
| **LXC 110 `jev-poc`** <POC_IP>, pve2, Debian 13, Docker, 4 cores, 4 GB, no GPU | **Yes, the recommendation** | CPU only, and Needle needs no GPU. 4 GB of RAM against a peak of 28 to 89 MB. The judge and the router already run here, so the bench needs no SSH tunnel. A free port sits next to 8080 and 8081. The image stays small, because no torch and no CUDA are needed |
| **legion-t5** <LEGION_IP>, Ubuntu 26.04, Podman, 12 cores, 14 GB, RTX 3060 Ti 8 GB | Works, but it costs more | The GPU brings nothing, because the engine is a CPU engine. The firewall allows only 11434, 11435, 11436 and 8080, and all 4 are taken or reserved, so the bench needs an SSH tunnel, as Laya did on port 8082. The 12 cores are the fastest CPU of the 4 options, which matters for the latency risk. Use this host only when LXC 110 proves too slow |
| **gaming-b650** <GAMING_IP>, AMD R9700 32 GB, Vulkan, no container runtime, about 1 GB of RAM free | No | No container runtime, so the Laya pattern does not apply. About 1 GB of free RAM leaves no room for a service, even a small one. The Vulkan GPU is useless here. This host serves the answer models and must stay free |
| **buildbox LXC 103** <BUILDBOX_IP>, Podman, 12 cores, 16 GB, no GPU | Only for the build | The repo rule says builds go here, never a toolchain on a service host. Use it to build the image and to run `pip download` and `needle fetch` for the offline copy. It is a build runner, so do not park a long-running judge on it |

**Recommendation: LXC 110 `jev-poc`, in Docker, on the CPU, on port 8084.** Reasons, in order:

1. Needle is a CPU engine, so the legion GPU is no advantage. The SemIf judge keeps its 3,568 MiB.
2. The judge, the router and the bench already live on LXC 110. No firewall hole and no SSH tunnel.
3. The memory need is tens of MB. 4 GB is plenty.
4. The image needs no torch and no CUDA, unlike Laya, so the build is minutes, not 20 minutes.

Build the image on buildbox LXC 103 when the pip download on LXC 110 is unwanted. LXC 110 already builds its
own images with `docker compose up -d --build`, so a local build is simpler and is the default.

Not verified: whether the `linux-x86_64` engine needs a CPU instruction set that the pve2 CPU lacks, for
example AVX-512. The engine is a prebuilt static binary, and the requirement is not documented. Step 1 of the
plan tests it.

## 4. The plan

The same order as Laya: a container, the adapter, a deploy script, the bench on the same 24 cases, then the
comparison table. Step 0 is new, because the latency risk and the engine risk are cheap to test first.

| Step | What | Time |
|---|---|---|
| 0 | **Smoke test in a venv on LXC 110.** `python3 -m venv`, `pip install cactus-needle`, one `complete()` call on 1 bench case in each mode. Read `peak_ram_mb`, `decode_tps` and the wall time. It proves the engine runs on this CPU, and it measures the real latency against the 1.69 s and the 250 s of the JevBench rows. **Stop here when a call needs more than 20 s: then move to legion-t5 or drop the candidate** | 30 min |
| 1 | **The container.** `Containerfile` in the shape of `../laya/Containerfile`: `python:3.13-slim`, `pip install cactus-needle`, then `needle fetch` in the build so the engine and the 35.3 MB of weights are baked in. Set `HF_HUB_OFFLINE=1`, `NEEDLE_TELEMETRY=0` and `DO_NOT_TRACK=1`. No torch, no CUDA | 45 min |
| 2 | **The `/v1/systemone` adapter.** `app.py`, in the shape of `../laya/app.py`. It maps a `noul` question to a boolean tool argument and a `choice` question to a string enum, exactly as the JevBench adapter does. It holds a lock, it resets between questions, and it fills `probabilities` from the single confidence with a marked source. The draft is in this folder | 60 min |
| 3 | **The deploy script.** `deploy-lxc110.sh`, in the shape of `../laya/deploy-legion.sh`: rsync, build, run on port 8084, then poll `/health`. Add the mode as an argument, `record_decision` or `tools`, because JevBench keeps both and never merges them | 20 min |
| 4 | **The bench, twice.** `python3 judge_bench.py --judge http://<POC_IP>:8084 --label needle3-record` and `--label needle3-tools`. The same 24 cases and the same 2 questions as every other judge. Count the abstentions as wrong, as JevBench does. Budget 2 minutes when step 0 gave 1 to 2 s per call, and 90 minutes when it gave 20 s | 20 to 90 min |
| 5 | **The comparison table.** `python3 results_table.py > results/tables.md`, then a Needle section in `../results/README.md` with the abstention count and the note that the calibration column stays empty | 30 min |

Total: 3.5 to 5 hours, without the fine-tune.

Step 6, only when step 4 gives a usable score: fine-tune a subnetwork on our own decisions with
`needle generate-data`, `needle finetune` and `needle build --lora`. Note that a fine-tune sets `confidence`
to `None`, because the head is calibrated on the base model only. Not estimated.

## 5. The blockers

| # | Blocker | Severity | Evidence |
|---|---|---|---|
| 1 | **The difficulty question is the question Needle fails.** 0 of 16 on `ordinal` and 0 of 78 on `routing` in the `record_decision` mode, 1 of 16 and 4 of 78 in the tools mode | Blocking | [per-task json](https://github.com/fstandhartinger/jevbench/blob/main/results/v1.2/jevbench-v1.2-per-task.json) |
| 2 | **No probability per option.** One calibrated scalar for the whole call. JevBench sets `has_distribution: false` and computes no Brier and no ECE | Blocking for calibration | [confidence guide](https://cactuscompute.com/blog/needle-confidence), [v1.4 results](https://github.com/fstandhartinger/jevbench/blob/main/results/v1.4/jevbench-v1.4-results.json) |
| 3 | **It abstains.** With no tool that serves the request it returns an empty list. Our 24 cases are chat requests, not tool requests, so expect abstentions. An abstention scores as wrong | High | [needle_local.py](https://github.com/fstandhartinger/jevbench/blob/main/jevbench/adapters/needle_local.py), [video transcript](https://www.youtube.com/watch?v=qbN559fQn7k) |
| 4 | **The latency on our CPU is unknown.** JevBench measured p50 1.69 s on 2 threads of a Ryzen 5 3600, and left the v1.4 run out because a rented CPU pod needed 100 to 250 s per item | High, and step 0 tests it | [v1.4 results](https://github.com/fstandhartinger/jevbench/blob/main/results/v1.4/jevbench-v1.4-results.json) |
| 5 | **It keeps the conversation state.** Without a `reset()` it produces wrong calls, and the C API keeps 1 process-global conversation. The service must lock and reset | Medium, the design handles it | [devices guide](https://cactuscompute.com/blog/needle-supported-devices), [video transcript](https://www.youtube.com/watch?v=qbN559fQn7k) |
| 6 | **Telemetry is on by default.** Turn it off with `NEEDLE_TELEMETRY=0` and `HF_HUB_OFFLINE=1`, and prove it with the method of `../decision-fork/security-test.sh` | Medium | [python docs](https://cactuscompute.com/blog/needle-python-docs) |
| 7 | **2 modes, 2 runs.** JevBench reports `record_decision` and `options_as_tools` and never merges them. Our comparison table needs 2 rows, not 1 | Low | [needle_local.py](https://github.com/fstandhartinger/jevbench/blob/main/jevbench/adapters/needle_local.py) |
| 8 | **2 questions need 2 calls.** One `record_decision` tool answers 1 question. Our judge asks 2 questions in 1 call, so Needle doubles the work and roughly doubles the time | Low | [needle_local.py](https://github.com/fstandhartinger/jevbench/blob/main/jevbench/adapters/needle_local.py) |
| 9 | **The context is shared.** The tool schemas sit in the model context with the system prompt and the history. `needle_init` fails when the static prefix does not fit. Our state is 8 messages of up to 2,000 characters each | Medium, not measured | [model card](https://huggingface.co/Cactus-Compute/needle3) |
| 10 | **The engine may need CPU features we lack.** The `linux-x86_64` engine is a prebuilt binary and the requirement is not documented. Not verified | Unknown, step 0 tests it | - |

### What "a label and no probability" means for our bench

`judge_bench.py` reads 2 fields that Needle cannot produce honestly:

- `answers["sensitive"]["probabilities"]["true"]` for the `noul` question.
- `answers["difficulty"]["confidence"]` for the `choice` question.

Two ways out. Both must be written down before the run, the way JevBench writes its mappings down:

1. **Report the scalar, and say what it is.** Put the confidence on the chosen label and spread the rest over
   the others, then set a field `probability_source: "label_only_no_calibrated_distribution"` in the answer.
   The draft `app.py` in this folder does this. It keeps `judge_bench.py` working without a change.
2. **Leave the probability empty and let the bench show a gap.** That needs a change in `judge_bench.py`.

Option 1 is the choice, because it keeps the bench unchanged, and because the extra field marks the number as
a converted scalar and not as a real distribution.

For the router the effect is smaller than it looks. `router/router.yaml` decides on the label, not on the
probability. The probability only lands in the decision log and on the web page. So a Needle judge would
still route, and the confidence column of the log would hold 1 number per call instead of a distribution.

For the calibration column of a JevBench-style table, the honest entry is **"none (label only)"**, which
JevBench counts as 0. Our own `../results/README.md` does not have a calibration column today. When we add
one, Needle 3 gets "none (label only)", the same words the JevBench row uses.

## Files in this folder

| File | What |
|---|---|
| `README.md` | This document |
| `Containerfile` | **Built and used.** The CPU image: `python:3.13-slim`, `cactus-needle==3.0.1`, the weights baked in |
| `smoke-test.py` | The first check: 3 cases, both questions, in the container. It proves the engine answers before the full bench starts |
| `needle_bench.py` | The full bench: the 24 cases of `../judge_cases.jsonl`, in both modes. It writes a result file for `../results_table.py` |
| `app.py` | **Untested draft.** The `/v1/systemone` adapter. A service adds nothing while the engine abstains |

### Replay the test

Run the 3 steps on the model host. The whole run takes about 20 minutes, and most of that is the build.

1. Build the image. The weights go into the image, so the container needs no network:

       podman build -t needle-smoke -f poc/needle/Containerfile poc/needle

2. Run the smoke test. It must show an answer for the 3 cases:

       podman run --rm -v $PWD/poc/needle:/app:ro needle-smoke python /app/smoke-test.py

3. Run the bench, once for each mode. Each run writes 1 JSON file into `out/`:

       podman run --rm -v $PWD/poc/needle:/app:ro -v $PWD/poc:/poc:ro needle-smoke \
         python /app/needle_bench.py --mode record_decision --cases /poc/judge_cases.jsonl --out /app/out
       podman run --rm -v $PWD/poc/needle:/app:ro -v $PWD/poc:/poc:ro needle-smoke \
         python /app/needle_bench.py --mode tools --cases /poc/judge_cases.jsonl --out /app/out

Copy the 2 JSON files to `../results/`, then run `python3 poc/results_table.py` to rebuild the tables.

## Verification state

| Claim | State |
|---|---|
| Licence, weights, file sizes, package name, API shape | Verified against the model card, the Hugging Face API, PyPI and the Cactus documentation |
| The JevBench numbers | Verified against `results/v1.2/jevbench-v1.2-per-task.json` (revision v1.3.0), `results/v1.4/jevbench-v1.4-results.json` and benchmarkheaven.com |
| The video content | Verified. The transcript was read with `youtube-transcript-api`. It was not blocked |
| The parameter count of 53M in the video | Not verified. The model card says 121M |
| The latency on our hardware | Verified on 2026-09-24. 0.20 s for both questions, on the CPU of legion-t5 |
| The CPU instruction requirement of the engine | Not verified. Not documented |
| The peak RAM on our hardware | Verified on 2026-09-24. About 100 MB |
| `Containerfile`, `smoke-test.py` and `needle_bench.py` | Verified on 2026-09-24. Built and run on legion-t5 |
| `app.py` in this folder | Not verified. Never run. A service adds nothing while the engine abstains |
