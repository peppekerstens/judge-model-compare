## Test 1: SemIf authored144 (mean family balanced accuracy)

| Run | GGUF | Tokenizer | authored144 | Reference (BF16) | Diff |
|---|---|---|---|---|---|
| ternary-bonsai-2-27b-ptq1_0 | `ternary-bonsai-2-27b-ptq1_0.gguf` | Qwen/Qwen3.8-27B | 0.915 | 0.958 | -0.043 |
| qwen3.5-9b-q4km | `qwen3.5-9b-standard.gguf` | Qwen/Qwen3.5-9B | 0.913 | - | - |
| qwen3.5-4b-q4km | `qwen3.5-4b.gguf` | Qwen/Qwen3.5-4B | 0.812 | 0.813 | -0.002 |
| qwen3.5-4b-gsq-q2kxl | `qwen3.5-4b-gsq-q2kxl.gguf` | Qwen/Qwen3.5-4B | 0.773 | 0.813 | -0.040 |
| qwen3.5-2b-q4km | `qwen3.5-2b.gguf` | Qwen/Qwen3.5-2B | 0.627 | - | - |
| minicpm5-2b-q4km | `minicpm5-2b.gguf` | openbmb/MiniCPM5-2B | 0.622 | 0.686 | -0.064 |
| qwen3-0.6b-q8 | `qwen3-0.6b-q8_0.gguf` | Qwen/Qwen3-0.6B | 0.438 | 0.440 | -0.003 |

## Test 2: JevBench public items (accuracy per tier)

| Run | Easy | Standard | Hard | All 231 | Hard ECE | Same outcome as SemIf ref | Failed | p50 latency |
|---|---|---|---|---|---|---|---|---|
| ternary-bonsai-2-27b-ptq1_0 | 100.0 % (48/48) | 90.3 % (65/72) | 66.7 % (74/111) | 81.0 % (187/231) | 0.143 | 199/231 | 0 | 1.22 s |
| qwen3.5-9b-q4km | 100.0 % (48/48) | 94.4 % (68/72) | 65.8 % (73/111) | 81.8 % (189/231) | 0.134 | 201/231 | 0 | 0.40 s |
| qwen3.5-4b-q4km | 97.9 % (47/48) | 95.8 % (69/72) | 59.5 % (66/111) | 78.8 % (182/231) | 0.126 | 224/231 | 0 | 0.24 s |
| qwen3.5-4b-gsq-q2kxl | 100.0 % (48/48) | 91.7 % (66/72) | 53.2 % (59/111) | 74.9 % (173/231) | 0.137 | 205/231 | 0 | 0.20 s |
| qwen3.5-2b-q4km | 100.0 % (48/48) | 75.0 % (54/72) | 43.2 % (48/111) | 64.9 % (150/231) | 0.311 | 174/231 | 0 | 0.20 s |
| minicpm5-2b-q4km | 95.8 % (46/48) | 69.4 % (50/72) | 45.9 % (51/111) | 63.6 % (147/231) | 0.358 | 165/231 | 0 | 0.19 s |
| qwen3-0.6b-q8 | 87.5 % (42/48) | 44.4 % (32/72) | 30.6 % (34/111) | 46.8 % (108/231) | 0.597 | 124/231 | 0 | 0.19 s |
| Published: SemIf Qwen3.5-4B BF16 | 100.0 % (48/48) | 98.6 % (71/72) | 61.3 % (68/111) | 81.0 % (187/231) | - | - | - | - |
| Published: Jev 1.13.0 | 100.0 % (48/48) | 98.6 % (71/72) | 73.0 % (81/111) | 86.6 % (200/231) | - | - | - | - |
