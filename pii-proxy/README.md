# PII proxy: replace sensitive data in the request, and put it back in the answer

**State on 2026-09-24: built, deployed and measured.** The chain runs, and it
sends no real value to the cloud in the 24 bench cases.

```
requestor  ->  detector  ->  replacer  ->  filtered call out  ->  restore
  user        Presidio      this gate      the target model      this gate
              analyzer      + the fork
              15 ms          265 ms
```

| Number | Value |
|---|---|
| Real values that reach the cloud model | 0 of 24 cases |
| Round trip exact, the answer holds the original value again | 24 of 24 |
| Mask time | 15 ms |
| Audit time, the fork, 1 call with 2 fields | 265 ms |
| False alarm, a mask on a case with no personal data | 0 of 16 |

## 1. The research

### The question

Is there a project that replaces sensitive data inside a request, keeps a map,
and puts the real value back into the answer?

### The answer

Yes. 5 projects do it. Your own gateway, LiteLLM, holds the most complete one.

| Project | Shape | Placeholder | Round trip | Streaming | State |
|---|---|---|---|---|---|
| [LiteLLM Presidio guardrail](https://docs.litellm.ai/docs/proxy/guardrails/pii_masking_v2) | Built into the gateway | `<PERSON_2>` | `output_parse_pii: true` | Yes. The stream buffers to the end | Production |
| [Microsoft Presidio](https://github.com/microsoft/presidio) | The engine under the row above | Free choice | `encrypt` and `decrypt` operators | Not applicable, a library | Production |
| [llm-proxy-pii-rust](https://github.com/francesco-stimola/llm-proxy-pii-rust) | A separate proxy in Rust | `[EMAIL_1]` | A per-request vault | Yes, a true partial restore per chunk | 1 star. AGPL-3.0 |
| [PIIGhost](https://github.com/Athroniaeth/piighost) | A Python library, LangChain middleware | `<<PERSON:1>>` | Cross-message memory | Not stated | New. Not a proxy |
| [anonLLM](https://github.com/fsndzomga/anonLLM) | A Python wrapper | Typed | Yes | No | Names, e-mails and telephone numbers only |

### Why this repository builds its own gate, and does not only switch on LiteLLM

3 reasons, and all 3 come from a measurement or from an open upstream issue.

1. **The LiteLLM counter restarts on every request.** The same person becomes
   `<PERSON_2>` in one request and `<PERSON_5>` in the next. A model that quotes
   an older answer breaks the round trip. See
   [issue 41600](https://github.com/BerriAI/litellm/issues/41600), open since
   2026-09-17. This gate numbers for each value, so the same value always gets
   the same placeholder inside a request.
2. **The Presidio anonymizer container takes 1 rule for each entity type.** Two
   people both become `<PERSON>`, and the round trip then cannot tell them apart.
   This gate replaces the spans itself, and it keeps a map for each instance.
3. **A mask alone does not make a request safe.** Presidio missed a Dutch street
   and a medical fact in the bench. The llama.cpp fork reads the masked text and
   catches what is left, for 265 ms. See the results in part 4.

### What each part does

| Part | Job | Why it cannot do the other job |
|---|---|---|
| Presidio analyzer | It returns a span: the start, the end and the type | It has no view of the meaning. A medical fact in a plain sentence stays invisible |
| The llama.cpp fork, `/v1/decision` | It answers `boolean` or `enum`, with an exact probability | It cannot return a span. The field types are `boolean`, `enum`, `integer` and `number` only. See `../poc/decision-fork/README.md` |
| This gate | It joins both, keeps the map, and restores the answer | - |

A generative call that emits JSON spans is the third route. It costs 1 to 3
seconds against 15 ms for Presidio, so it loses on speed.

## 2. The plan, and what is done

| # | Step | Time | State |
|---|---|---|---|
| 1 | Raise LXC 109 from 4 GB to 6 GB. The analyzer holds a spaCy model | 5 min | Done |
| 2 | Deploy the 2 Presidio containers on LXC 109, next to LiteLLM | 20 min | Done |
| 3 | Free the GPU of legion-t5 and start the llama.cpp fork on port 11436 | 10 min | Done |
| 4 | Write `gate.py`: mask, audit, route and restore | 60 min | Done |
| 5 | Label the 24 bench cases with the strings that must not leak | 20 min | Done |
| 6 | Run the bench, both with the fork and without it | 30 min | Done |
| 7 | Build the gate service and run it on LXC 110, port 8086 | 30 min | Done |
| 8 | Send real traffic through it, and compare the answer quality | 2 hours | Open |
| 9 | Decide: keep this gate, or switch on the LiteLLM guardrail | 30 min | Open |

## 3. The files

| File | What |
|---|---|
| `gate.py` | The chain: `mask`, `audit`, `route` and `restore`. It holds the ad-hoc recognizers and both prompt versions |
| `gate/app.py` | The service. It speaks `/v1/chat/completions`, and it streams |
| `gate/Containerfile` | The image. 120 MB, no model and no GPU |
| `deploy-presidio.sh` | The 2 Presidio containers on the LiteLLM host. `deploy`, `check` and `stop` |
| `deploy-gate.sh` | The gate on the proof of concept host. `deploy`, `check` and `stop` |
| `gpu-window.sh` | It frees the GPU of legion-t5 for the test, and gives it back. `open`, `close` and `state` |
| `build-cases.py` | It adds the `must_mask` list to the 24 bench cases |
| `pii_cases.jsonl` | The 24 cases, with the strings that must not leak |
| `pii_bench.py` | The measurement. It writes a result file into `results/` |
| `results/` | The raw result of each run |

### Replay the whole test

Every step reads the addresses from `.env` in the repository root.

1. Raise the memory of the LiteLLM host, on the Proxmox node:

       pct set 109 -memory 6144

2. Deploy Presidio:

       ./pii-proxy/deploy-presidio.sh

3. Free the GPU and start the fork:

       ./pii-proxy/gpu-window.sh open

4. Build the case file and run both chains:

       python3 pii-proxy/build-cases.py
       python3 pii-proxy/pii_bench.py
       python3 pii-proxy/pii_bench.py --no-audit

5. Deploy the gate service, and give the GPU back at the end:

       ./pii-proxy/deploy-gate.sh
       ./pii-proxy/gpu-window.sh close

## 4. The result, 24 cases, 2026-09-24

The bench holds the same 24 cases as the judge bench. 8 of them carry personal
data. Each of those 8 lists the exact strings that must not reach the cloud.

| Chain | Leaks | Leaks that reach the cloud | Residual caught | Cleared for the cloud | False alarms | Difficulty | Mask | Audit |
|---|---|---|---|---|---|---|---|---|
| **Presidio + the fork** | 1 | **0** | **1 of 1** | **4 of 8** | **0 of 16** | **23 of 24** | 15 ms | 265 ms |
| Presidio alone | 1 | 0 | 0 of 1 | 0 of 8 | 2 of 16 | not asked | 10 ms | 0 ms |

- **Leaks** counts the listed strings that survive the mask.
- **Residual caught** counts the leaks that the fork still marks as sensitive.
  A caught leak keeps the request inside the network, so it never reaches the cloud.
- **Cleared for the cloud** counts the 8 sensitive cases that the mask made safe.
  Presidio alone can never clear a case, because a found entity always looks
  sensitive to it. The fork reads the masked text, so it can say "this is clean now".
- **False alarms** counts the 16 clean cases that got masked anyway. Presidio
  marks "France" as a location and "Paxos" as a person. The fork ignores both.

### What the fork adds, for 265 ms

1. It removes the 2 false alarms, so 2 clean requests keep the fast route.
2. It clears 4 of the 8 sensitive cases for the cloud, after the mask.
3. It catches the 1 value that Presidio cannot see: the medical fact in case r2-11.
4. It answers the difficulty question in the same call, 23 of 24, so the router
   needs no second judge.

### The 1 value that still leaks

Case r2-11 reads "My doctor wrote that I have asthma". Presidio has no
recognizer for a medical condition, and a word list is a poor fix. The fork
marks the case as sensitive with a probability of 0.73, so the router keeps the
request on the local model. The value never leaves the network.

### The 2 wording rounds

The first prompt of the audit scored badly, and the result file stays in
`results/` as proof.

| Round | Sensitivity | Difficulty | The cause |
|---|---|---|---|
| v1 | It missed both residual values | 12 of 24 | The words "already removed" made the model read the whole text as safe. The enum had no level criteria |
| v2 | It caught the residual value | 23 of 24 | It names the street and the medical fact. The enum carries the same level criteria as `../poc/router/router.yaml` |

### The recognizers that Presidio does not ship

The gate sends these in the request itself, as `ad_hoc_recognizers`, so the
analyzer image needs no change.

| Entity | Pattern | Why |
|---|---|---|
| `AWS_ACCESS_KEY` | `AKIA` or `ASIA` plus 16 characters | Case r2-08 |
| `AWS_SECRET_KEY` | 40 characters, with a context word | Case r2-08 |
| `STREET_ADDRESS` | A Dutch street word plus a house number | Case r1-10. Presidio finds "Utrecht" but not "Kerkstraat 12" |
| `PASSWORD` | The word after a `password:` label | Case r1-11 |

2 more settings keep the noise down. A span under a score of 0.4 goes away, and
the types `DATE_TIME`, `URL` and the 5 `US_` types never get a mask, because a
date or an amount breaks a tool call.

## 5. Where it runs

| Part | Host | Port | Note |
|---|---|---|---|
| Presidio analyzer | LXC 109, next to LiteLLM | 5002 | The image is `mcr.microsoft.com/presidio-analyzer` |
| Presidio anonymizer | LXC 109 | 5001 | The LiteLLM guardrail needs it. This gate does not use it |
| The llama.cpp fork | legion-t5 GPU | 11436 | 3,454 MiB. It shares the port with `llama-rerank`, so only one of the 2 runs |
| The gate | LXC 110, next to the router | 8086 | 120 MB, no model |

The LXC 109 memory went from 4,096 MB to 6,144 MB on 2026-09-24. The analyzer
holds a spaCy model, and 4 GB is not enough next to the LiteLLM stack.

## 6. The open points

1. **The fork and `llama-rerank` share port 11436 and the same card.** Only one
   of the 2 runs. `gpu-window.sh` switches between them in 1 command.
   A `/health` of 200 on that port proves nothing, because `llama-rerank` is
   also a llama-server and answers it. `/healthz` of the gate therefore sends
   1 small decision, and it reports `decision_endpoint` true or false.
2. **No real traffic ran through the gate yet.** The bench measures the decision
   and the mask, not the answer quality of a masked prompt.
3. **A mask can break an answer.** A request like "correct this address" fails
   when the model never sees the address. The bench holds no such case.
4. **The gate keeps the map in memory for the length of 1 request.** A second
   turn in the same conversation gets a new map, so an older placeholder in the
   history does not restore. This is the same limit as the open LiteLLM issue.

## 7. References

| Source | What it gave |
|---|---|
| https://docs.litellm.ai/docs/proxy/guardrails/pii_masking_v2 | The guardrail config, `output_parse_pii`, the 2 required containers |
| https://docs.litellm.ai/docs/tutorials/presidio_pii_masking | The end-to-end example of the round trip |
| https://github.com/BerriAI/litellm/issues/41600 | The counter restarts on every request. Open since 2026-09-17 |
| https://github.com/BerriAI/litellm/pull/42351 | The streaming fix for `/v1/messages`. Merged 2026-09-22. The stream buffers to the end |
| https://github.com/BerriAI/litellm/issues/31950 | A placeholder inside `tool_calls` arguments did not restore |
| https://github.com/BerriAI/litellm/pull/32014 | The fix for the row above |
| https://github.com/microsoft/presidio | The analyzer and the anonymizer, the `ad_hoc_recognizers` field |
| https://microsoft.github.io/presidio/supported_entities/ | The list of entity types |
| https://github.com/francesco-stimola/llm-proxy-pii-rust | The 3-layer detector, the per-request vault, the partial stream restore |
| https://github.com/Athroniaeth/piighost | The `<<PERSON:1>>` shape and the cross-message memory |
| https://github.com/fsndzomga/anonLLM | The smallest of the 5, names and e-mails and telephone numbers |
| https://github.com/malteos/awesome-anonymization-for-llms | The reading list for this subject |
| `../poc/decision-fork/README.md` | The field types of `/v1/decision`, and the security audit of the fork |
| `../poc/results/README.md` | The judge comparison that picked the model |
