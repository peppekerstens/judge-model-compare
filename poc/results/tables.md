## Judge bench: 24 cases, both questions

| Judge model | VRAM | Sensitive | Difficulty | Both | Median time | Mean time | Slowest |
|---|---|---|---|---|---|---|---|
| Qwen/Qwen3.5-2B | 1,712 MiB | 24/24 | 12/24 | 12/24 | 0.41 s | 0.48 s | 1.78 s |
| Qwen/Qwen3.5-4B | 3,568 MiB | 24/24 | 23/24 | 23/24 | 0.56 s | 0.67 s | 2.18 s |
| Qwen/Qwen3.5-9B | 5,932 MiB | 24/24 | 22/24 | 22/24 | 0.80 s | 0.88 s | 2.20 s |
| qwen3.5-4b-decision-fork | 3,452 MiB | 22/24 | 23/24 | 21/24 | 0.28 s | 0.27 s | 0.41 s |
| qwen3.5-4b-decision-fork-true_only | 3,452 MiB | 22/24 | 23/24 | 21/24 | 0.25 s | 0.29 s | 0.51 s |
| qwen3.5-4b-decision-fork-both | 3,452 MiB | 20/24 | 23/24 | 19/24 | 0.23 s | 0.27 s | 0.47 s |
| qwen3.5-4b-decision-fork-enum | 3,452 MiB | 21/24 | 20/24 | 17/24 | 0.29 s | 0.28 s | 0.41 s |
| convaiinnovations/laya-multilingual | none, CPU | 14/24 | 6/24 | 4/24 | 0.48 s | 1.35 s | 19.15 s |
| laya-multilingual-gpu | 1,715 MiB | 14/24 | 6/24 | 4/24 | 0.20 s | 0.59 s | 10.02 s |
| needle3-record_decision | none, CPU | 1/24 | 0/24 | 0/24 | 0.20 s | 0.20 s | 0.52 s |
| needle3-tools | none, CPU | 1/24 | 6/24 | 1/24 | 0.21 s | 0.23 s | 0.41 s |

### The cases that a judge reads differently

| Case | Wanted | 2B | 4B | 9B | fork | fork true_only | fork both | fork enum | Laya CPU | Laya GPU | Needle record | Needle tools |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| r1-01 | simple, sensitive False | ok | ok | ok | ok | ok | ok | ok | ok | ok | abstained, sensitive abstained | abstained, sensitive abstained |
| r1-02 | simple, sensitive False | hard | ok | ok | ok | ok | ok | ok | hard | hard | abstained, sensitive abstained | abstained, sensitive abstained |
| r1-03 | simple, sensitive False | ok | ok | ok | ok | ok | ok | ok | ok, sensitive True | ok, sensitive True | abstained, sensitive abstained | abstained, sensitive abstained |
| r1-04 | medium, sensitive False | hard | ok | ok | ok | ok | ok | ok | simple | simple | abstained, sensitive abstained | ok, sensitive abstained |
| r1-05 | medium, sensitive False | ok | ok | ok | ok | ok | ok | ok | simple, sensitive True | simple, sensitive True | abstained, sensitive abstained | simple, sensitive abstained |
| r1-06 | medium, sensitive False | hard | ok | ok | ok | ok | ok | ok | simple, sensitive True | simple, sensitive True | abstained, sensitive abstained | abstained, sensitive abstained |
| r1-07 | hard, sensitive False | ok | ok | ok | ok | ok | ok | ok | simple | simple | abstained, sensitive abstained | medium, sensitive abstained |
| r1-08 | hard, sensitive False | ok | ok | ok | ok | ok | ok | ok | simple | simple | abstained, sensitive abstained | medium, sensitive abstained |
| r1-09 | hard, sensitive False | ok | ok | ok | ok | ok | ok | ok | simple | simple | abstained, sensitive abstained | simple, sensitive abstained |
| r1-10 | simple, sensitive True | ok | ok | ok | ok | ok | ok, sensitive False | ok, sensitive False | ok, sensitive False | ok, sensitive False | abstained, sensitive abstained | medium, sensitive abstained |
| r1-11 | medium, sensitive True | hard | ok | ok | ok | ok | ok | ok | simple, sensitive False | simple, sensitive False | abstained | ok |
| r1-12 | hard, sensitive True | ok | ok | ok | ok | ok | ok | ok | simple, sensitive False | simple, sensitive False | abstained, sensitive abstained | simple, sensitive abstained |
| r2-01 | medium, sensitive True | hard | ok | ok | ok | ok | ok, sensitive False | ok | simple, sensitive False | simple, sensitive False | abstained, sensitive abstained | ok, sensitive abstained |
| r2-02 | simple, sensitive True | hard | ok | ok | ok, sensitive False | ok, sensitive False | ok, sensitive False | ok, sensitive False | hard | hard | abstained, sensitive abstained | abstained, sensitive abstained |
| r2-03 | medium, sensitive False | hard | ok | ok | ok | ok | ok | ok | simple, sensitive True | simple, sensitive True | abstained, sensitive abstained | ok, sensitive abstained |
| r2-04 | hard, sensitive False | ok | ok | ok | ok | ok | ok | medium | simple, sensitive True | simple, sensitive True | abstained, sensitive abstained | abstained, sensitive abstained |
| r2-05 | hard, sensitive True | ok | ok | ok | ok | ok | ok | medium | simple | simple | abstained, sensitive abstained | simple, sensitive abstained |
| r2-06 | simple, sensitive False | hard | ok | ok | ok | ok | ok | ok | ok | ok | abstained, sensitive abstained | abstained, sensitive abstained |
| r2-07 | hard, sensitive False | ok | ok | ok | ok | ok | ok | ok | simple | simple | abstained, sensitive abstained | medium, sensitive abstained |
| r2-08 | medium, sensitive True | hard | ok | hard | ok | ok | ok | simple | simple | simple | abstained, sensitive abstained | ok, sensitive abstained |
| r2-09 | medium, sensitive False | simple | simple | simple | simple | simple | simple | simple | simple, sensitive True | simple, sensitive True | abstained, sensitive abstained | simple, sensitive abstained |
| r2-10 | hard, sensitive False | ok | ok | ok | ok | ok | ok | ok | simple | simple | abstained, sensitive abstained | medium, sensitive abstained |
| r2-11 | simple, sensitive True | hard | ok | ok | ok, sensitive False | ok, sensitive False | ok, sensitive False | ok, sensitive False | ok | ok | abstained, sensitive abstained | ok, sensitive abstained |
| r2-12 | simple, sensitive False | hard | ok | ok | ok | ok | ok | ok | ok | ok | abstained, sensitive abstained | abstained, sensitive abstained |

## End-to-end router test: 7 examples

| Judge model | Routes correct | Mean judge time | Slowest judge time |
|---|---|---|---|
| Qwen/Qwen3.5-4B | 7/7 | 0.62 s | 0.90 s |
| Qwen/Qwen3.5-9B | 7/7 | 0.88 s | 1.14 s |
