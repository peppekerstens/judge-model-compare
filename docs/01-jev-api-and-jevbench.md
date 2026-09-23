# 01 - Jev: the TypeSafe API and JevBench

Research date: 2026-09-22. Every fact has a source link. "Not verified" means that no primary source confirms the fact.

Main sources:

- [B] Launch blog, dated 2026-09-15: https://typesafe.ai/blog/introducing-system-one-models-and-jev
- [D] TypeSafe docs index: https://docs.typesafe.ai/llms.txt
- [JB] JevBench v1.3.0: https://benchmarkheaven.com/jev-models
- [V1] Sam Witteveen, Jev intro video: https://www.youtube.com/watch?v=X117w2Rark8 (transcript fetched)
- [V2] Sam Witteveen, open Jev models video: https://www.youtube.com/watch?v=53wDOI_7x8I (transcript fetched)

## 1. What Jev is

### Summary

- Jev is the first "System One model" from TypeSafe AI, Inc. The founder is Diogo Almeida (ex-OpenAI, InstructGPT/RLHF). [B]
- Jev does not generate text. You send a `state` (text or JSON) and a map of typed questions. Jev returns typed answers with probabilities. [D: https://docs.typesafe.ai/introduction.md]
- The blog calls it "a frontier-intelligence function call: unstructured state in, typed probabilistic decisions out." [B]
- Current version: `jev-1.13.0`. The aliases `jev-latest` and `jev-preview` both point to it. [https://docs.typesafe.ai/models.md]
- Input is text only: a string, a JSON object, or an array of text. There is no image, audio, or video input. [https://docs.typesafe.ai/models.md]
- English is the main training language. Other languages work, but less well. [https://docs.typesafe.ai/models.md]

### The three question types ("primitives")

Source: https://docs.typesafe.ai/introduction.md and https://docs.typesafe.ai/api.md

| Type | Purpose | `criteria` | Answer fields |
|---|---|---|---|
| `choice` | Select one option from a set | Map of option key to description (or `null`). Max 255 options. | `choice`, `probabilities` (sum to 1), `confidence` |
| `score` | Rate the state on ordered levels | Ordered array of level descriptions. Min 2, max 10 levels. | `score` (probability-weighted, can fall between levels), `legend`, `probabilities`, `confidence` |
| `noul` | Yes/no question | Optional object with `true` and `false` descriptions | `noul` (0 to 1, the probability of "yes") |

- "Noul" is TypeSafe's name for the yes/no type. The video spells it "null". [V1] The docs spell it `noul`. [https://docs.typesafe.ai/primitives/noul.md]
- A noul answer has no `confidence` field. Only choice and score answers have it. [https://docs.typesafe.ai/api.md]
- `instructions` and `criteria` accept a string, an object, or an array. You can put data next to the question and refer to it by name in backticks. [https://docs.typesafe.ai/api.md]
- The question key that you choose is not sent to the model. [https://docs.typesafe.ai/api.md]
- Jev evaluates all questions in one request in parallel and in isolation against the same state. The docs say that more questions "barely" change the response time and do not cause context rot between questions. [https://docs.typesafe.ai/introduction.md]
- Blog: for more than 255 options, TypeSafe uses two stages (score each option, then choose). [B]

### Confidence

- `confidence` is computed from the probability distribution. It is not a separate model output. [https://docs.typesafe.ai/confidence.md]
- For a choice, the docs page code computes `(n * p_max - 1) / (n - 1)`, clipped to 0..1 (n = number of options). [https://docs.typesafe.ai/confidence.md, `choiceConfidence` function in the page source]
- The score formula for `confidence` is not published. Not verified.
- The docs suggest a start rule: below 0.5, do not act. Use a higher threshold for high-risk actions. [https://docs.typesafe.ai/confidence.md]

### Latency and cost claims (vendor claims)

- End-to-end response time is 70 ms to 500 ms. TypeSafe says this is "40x-200x faster" than frontier LLMs on System One queries. [B]
- TypeSafe ran its own evals from laptops on the US West Coast. The service runs there. [B]
- The home-page claims of "193.6x faster, 444.6x cheaper" come from the workflow evals. TypeSafe says these are "on the higher end of real world gains". [B]
- The reference answers in the workflow evals are the average of GPT-6 Astra and Fable 5.1. The eval authors are on the TypeSafe team. [B], details at https://evals.typesafe.ai/ (not fetched)
- "Can't hallucinate" means that the output always matches the schema. It does not mean that the answer is always correct. [B] [V1]
- Independent measure: JevBench measured Jev at 0.65 s p50 and 0.72 s p95 from a server in Germany, one request at a time. [JB]

### How it works (architecture)

- TypeSafe names three parts: a new model architecture, a parallel sampler, and a training method called RLCD (Reinforcement Learning for Calibrated Decisions). [B]
- RLCD trains the model to return decisions and calibrated probabilities, not text. [https://docs.typesafe.ai/introduction/machine-learning-primer.md]
- FAQ answer: "Jev is neither small nor an LLM". [B, FAQ "Is Jev just a smaller LLM?"]
- TypeSafe makes all its training data itself. It does not train on customer data. [B, FAQ] [https://docs.typesafe.ai/models.md]
- Jev has one set of weights for all accounts. There is no fine-tuning or LoRA per customer. [https://docs.typesafe.ai/models.md]
- There is no paper and no architecture diagram. [V1]
- Parameter count, base model, and architecture details: not published. Not verified.
- Sam Witteveen guesses that Jev is a transformer that uses the prefill pass and a classification or regression head. This is a guess, not a fact. [V1]
- Many open rebuilds use the same idea. They read the logits of the option tokens after one prefill pass and apply softmax. [V2] [JB, run notes]
- TypeSafe says that it will not publish results on public benchmarks. [B, FAQ "How does Jev perform against public benchmarks?"]

### Known weak points (TypeSafe's own list for jev-1.13, reviewed 2026-09-17)

Source: https://docs.typesafe.ai/model-jaggedness/jev-1.13.md

1. Literal reading of instructions.
2. Math, counting, and numeric values (hex, RGB).
3. Date and time comparison.
4. Indirection and multi-hop questions.
5. Large state with unrelated detail (context rot).
6. Adversarial content and prompt injection in the state.
7. Instructions that contradict the criteria.
8. No structural invariants. Example: `P(refund)` = 0.72 and `P(not refund)` = 0.47 on the same ticket (sum 1.19).
9. Text generation.

## 2. The TypeSafe Jev API

### Endpoint and auth

- `POST https://api.typesafe.ai/v1/systemone` [https://docs.typesafe.ai/api.md]
- Header `Authorization: Bearer <API_KEY>` and `Content-Type: application/json`. [https://docs.typesafe.ai/api.md]
- You get the key from https://console.typesafe.ai/keys. [https://docs.typesafe.ai/introduction/quickstart.md]
- `GET https://api.typesafe.ai/v1/models` lists the model names (currently the aliases). [https://docs.typesafe.ai/models.md]
- Access status: "early access". TypeSafe moves developers off a waitlist. [B]
- Errors: 401 (bad key), 422 (validation), 429 (rate limit), 529 (overloaded). Retry 429 and 529 with exponential backoff. [https://docs.typesafe.ai/api.md]

### Request and response (example from the docs)

Request [https://docs.typesafe.ai/introduction/quickstart.md]:

```json
{
  "state": "Hi, I've been trying to connect my Stripe account for 3 days and the integration keeps failing. I'm losing sales. Please help ASAP.",
  "model": "jev-latest",
  "questions": {
    "department": {
      "type": "choice",
      "instructions": "Which team should handle this",
      "criteria": {
        "billing": "Payment or subscription issues",
        "technical": "Bugs or integration problems",
        "sales": "Pricing or account questions"
      }
    },
    "frustration": {
      "type": "score",
      "instructions": "How frustrated the customer appears",
      "criteria": [
        "Calm, just stating facts",
        "Frustrated but civil",
        "Very angry, strong language"
      ]
    },
    "is_urgent": {
      "type": "noul",
      "instructions": "The message conveys urgency or time-sensitivity"
    }
  }
}
```

Response [https://docs.typesafe.ai/introduction/quickstart.md]:

```json
{
  "model": "jev-1.13.0",
  "answers": {
    "department": {
      "type": "choice",
      "choice": "technical",
      "confidence": 0.78,
      "probabilities": { "technical": 0.85, "sales": 0.0, "billing": 0.15 }
    },
    "frustration": {
      "type": "score",
      "score": 1.0,
      "confidence": 1.0,
      "legend": { "0": "Calm, just stating facts", "1": "Frustrated but civil", "2": "Very angry, strong language" },
      "probabilities": { "0": 0.0, "1": 1.0, "2": 0.0 }
    },
    "is_urgent": { "type": "noul", "noul": 1.0 }
  },
  "usage": { "input_tokens": 392, "output_tokens": 65 }
}
```

Note: this is the docs example. I did not call the API myself (no key). The response is not verified by a live call.

### SDKs

- Python: `pip install typesafe-sdk` (Python >= 3.10). Classes `TypeSafeClient`, `AsyncTypeSafeClient`, `Choice`, `Score`, `Noul`. Method `client.system_one(state=..., questions=...)`. [https://docs.typesafe.ai/introduction/quickstart.md]
- Environment variables: `TYPESAFE_API_KEY`, `TYPESAFE_BASE_URL` (default `https://api.typesafe.ai`), `TYPESAFE_DEFAULT_MODEL` (default `jev-latest`). Default timeout is 10.0 s. [https://docs.typesafe.ai/sdk/python/api/constants.md]
- JavaScript: `@typesafe-ai/sdk`. [https://docs.typesafe.ai/models.md]
- Python adapter to call LLMs in the same format: https://github.com/typesafe-ai/system-one-adapter-python (linked from [B], not read).

### Other access routes

- OpenRouter: model ids `typesafe/jev-1.13` and `~typesafe/jev-latest`. Endpoint `POST https://openrouter.ai/api/v1/systemone`, same body shape, OpenRouter key. The response adds `id`, `provider`, and `usage.cost`. [https://openrouter.ai/docs/guides/community/typesafe-sdk]
- A search snippet says that OpenRouter uses `POST https://openrouter.ai/api/alpha/decisions`. This conflicts with the OpenRouter docs page above. Not verified.
- The OpenRouter model page (https://openrouter.ai/typesafe/jev-1.13) returned HTTP 404 to my fetch. OpenRouter pricing is not verified. The public list at `openrouter.ai/api/v1/models` does not contain Jev (checked 2026-09-22).
- A Cloudflare AI docs page exists: https://developers.cloudflare.com/ai/models/typesafe/jev/ (search result only, not read). Not verified.

### Pricing

- $0.042 per million input tokens ($42 per billion). Output tokens are free. [https://docs.typesafe.ai/models.md] [B]
- The MCA uses prepaid credits. Purchased credits expire after 12 months or at the end of the term. [https://typesafe.ai/legal/mca, section on Credits]
- JevBench computes about $0.040 per 1,000 decisions for Jev (about 950 input tokens per decision). [JB]

### Rate limits and context

Source: https://docs.typesafe.ai/models.md

- 250,000 tokens per second and 1,200 requests per minute. The limits "can change without notice". Higher limits come with custom or enterprise plans.
- Context: 64k tokens per request (state plus all questions). 32k tokens for the state plus the longest question.

### Weights and terms

- Weights are closed. Access is API only. JevBench lists Jev as "proprietary API". [JB, credit list] TypeSafe publishes no weights. [https://docs.typesafe.ai/models.md]
- The Master Customer Agreement (last updated 2026-09-19) forbids use of the Services or Output "to perform model distillation, train a model to imitate the output of the Services, or develop (or to facilitate the development of) a similar or competing product or service". It also forbids reverse engineering. [https://typesafe.ai/legal/mca, customer restrictions (a)-(l)]
- Impact: do not use Jev outputs to train or label data for an open Jev-like model.
- TypeSafe does not train on customer data without consent. Zero data retention is available for enterprise customers. [https://typesafe.ai/legal/mca] [https://docs.typesafe.ai/legal.md]
- Benchmark publication: [V2] says that the terms forbid benchmarks against other models. A third-party article quotes MCA section 2.3(f), version of 2026-08-27: "publish benchmarks or performance information about the Services." [https://wunderlandmedia.com/typesafe-ai-jev-terms-of-service-gdpr]. The current MCA (2026-09-19) that I fetched has no occurrence of the word "benchmark". The clause seems to be removed. Not verified against an archived copy of the old version.

## 3. JevBench v1.3.0

Source for this section: [JB] https://benchmarkheaven.com/jev-models. The harness, public tasks, and scoring rules are MIT-licensed at https://github.com/fstandhartinger/jevbench.

### Date and setup

- Scored 21 Sept 2026. Protocol `jevbench::v1.2`. Results JSON sha256 prefix `20fce8e6e4f0`.
- 52 systems, 534 decisions: 72 easy + 96 standard + 146 judge + 220 hard.
- Requests go one at a time, with no retries, from a server in Germany. Latency includes the network.
- The data is English only. The authors call 534 decisions "a pilot, not a census".
- The authors of JevBench also run jev-router.com (self-hosted open decision models). They disclose this. It is not a ranked entrant.
- [V2] quotes an older version: Jev at 75.3 and djev at 74.3. The current v1.3.0 numbers are lower because v1.3.0 changed the scoring (chance-corrected Intelligence). v1.2 numbers are not comparable with v1.1 or v1.0.

### Tiers

- easy (72): clear-cut decisions (intent, explicit yes/no fact, enum extraction, one obvious tool).
- standard (96): authored decisions (policy, intent, extraction, ordinal, adequacy, routing).
- judge (146): imported decisions (route real task prompts into 9 categories, judge if a saved math answer is correct).
- hard (220; 111 public, 109 held out): long policy documents (2-6k tokens), trade-offs, ambiguous cases with a "no clear answer" label, traps, multi-hop lookups, date/number reasoning, adversarial distractors, subtle answer judging, overlapping routing, and 20 probability items with an exact gold distribution. Claude Opus 5 wrote half, GPT-5.6 Sol wrote half. Each model reviewed the other half.

### Metrics

- **JevBench Score**: geometric mean of the four axes, 25 % each. If Intelligence is below 50, the score is multiplied by (Intelligence / 50)^2.
- **Intelligence**: per tier, `100 x (accuracy - chance) / (1 - chance)`, clipped at 0. Chance = 1 / number of options (or levels). Tier weights: hard 30 %, easy 14 %, standard 28 %, judge 28 %. Failed or unparseable answers count as wrong.
- **Calibration**: hard tier only. Mean of (a) `100 x (1 - ECE / 0.5)`, ECE = top-label expected calibration error in 10 bins, and (b) `100 x (1 - mean total-variation distance)` to the gold distribution on the 20 probability items. Label-only systems get 0.
- **Speed**: mean of score(p50) and score(p95) on the 242 standard+judge decisions. `score(s) = 100 - 20 log10(s / 0.1 s)`, clipped to 0..100 (0.1 s = 100, 1 s = 80, 10 s = 60). Self-hosted and demo endpoints get an adjustment of x2 latency (+0.15 s on the authors' servers). Production APIs are not adjusted.
- **Cost**: US dollars per 1,000 decisions (not tokens). `score = 100 - 30 log10(usd / 0.001)`, clipped ($0.001 = 100, $0.01 = 70, $0.10 = 40, $1 = 10). "est." = hosted price of the same weights or size class. "announced" = published price, not yet charged.
- **Ranked**: only a system's own model, with each tier attempted for >= 95 % of its decisions.

### Full results table (copied from [JB], 2026-09-21 data)

Columns: Score = JevBench Score. I = Intelligence, C = Calibration, S = Speed, K = Cost (axis scores, 0-100). $/1k = US dollars per 1,000 decisions. Easy/Std/Judge/Hard = accuracy per tier. Latency = p50 and p95, raw and adjusted. "Weights" is my own label from the JevBench credit list. † = JevBench has a run note for this system.

| Rank | System | Weights | Score | I | C | S | K | $/1k | Easy | Std | Judge | Hard | Latency | Endpoint |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | TypeSafe AI Jev 1.13.0 | closed (API) | 74.4 | 85.7 | 82.7 | 83.3 | 52.0 | $0.040 | 100.0% | 99.0% | 94.5% | 74.1% | 0.65 s raw p95 0.72 s raw | production API |
| 2 | Theodore Lee (TheoLeeCJ) SemIf formerly OpenJev (Qwen3.5-4B, TheoLeeCJ | open | 73.1 | 79.0 | 72.6 | 83.7 | 59.5 | ~ $0.022 est. | 100.0% | 97.9% | 95.2% | 59.5% | 0.20 s raw -> 0.55 s adjusted p95 0.32 s raw -> 0.78 s | our RunPod GPU |
| 3 | Maisa (David Villalón) djev † Maisa, diffusion-gemma | open | 73.0 | 82.7 | 65.4 | 91.4 | 57.6 | $0.026 announced | 100.0% | 97.9% | 93.2% | 69.5% | 0.24 s raw p95 0.31 s raw | production API |
| 4 | Eldan Ring Winnow-12B Q8 † | open | 71.2 | 82.0 | 72.0 | 82.3 | 52.9 | ~ $0.037 est. | 100.0% | 96.9% | 91.1% | 70.9% | 0.23 s raw -> 0.60 s adjusted p95 0.41 s raw -> 0.98 s | our RunPod GPU |
| 5 | kshetrajna12 reflex 4B † | open | 70.3 | 80.1 | 75.2 | 68.0 | 59.7 | ~ $0.022 est. | 100.0% | 94.8% | 97.3% | 63.2% | 1.80 s raw -> 3.75 s adjusted p95 2.05 s raw -> 4.26 s | our RunPod GPU |
| 6 | hjmurmur (Octalab) jqv † Qwen3-32B zero-shot | open | 68.6 | 79.3 | 79.0 | 74.6 | 47.5 | ~ $0.056 est. | 100.0% | 95.8% | 92.5% | 64.5% | 0.75 s raw -> 1.64 s adjusted p95 0.97 s raw -> 2.10 s | our RunPod GPU |
| 7 | milliseconds.ai (Baptiste Laget) decision-machine-1 † milliseconds.ai | closed (API) | 68.3 | 62.1 | 70.4 | 92.9 | 53.7 | $0.035 | 100.0% | 76.0% | 89.7% | 46.8% | 0.17 s raw p95 0.30 s raw | production API |
| 8 | Mapika decider-35b-a3b † | open | 67.6 | 79.6 | 71.5 | 80.8 | 45.3 | ~ $0.067 est. | 100.0% | 96.9% | 91.1% | 65.5% | 0.29 s raw -> 0.73 s adjusted p95 0.49 s raw -> 1.14 s | our RunPod GPU |
| 9 | IkerMoel open-alternative-jev † Qwen3.5-4B, IkerMoel | open | 67.0 | 64.0 | 63.2 | 83.5 | 59.6 | ~ $0.022 est. | 100.0% | 84.4% | 74.7% | 56.8% | 0.21 s raw -> 0.56 s adjusted p95 0.32 s raw -> 0.80 s | our RunPod GPU |
| 10 | mithalouni system-one-open Gemma 4 E2B LoRA on an L4 | open | 66.6 | 69.5 | 56.7 | 77.0 | 64.8 | ~ $0.015 est. | 100.0% | 93.8% | 87.7% | 49.1% | 0.65 s raw -> 1.30 s adjusted p95 0.77 s raw -> 1.54 s | author's demo server |
| 11 | razorback16 / Codiv OpenJev DiffusionGemma 26B-A4B NVFP4, razorback16 | open | 66.4 | 79.2 | 64.8 | 83.2 | 45.5 | ~ $0.066 est. | 100.0% | 95.8% | 91.1% | 65.5% | 0.24 s raw -> 0.63 s adjusted p95 0.31 s raw -> 0.76 s | our RunPod GPU |
| 12 | Featherless AI SimpleJev Qwen3.8-27B † | open | 66.3 | 84.7 | 81.1 | 71.2 | 39.5 | ~ $0.104 est. | 100.0% | 96.9% | 93.2% | 75.0% | 1.01 s raw -> 2.03 s adjusted p95 1.88 s raw -> 3.76 s | author's demo server |
| 13 | ZeroEntropy ZeroEntropy zerank-2 † | open | 66.0 | 63.0 | 76.5 | 79.0 | 49.8 | $0.047 | 100.0% | 79.2% | 88.4% | 47.3% | 0.13 s raw -> 0.40 s adjusted p95 1.50 s raw -> 3.15 s | our RunPod GPU |
| 14 | OpenAI GPT-5.6 Luna low reasoning effort | closed (API) | 65.9 | 95.3 | 89.8 | 77.5 | 28.5 | $0.242 | 100.0% | 97.9% | 96.6% | 94.5% | 0.97 s raw p95 1.82 s raw | production API |
| 15 | ekzhang openjev-sglang Qwen3.6-35B-A3B on SGLang | open | 65.3 | 83.4 | 77.4 | 77.1 | 36.5 | ~ $0.131 est. | 100.0% | 95.8% | 95.2% | 71.4% | 0.68 s raw -> 1.36 s adjusted p95 0.73 s raw -> 1.45 s | author's demo server |
| 16 | Qwen Qwen3-Reranker-4B † | open | 63.8 | 64.0 | 67.0 | 78.7 | 49.2 | $0.050 | 100.0% | 79.2% | 87.7% | 50.0% | 0.13 s raw -> 0.41 s adjusted p95 1.56 s raw -> 3.27 s | our RunPod GPU |
| 17 | kshetrajna12 reflex-27b † Qwen3.8-27B | open | 63.3 | 85.8 | 86.2 | 67.5 | 32.3 | ~ $0.181 est. | 100.0% | 95.8% | 95.9% | 75.9% | 1.89 s raw -> 3.93 s adjusted p95 2.21 s raw -> 4.57 s | our RunPod GPU |
| 18 | Zhengxu Yu LitJev † Qwen3.8-27B | open | 62.7 | 82.4 | 83.5 | 66.7 | 33.6 | ~ $0.163 est. | 100.0% | 97.9% | 88.4% | 73.2% | 2.03 s raw -> 4.20 s adjusted p95 2.46 s raw -> 5.06 s | our RunPod GPU |
| 19 | Jared Palmer kev 0.6B † research preview | open | 62.5 | 51.9 | 51.1 | 75.6 | 76.1 | ~ $0.0063 est. | 100.0% | 81.3% | 66.4% | 40.0% | 0.59 s raw -> 1.33 s adjusted p95 0.97 s raw -> 2.09 s | our RunPod GPU |
| 20 | Featherless AI SimpleJev Qwen3.6-35B-A3B † | open | 62.5 | 79.5 | 67.1 | 75.0 | 38.1 | ~ $0.116 est. | 100.0% | 93.8% | 93.2% | 66.4% | 0.85 s raw -> 1.70 s adjusted p95 0.93 s raw -> 1.86 s | author's demo server |
| 21 | David Villalon / Maisa djev † thinking | open | 62.4 | 80.8 | 92.7 | 75.2 | 26.9 | ~ $0.274 est. | 95.8% | 99.0% | 80.1% | 77.7% | 0.43 s raw -> 1.00 s adjusted p95 1.45 s raw -> 3.05 s | our RunPod GPU |
| 22 | us (GitHub) jev-local † Qwen3.5-9B | open | 61.8 | 70.8 | 68.7 | 69.2 | 43.3 | ~ $0.077 est. | 100.0% | 84.4% | 89.0% | 59.1% | 1.05 s raw -> 2.24 s adjusted p95 2.62 s raw -> 5.38 s | our RunPod GPU |
| 23 | Mapika decider-2b † | open | 61.7 | 61.2 | 46.6 | 83.2 | 61.0 | ~ $0.020 est. | 100.0% | 85.4% | 77.4% | 47.3% | 0.26 s raw -> 0.67 s adjusted p95 0.28 s raw -> 0.72 s | our RunPod GPU |
| 24 | Bespoke Labs Bespoke Nimble 9B † | open | 60.5 | 77.9 | 65.3 | 78.7 | 33.4 | ~ $0.166 est. | 100.0% | 94.8% | 89.0% | 65.5% | 0.39 s raw -> 0.93 s adjusted p95 0.65 s raw -> 1.46 s | our RunPod GPU |
| 25 | Google Gemini 3.1 Flash-Lite | closed (API) | 60.1 | 85.6 | 68.1 | 81.8 | 27.4 | $0.264 | 100.0% | 99.0% | 93.2% | 75.0% | 0.76 s raw p95 0.88 s raw | production API |
| 26 | razorback16 OpenJev † thinking, BF16 | open | 60.0 | 88.0 | 69.6 | 76.1 | 27.8 | ~ $0.255 est. | 100.0% | 100.0% | 94.5% | 78.2% | 0.46 s raw -> 1.08 s adjusted p95 1.08 s raw -> 2.31 s | our RunPod GPU |
| 27 | Jared Palmer kev 4B † research preview | open | 59.7 | 64.8 | 42.0 | 75.7 | 61.8 | ~ $0.019 est. | 100.0% | 91.7% | 85.6% | 42.3% | 0.55 s raw -> 1.25 s adjusted p95 0.99 s raw -> 2.13 s | our RunPod GPU |
| 28 | DeepSeek DeepSeek V4.1 Flash thinking default | open weights, API route used | 57.5 | 94.3 | 96.7 | 71.6 | 16.8 | $0.594 | 98.6% | 99.0% | 93.2% | 95.0% | 1.42 s raw p95 4.89 s raw | production API |
| 29 | Jared Palmer kev 8B † research preview | open | 56.4 | 69.4 | 44.2 | 74.9 | 44.0 | ~ $0.073 est. | 100.0% | 92.7% | 90.4% | 47.3% | 0.59 s raw -> 1.33 s adjusted p95 1.15 s raw -> 2.45 s | our RunPod GPU |
| 30 | Zefan Cai (@Zefan_Cai) Open-Jev 9B † Zefan Cai | open | 55.0 | 71.2 | 63.3 | 72.0 | 28.1 | ~ $0.249 est. | 100.0% | 90.6% | 81.5% | 60.9% | 0.75 s raw -> 1.66 s adjusted p95 1.81 s raw -> 3.77 s | our RunPod GPU |
| 31 | Sean Goedecke system-one Qwen3-8B, Sean Goedecke | open | 54.8 | 70.3 | 36.8 | 84.4 | 41.5 | ~ $0.089 est. | 100.0% | 90.6% | 91.8% | 50.0% | 0.17 s raw -> 0.48 s adjusted p95 0.30 s raw -> 0.76 s | our RunPod GPU |
| 32 | Logan Markewich jeff † Logan Markewich, GLiFormer 400M | open | 54.4 | 46.9 | 64.6 | 63.5 | 76.6 | ~ $0.0060 est. | 100.0% | 76.0% | 61.6% | 37.7% | 0.94 s raw -> 2.03 s adjusted p95 10.97 s raw -> 22.09 s | our CPU |
| 33 | Convai Innovations Laya † Convai Innovations, ModernBERT-large 421M | open | 54.4 | 45.8 | 62.5 | 71.1 | 86.2 | ~ $0.0029 est. | 94.4% | 72.9% | 69.2% | 34.1% | 0.79 s raw -> 1.72 s adjusted p95 2.20 s raw -> 4.54 s | our CPU |
| 34 | Zefan Cai (@Zefan_Cai) Open-Jev 2B † Zefan Cai | open | 51.3 | 61.0 | 55.1 | 73.5 | 28.1 | ~ $0.249 est. | 100.0% | 79.2% | 88.4% | 42.7% | 0.66 s raw -> 1.48 s adjusted p95 1.45 s raw -> 3.05 s | our RunPod GPU |
| 35 | Deepan Wadhwa OpenDecision † ModernBERT-large zero-shot | open | 40.6 | 40.8 | 56.1 | 79.9 | 75.3 | ~ $0.0066 est. | 87.5% | 62.5% | 71.2% | 33.2% | 0.34 s raw -> 0.83 s adjusted p95 0.54 s raw -> 1.24 s | our RunPod GPU |
| 36 | Hemant (heman10x) openJev Verdict 1.4 † | open | 38.9 | 38.6 | 74.1 | 78.1 | 82.4 | ~ $0.0039 est. | 86.1% | 67.7% | 56.2% | 37.7% | 0.31 s raw -> 0.78 s adjusted p95 0.92 s raw -> 2.00 s | our CPU |
| 37 | Hemant (heman10x) openJev Verdict † heman10x, ModernBERT-base 151M | open | 38.1 | 39.8 | 51.3 | 76.7 | 83.1 | ~ $0.0037 est. | 86.1% | 65.6% | 61.0% | 38.2% | 0.28 s raw -> 0.71 s adjusted p95 1.45 s raw -> 3.04 s | our CPU |
| 38 | Jared Palmer kev 0.5B † | open | 33.2 | 38.2 | 47.4 | 77.0 | 76.1 | ~ $0.0063 est. | 95.8% | 52.1% | 71.2% | 30.9% | 0.43 s raw -> 1.01 s adjusted p95 0.92 s raw -> 1.99 s | our RunPod GPU |
| 39 | Fastino GLiNER2 large † | open | 29.6 | 40.1 | 24.3 | 61.7 | 73.3 | ~ $0.0077 est. | 98.6% | 62.5% | 61.0% | 36.4% | 1.10 s raw -> 2.34 s adjusted p95 14.49 s raw -> 29.13 s | our CPU |
| 40 | Aditya (isHeSatoshi) smalljev semantic-v9 † | open | 27.4 | 35.1 | 58.9 | 79.8 | 57.9 | ~ $0.025 est. | 97.2% | 68.8% | 40.4% | 38.2% | 0.41 s raw -> 0.98 s adjusted p95 0.46 s raw -> 1.07 s | our RunPod GPU |
| 41 | Fastino GLiNER2 † Fastino, gliner2.5-base | open | 24.0 | 35.6 | 23.7 | 71.8 | 83.1 | ~ $0.0037 est. | 97.2% | 66.7% | 45.9% | 36.4% | 0.31 s raw -> 0.78 s adjusted p95 4.15 s raw -> 8.46 s | our CPU |
| 42 | Kotoba Labs open-jev-deberta-v3-large local CPU | open | 23.1 | 31.9 | 66.4 | 66.0 | 74.0 | ~ $0.0073 est. | 100.0% | 49.0% | 53.4% | 36.4% | 1.77 s raw -> 3.69 s adjusted p95 3.35 s raw -> 6.85 s | our CPU |
| 43 | Fastino GLiNER2.5 multi † Fastino, 287M | open | 16.6 | 27.7 | 56.1 | 67.8 | 82.4 | ~ $0.0039 est. | 90.3% | 51.0% | 43.8% | 37.7% | 0.43 s raw -> 1.01 s adjusted p95 8.18 s raw -> 16.50 s | our CPU |
| 44 | Fastino GLiNER2.5 small † Fastino, 74M | open | 13.8 | 25.6 | 47.2 | 77.8 | 82.4 | ~ $0.0039 est. | 83.3% | 47.9% | 50.0% | 33.2% | 0.11 s raw -> 0.38 s adjusted p95 2.10 s raw -> 4.35 s | our CPU |
| 45 | Mixedbread Mixedbread mxbai-rerank-base-v2 † | open | 0.8 | 6.7 | 83.1 | 87.5 | 67.9 | $0.012 | 44.4% | 33.3% | 26.7% | 40.0% | 0.07 s raw -> 0.29 s adjusted p95 0.23 s raw -> 0.62 s | our RunPod GPU |
| 46 | BAAI BAAI bge-reranker-v2-m3 † | open | 0.7 | 6.3 | 83.8 | 89.5 | 73.4 | $0.0077 | 43.1% | 36.5% | 8.9% | 36.8% | 0.03 s raw -> 0.22 s adjusted p95 0.18 s raw -> 0.51 s | our RunPod GPU |
| 47 | Alibaba-NLP Alibaba GTE Reranker ModernBERT-base † | open | 0.3 | 4.6 | 76.8 | 90.6 | 69.6 | $0.010 | 33.3% | 39.6% | 30.1% | 33.6% | 0.05 s raw -> 0.25 s adjusted p95 0.10 s raw -> 0.35 s | our RunPod GPU |
| 48 | AltSlate Labs Certo v1 † | open | 0.0 | 0.0 | 82.0 | 94.0 | 100.0 | ~ $0.0010 est. | 27.8% | 30.2% | 21.9% | 31.8% | 0.02 s raw -> 0.19 s adjusted p95 0.03 s raw -> 0.21 s | our RunPod GPU |
| - | mrmps (@michael_chomsky) classifier.dev † fast tier honorable mention · not ranked | service on Jev (closed model, MIT code) | 83.6 | 85.1 | 77.9 | 87.6 | 84.3 | ~ $0.0033 est. | 100.0% | 99.0% | 97.3% | 70.5% | 0.39 s raw p95 0.45 s raw | production API |
| - | Qwen / Chutes Qwen3.8 27B Chutes TEE partial run · not ranked | open | 24.8 | 67.4 | 92.1 | 61.3 | 0.0 | ~ $2.669 est. | 98.6% | 99.0% | 95.3% | 21.4% | 5.75 s raw p95 12.97 s raw | production API |
| - | Cactus Compute Needle 3, options as tools post-hoc adapter mode partial run · not ranked | open | 1.1 | 13.5 | none (label only) | 52.8 | 65.3 | ~ $0.014 est. | 66.7% | 31.3% | 34.2% | — | 3.78 s raw -> 7.71 s adjusted p95 33.64 s raw -> 67.42 s | our CPU |
| - | Cactus Compute Needle 3 Cactus, 2-bit, local CPU partial run · not ranked | open | 0.1 | 4.6 | none (label only) | 59.9 | 58.7 | ~ $0.024 est. | 47.2% | 16.7% | 31.5% | 7.7% | 1.69 s raw -> 3.52 s adjusted p95 14.36 s raw -> 28.88 s | our CPU |
The first 48 rows are ranked. `classifier.dev` is an honorable mention: it runs Jev ("model": "jev-1.13.0"), so JevBench does not rank it. The last 3 rows are partial runs (a tier below 95 % attempted), not ranked. [JB]

### Topic accuracy, Jev 1.13.0 compared with SemIf (all tiers, not part of the score) [JB]

| Topic (items) | Jev 1.13.0 | SemIf |
|---|---|---|
| Math & numbers (129) | 87.6% | 79.1% |
| Coding & software (56) | 83.9% | 96.4% |
| Rules, policy & law (67) | 83.6% | 64.2% |
| Finance & commerce (64) | 73.4% | 60.9% |
| Support & operations (119) | 89.1% | 87.4% |
| Everyday language (79) | 100.0% | 100.0% |
| Safety & security (20) | 100.0% | 75.0% |

### Hard tier, public compared with held-out (selected rows) [JB]

The noise is about +/-9 points. The field mean gap is -0.7 points over 49 complete systems.

| System | Hard public | Hard held-out | Gap |
|---|---|---|---|
| Jev 1.13.0 | 73.0% (81/111) | 75.2% (82/109) | -2.3 |
| SemIf | 61.3% (68/111) | 57.8% (63/109) | +3.5 |
| djev (Maisa, diffusion-gemma) | 67.6% (75/111) | 71.6% (78/109) | -4.0 |
| decider-35b-a3b | 66.7% (74/111) | 64.2% (70/109) | +2.4 |
| decider-2b | 49.5% (55/111) | 45.0% (49/109) | +4.6 |
| Bespoke Nimble 9B | 62.2% (69/111) | 68.8% (75/109) | -6.6 |
| GPT-5.6 Luna (low) | 96.4% (107/111) | 92.7% (101/109) | +3.7 |
| DeepSeek V4.1 Flash | 96.4% (107/111) | 93.6% (102/109) | +2.8 |

### Key observations from the table

- Jev 1.13.0 is #1 at 74.4. SemIf (frozen Qwen3.5-4B, logit readout, no training) is #2 at 73.1. djev (DiffusionGemma 26B-A4B, no own weights) is #3 at 73.0. [JB]
- On the hard tier, Jev gets 74.1 %. The best open rows are OpenJev thinking (78.2 %), djev thinking (77.7 %), reflex-27b (75.9 %), and SimpleJev Qwen3.8-27B (75.0 %). All of these use 26B or 27B models. They cost 2.6x to 6.9x more per decision than Jev. [JB]
- The best small open rows on the hard tier: Winnow-12B Q8 70.9 %, djev 69.5 %, reflex 4B 63.2 %, SemIf 59.5 %. [JB]
- GPT-5.6 Luna (low) has the highest Intelligence (95.3) and hard accuracy (94.5 %). It costs $0.242 per 1,000 decisions (about 6x Jev). [JB]
- Generic rerankers (bge, mxbai, GTE) have Intelligence below 7 and score near 0. Zerank-2 and Qwen3-Reranker-4B do better (66.0 and 63.8). [JB]
- [V2] says the open projects are close on easy and standard items, but there is "a real gap" on hard items (multi-hop, date arithmetic).

### Systems that JevBench could not measure [JB]

open-jev (Dasein Labs, MLX only), open-jev (JoshuaSP, no host), mini-jev (no Score type), system-one-gemma (gated licence), jevlike (vision only), AlexWortega/openjev (no distribution over labels), Needle 3 native mode, Succinct Router 14M, jev-model-router / Director / Loki (applications), ProgramAsWeights, EigenJev (auth only), NanoJev (different schema), Werr (missing module, telemetry), DIY Jev (404), SimpleJev RWKV variants (no provenance).

## Open items (not verified)

1. A live API call. I had no TypeSafe key.
2. The formula for score `confidence`.
3. Jev architecture and parameter count.
4. OpenRouter price and the correct OpenRouter endpoint path (`/api/v1/systemone` or `/api/alpha/decisions`).
5. The exact text and removal date of the old benchmark-publication clause (MCA 2026-08-27, section 2.3(f)).
6. The workflow eval details at https://evals.typesafe.ai/.
