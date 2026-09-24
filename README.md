# judge-model-compare

A test bench for a router judge: a small model that reads each request and picks the model that answers it.

The work starts with Jev, the "System 1" classification model from TypeSafe AI, and with the open Jev-style models. It grew into a comparison of judge candidates on 24 labeled cases, plus a running router.

Status: research and a running proof of concept. Local repo, no remote.

Open work: see `docs/06-test-log.md`, section "Work still to do". Needle 3 is tested and closed on 2026-09-24.

## Sources

- Video: [Jev - The Ultimate Classification Model?](https://www.youtube.com/watch?v=X117w2Rark8) (Sam Witteveen, 2026-09-18)
- Video: [Open Jev Models Are Here!!](https://www.youtube.com/watch?v=53wDOI_7x8I) (2026-09-20)
- Video: [How to Build Things with Jev & OpenJevs](https://www.youtube.com/watch?v=ZR7anrL50xs) (2026-09-21)
- Blog: https://typesafe.ai/blog/introducing-system-one-models-and-jev
- Benchmark: https://benchmarkheaven.com/jev-models

## Contents

| Path | What |
|---|---|
| `docs/06-test-log.md` | **Start here.** Every test, every result, and the overview table |
| `docs/00-summary.md` | The model options table, and the common blockers |
| `docs/01-jev-api-and-jevbench.md` | The Jev API, and the JevBench results |
| `docs/02-open-models-part1.md` | SemIf, Bespoke Nimble, Decider, OpenJev |
| `docs/03-open-models-part2.md` | DiffusionGemma, NanoJev, Laya, OpenSourceJev, others |
| `docs/04-router.md` | The router from video 3, and the community routers |
| `docs/05-semif-accuracy-test.md` | SemIf accuracy test with 7 local GGUF models on legion-t5 (2026-09-22) |
| `docs/07-poc-router-plan.md` | Stage 1: the plan and the decisions for the proof of concept |
| `docs/08-codacus-llama-fork.md` | The code audit of the llama.cpp fork with the Jev decision endpoint |
| `poc/` | The running proof of concept: judge, router, web log page. See `poc/README.md` |
| `poc/laya/` | The Laya judge on legion-t5, and its result. See `poc/laya/README.md` |
| `poc/decision-fork/` | The llama.cpp fork with Jev support: build, install and security test. See `poc/decision-fork/README.md` |
| `poc/decision-judge/` | The judge that uses the fork endpoint, with the speed and quality result |
| `poc/needle/` | Needle 3 of Cactus Compute: the facts, the bench and the result. Not usable as a judge |
| `poc/results/` | The judge comparison and the raw result files. See `poc/results/README.md` |
| `semif-test/` | Scripts, container and results to run that test again. See `semif-test/README.md` |
| `router/` | A copy of one open-source Jev router. See `router/UPSTREAM.md` |

## Configuration

The host addresses live in `.env` at the repository root. That file is in `.gitignore`, so no address of the network lands in the repository. Start like this:

```sh
cp .env.example .env && ${EDITOR:-nano} .env
cp poc/.env.example poc/.env   # the compose file in poc/ reads that one
```

Every shell script reads `.env` through `scripts-lib.sh`. Every Python script reads it through `envload.py`. The documents write an address as a name, for example `<LEGION_IP>`.

## Local hosts

| Host | GPU | Notes |
|---|---|---|
| gaming-b650 | AMD Radeon AI PRO R9700, 32 GB, Vulkan | A 27B chat model uses most of the VRAM |
| legion-t5 | NVIDIA RTX 3060 Ti, 8 GB, CUDA | Embed and rerank models run here. The 14 GB RAM is almost full |
