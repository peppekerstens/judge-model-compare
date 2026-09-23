# Judge model comparison (2026-09-23)

Result: **Qwen3.5-4B Q4_K_M is the best judge.** It reads 23 of 24 cases the way we want. It is faster than the 9B model (0.60 s against 0.88 s), and it uses 3,568 MiB instead of 5,932 MiB. The 9B model reads 22 of 24 cases right. The 2B model is not usable, because it calls almost every request hard.

The 3 Qwen models read the sensitivity question right in every case, 24 of 24.

The same 4B model on the llama.cpp fork answers both questions in 1 call. It is 2.2 times faster (0.28 s against 0.51 s), and it reads 21 of 24 cases right. It misses 2 sensitivity cases that the letter method reads right.

Laya multilingual joined the bench on 2026-09-23 as a fourth judge. It reads 4 of 24 cases right, so it is not usable without a fine-tune. It ran twice: on the CPU and on the GPU of legion-t5.

## Method

- The judge bench (`judge_bench.py`) calls the judge service directly. It runs no answer model and it sends no cloud request, so the numbers show only the judge.
- The question wording comes from `router/router.yaml`, so the bench asks exactly what the router asks.
- The cases live in `judge_cases.jsonl`, with the wanted answer for each case. Round 1 has 12 plain cases. Round 2 has 12 harder cases: an internal IP address, a telephone number, an AWS key, a salary list, a medical fact, and difficulty near the border between 2 levels.
- The end-to-end test (`run_tests.py`) sends 7 real requests through the router, 5 normal and 2 as a stream. It checks the route against the expected route.
- The model swap uses `switch_judge.sh`. It serves the GGUF on legion-t5 and points the container at the matching tokenizer.
- Each model ran the cases once. There are no repeat draws.
- The judge `qwen3.5-4b-decision-fork` is the same GGUF, served by the llama.cpp fork with the `/v1/decision` endpoint. The judge service for it is `poc/decision-judge/` on LXC 110, port 8085.
- The 3 Qwen judges run in llama-server on the legion-t5 GPU. Laya runs in a Podman container on legion-t5: port 8082 on the CPU, and port 8083 on the GPU.

## Why the test stopped at 24 cases

The rule was to add cases as long as the models answer the same. Round 1 already separated the 2B model (8 of 12) from the 4B and the 9B model (12 of 12 each). Round 2 separated the 4B model (11 of 12) from the 9B model (10 of 12). After that difference, more cases add cost but no new decision.

## Judge bench: 24 cases, both questions

| Judge model | VRAM | Sensitive | Difficulty | Both | Median time | Mean time | Slowest |
|---|---|---|---|---|---|---|---|
| Qwen/Qwen3.5-2B | 1,712 MiB | 24/24 | 12/24 | 12/24 | 0.41 s | 0.48 s | 1.78 s |
| Qwen/Qwen3.5-4B | 3,568 MiB | 24/24 | 23/24 | 23/24 | 0.51 s | 0.60 s | 1.88 s |
| Qwen/Qwen3.5-9B | 5,932 MiB | 24/24 | 22/24 | 22/24 | 0.80 s | 0.88 s | 2.20 s |
| qwen3.5-4b-decision-fork | 3,452 MiB | 22/24 | 23/24 | 21/24 | 0.28 s | 0.27 s | 0.41 s |
| qwen3.5-4b-decision-fork-true_only | 3,452 MiB | 22/24 | 23/24 | 21/24 | 0.25 s | 0.29 s | 0.51 s |
| qwen3.5-4b-decision-fork-both | 3,452 MiB | 20/24 | 23/24 | 19/24 | 0.23 s | 0.27 s | 0.47 s |
| qwen3.5-4b-decision-fork-enum | 3,452 MiB | 21/24 | 20/24 | 17/24 | 0.29 s | 0.28 s | 0.41 s |
| convaiinnovations/laya-multilingual | none, CPU | 14/24 | 6/24 | 4/24 | 0.48 s | 1.35 s | 19.15 s |
| laya-multilingual-gpu | 1,715 MiB | 14/24 | 6/24 | 4/24 | 0.20 s | 0.59 s | 10.02 s |

### The cases that a judge reads differently

