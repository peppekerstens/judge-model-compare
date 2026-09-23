# The judge on the fork endpoint

This service speaks the same `/v1/systemone` shape as the SemIf judge and the Laya judge. Inside, it sends 1 call to the llama.cpp fork endpoint `/v1/decision`. The fork itself is in `../decision-fork/`.

## Result, 2026-09-23

The same model, Qwen3.5-4B Q4_K_M, on the same GPU.

| Qwen3.5-4B | Calls per request | Median time | Sensitive | Difficulty | Both |
|---|---|---|---|---|---|
| Letter method (`semif-judge`) | 2 | 0.51 s | 24/24 | 23/24 | **23/24** |
| The fork (`decision-judge`) | 1 | **0.28 s** | 22/24 | 23/24 | 21/24 |

The fork is 2.2 times faster and reads 2 sensitivity cases wrong: r2-02, a telephone number, and r2-11, a medical fact. The difficulty score is equal.

### The wording test, 2026-09-23

I tested 3 ways to put the sensitivity question into the schema. The variable is `NOUL_MODE`.

| `NOUL_MODE` | The field | Sensitive | Difficulty | Both |
|---|---|---|---|---|
| `true_only` | A boolean, with the question plus the text for true | **22/24** | **23/24** | **21/24** |
| `both` | A boolean, with the text for true and for false | 20/24 | 23/24 | 19/24 |
| `enum` | An enum with the values yes and no | 21/24 | 20/24 | 17/24 |

More text in the description makes the answer worse. The `enum` variant also pulls the difficulty score down, from 23 to 20. The missing text for the false side is therefore not the cause.

**Verdict: the router keeps the letter method.** That method reads 24 of 24 sensitivity cases right. The fork keeps a real speed win for the difficulty question, at 23 of 24.

## How the mapping works

| Our question | In the fork schema |
|---|---|
| `noul`, with a text for true and false | A `boolean` field. The description holds the question plus the text for true. The text for false stays out, because it lowers the score |
| `choice`, with a text per option | An `enum` field. The choices are the option names, and the description holds the question plus every option text |
| The state | 1 context string. A JSON state becomes `role: text` lines |

The answer maps back the same way. The fork gives the probability of the chosen value only. For a `choice` the service splits the rest evenly over the other values, so the calibration number of a wrong answer is an estimate.

## Run it

```sh
# 1. the fork server on legion-t5, port 11436
cd ../decision-fork && ./build-legion.sh run

# 2. the judge on LXC 110, port 8085
rsync -a . root@<POC_IP>:/opt/jev-poc-src/poc/decision-judge/
ssh root@<POC_IP> 'cd /opt/jev-poc-src/poc/decision-judge && \
  docker build -q -f Containerfile -t jev-poc/decision-judge . && \
  docker rm -f decision-judge; \
  docker run -d --name decision-judge -p 8085:8085 jev-poc/decision-judge'

# 3. the bench, the same 24 cases
cd .. && python3 judge_bench.py --judge http://<POC_IP>:8085 --label decision-fork-4b
```

Docker needs `-f Containerfile`, because it reads only `Dockerfile` by itself.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `DECISION_URL` | `http://<LEGION_IP>:11436` | The fork server |
| `JUDGE_MODEL` | `qwen3.5-4b-decision-fork` | The name in the result file |
| `DECISION_TIMEOUT_S` | 300 | The timeout of 1 call |
| `NOUL_MODE` | `true_only` | How a yes/no question becomes a field: `true_only`, `both` or `enum`. The test of 2026-09-23 shows `true_only` is the best |

## Open points

1. The router still uses the SemIf judge. This service is a test judge only.
2. Why the fork misses those 2 cases is still open. The wording is not the cause. The next idea is the prompt template, because the fork builds its own prompt.
3. The fork server holds 3,452 MiB of VRAM next to the 3,546 MiB of the SemIf judge model. Both together fill 7 GB of the 8 GB card.