| Case | Wanted | Qwen3.5-2B | Qwen3.5-4B | Qwen3.5-9B | 4B on the fork | Laya CPU | Laya GPU |
|---|---|---|---|---|---|---|---|
| r1-02 | simple, sensitive False | hard | ok | ok | ok | ok | ok | ok | hard | hard |
| r1-03 | simple, sensitive False | ok | ok | ok | ok | ok | ok | ok | ok, sensitive True | ok, sensitive True |
| r1-04 | medium, sensitive False | hard | ok | ok | ok | ok | ok | ok | simple | simple |
| r1-05 | medium, sensitive False | ok | ok | ok | ok | ok | ok | ok | simple, sensitive True | simple, sensitive True |
| r1-06 | medium, sensitive False | hard | ok | ok | ok | ok | ok | ok | simple, sensitive True | simple, sensitive True |
| r1-07 | hard, sensitive False | ok | ok | ok | ok | ok | ok | ok | simple | simple |
| r1-08 | hard, sensitive False | ok | ok | ok | ok | ok | ok | ok | simple | simple |
| r1-09 | hard, sensitive False | ok | ok | ok | ok | ok | ok | ok | simple | simple |
| r1-10 | simple, sensitive True | ok | ok | ok | ok | ok | ok, sensitive False | ok, sensitive False | ok, sensitive False | ok, sensitive False |
| r1-11 | medium, sensitive True | hard | ok | ok | ok | ok | ok | ok | simple, sensitive False | simple, sensitive False |
| r1-12 | hard, sensitive True | ok | ok | ok | ok | ok | ok | ok | simple, sensitive False | simple, sensitive False |
| r2-01 | medium, sensitive True | hard | ok | ok | ok | ok | ok, sensitive False | ok | simple, sensitive False | simple, sensitive False |
| r2-02 | simple, sensitive True | hard | ok | ok | ok, sensitive False | ok, sensitive False | ok, sensitive False | ok, sensitive False | hard | hard |
| r2-03 | medium, sensitive False | hard | ok | ok | ok | ok | ok | ok | simple, sensitive True | simple, sensitive True |
| r2-04 | hard, sensitive False | ok | ok | ok | ok | ok | ok | medium | simple, sensitive True | simple, sensitive True |
| r2-05 | hard, sensitive True | ok | ok | ok | ok | ok | ok | medium | simple | simple |
| r2-06 | simple, sensitive False | hard | ok | ok | ok | ok | ok | ok | ok | ok |
| r2-07 | hard, sensitive False | ok | ok | ok | ok | ok | ok | ok | simple | simple |
| r2-08 | medium, sensitive True | hard | ok | hard | ok | ok | ok | simple | simple | simple |
| r2-09 | medium, sensitive False | simple | simple | simple | simple | simple | simple | simple | simple, sensitive True | simple, sensitive True |
| r2-10 | hard, sensitive False | ok | ok | ok | ok | ok | ok | ok | simple | simple |
| r2-11 | simple, sensitive True | hard | ok | ok | ok, sensitive False | ok, sensitive False | ok, sensitive False | ok, sensitive False | ok | ok |
| r2-12 | simple, sensitive False | hard | ok | ok | ok | ok | ok | ok | ok | ok |

## End-to-end router test: 7 examples

| Judge model | Routes correct | Mean judge time | Slowest judge time |
|---|---|---|---|
| Qwen/Qwen3.5-4B | 7/7 | 0.62 s | 0.90 s |
| Qwen/Qwen3.5-9B | 7/7 | 0.88 s | 1.14 s |

## What the numbers mean

1. **The sensitivity question is easy.** Every model, down to 2B, found the personal data, the password, the AWS key, the salary list, the medical fact and the internal IP address. The rule "sensitive data stays local" is therefore safe with a small model.
2. **The difficulty question is the hard one.** The 2B model answers "hard" for almost every request. In the router that sends nearly all traffic to the cloud, which is the opposite of what you want.
3. **A bigger judge is not better here.** The 9B model reads r2-08 as hard, which the 4B model reads right. Both read r2-09 as simple, and we wanted medium. That case is a rewrite task with numbers, and the border between simple and medium is thin there.
4. **The GPU makes Laya 2.6 times faster, and it changes no answer.** Every one of the 24 cases gives the same answer on the CPU and on the GPU. Only the time differs.

| Laya multilingual | Median | Warm mean | First call | VRAM | Image |
|---|---|---|---|---|---|
| CPU, 12 cores | 0.48 s | 0.58 s | 19.2 s | none | 1.97 GB |
| GPU, RTX 3060 Ti | **0.20 s** | **0.18 s** | 10.0 s | 1,715 MiB | 3.9 GB |

The first call of each run loads the model, so it is much slower. The warm mean leaves those 2 calls out. On the GPU, Laya is faster than every Qwen judge (0.20 s against 0.51 s for the 4B model), but it reads far fewer cases right.

5. **Laya needs a fine-tune.** The multilingual checkpoint reads 14 of 24 sensitivity answers and 6 of 24 difficulty answers right. It calls almost every request simple, and it misses personal data in 10 cases. The author says the same in the README: the base checkpoints score near random zero-shot, and Laya is "a fast base to specialise". It runs on the CPU of legion-t5, so it costs no VRAM, and it answers in 0.5 to 0.8 s after the first call.
6. **The fork trades 2 sensitivity answers for speed.** The same Qwen3.5-4B model, through `/v1/decision`, needs 0.28 s instead of 0.51 s for both questions. It answers both fields in 1 call, with real words instead of letters. It reads r2-02 (a telephone number) and r2-11 (a medical fact) as not sensitive, which the letter method reads right. The difficulty score is the same, 23 of 24.

| Qwen3.5-4B | Calls | Median time | Sensitive | Difficulty | Both |
|---|---|---|---|---|---|
| Letter method, 2 calls | 2 | 0.51 s | 24/24 | 23/24 | 23/24 |
| Fork, `/v1/decision` | 1 | **0.28 s** | 22/24 | 23/24 | 21/24 |

**The wording test of 2026-09-23 ran, and it failed to fix the 2 cases.** The 3 variants:

| Variant | Sensitivity field | Sensitive | Difficulty | Both |
|---|---|---|---|---|
| `true_only` | The question plus the text for true | **22/24** | **23/24** | **21/24** |
| `both` | Also the text for false | 20/24 | 23/24 | 19/24 |
| `enum` | An enum with the values yes and no | 21/24 | 20/24 | 17/24 |

More text makes it worse, not better. The first version stays the best. The `enum` variant also hurts the difficulty question, which drops from 23 to 20. The cause is therefore not the missing text for the false side.

**Verdict: the letter method stays the judge of the router.** It reads 24 of 24 sensitivity cases right. The fork keeps its speed win, and it loses 2 sensitivity cases that we cannot fix with wording.

7. **Cost of a judge call:** 0.60 s with the 4B model for both questions. The 9B model needs 0.88 s, which is 47 % more, for a worse score.

## Files

| File | What |
|---|---|
| `judge_cases.jsonl` | The 24 cases with the wanted answers, in 2 rounds |
| `judge_bench.py` | The judge bench. It writes `results/judge-<model>-r<rounds>-<date>.json` |
| `run_tests.py` | The end-to-end router test. It writes `results/<model>-<date>.json` |
| `results_table.py` | It builds the tables in this file from those result files |
| `switch_judge.sh` | It switches the judge model on legion-t5 and in the container |
| `laya/` | The Laya judge: the same `/v1/systemone` shape, in a Podman container on legion-t5 port 8082 |

## Repeat the test

```sh
cd poc
./switch_judge.sh 2b && python3 judge_bench.py
./switch_judge.sh 4b && python3 judge_bench.py && python3 run_tests.py
./switch_judge.sh 9b && python3 judge_bench.py && python3 run_tests.py
./switch_judge.sh 4b          # 4B stays the judge of the proof of concept
python3 results_table.py > results/tables.md
```

Time: about 2 minutes for each judge bench, and about 3 minutes for each end-to-end run.

The Laya judge runs on legion-t5 in Podman, on the CPU. The firewall there blocks port 8082, so the bench uses an SSH tunnel:

```sh
ssh -f -N -L 18082:127.0.0.1:8082 legion
python3 judge_bench.py --judge http://127.0.0.1:18082 --label laya-multilingual
```
