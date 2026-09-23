"""SemIf direct scoring against a remote llama-server.

SemIf (TheoLeeCJ/SemIf) runs one forward pass and applies softmax over the
logits of the answer letters A, B, C... This module keeps the SemIf prompt
code unchanged (semif_phase1.direct.encode_prompt) and replaces only the
forward pass: it sends the exact token IDs to llama-server /completion and
reads the raw log-probabilities of the answer-letter tokens.

Softmax over the letter logits equals a renormalization of the full-vocabulary
probabilities over the same letters, because the log normalizer cancels. The
result is therefore the SemIf readout, as long as each letter token is in the
top-N list that llama-server returns. A row with a missing letter gets the
lowest logprob in the list for that letter, and the row is flagged.

Environment:
  SEMIF_LLAMA_URL   base URL of llama-server, for example http://10.0.0.10:11435
  SEMIF_N_PROBS     top-N log-probabilities to request (default 200)
  SEMIF_MAX_TOKENS  prompt token limit (default 16384)

Two entry points:
  python remote_semif.py score --model HF_ID --revision REV --input ROWS --output PREDS
      SemIf row format in, SemIf prediction format out (for benchmarks/evaluate.py).
  python remote_semif.py jevbench -- <jevbench run arguments>
      Runs the JevBench harness with its semif_direct adapter, but remote.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import urllib.request

from semif_phase1.core import digest, softmax  # noqa: F401  (digest kept for parity)
from semif_phase1.direct import PROMPT_VERSION, encode_prompt

URL = os.environ.get("SEMIF_LLAMA_URL", "http://127.0.0.1:11435").rstrip("/")
N_PROBS = int(os.environ.get("SEMIF_N_PROBS", "200"))
MAX_TOKENS = int(os.environ.get("SEMIF_MAX_TOKENS", "16384"))

_TOKENIZERS: dict = {}


def load_tokenizer(source: str, revision: str | None):
    key = (source, revision)
    if key not in _TOKENIZERS:
        import transformers

        _TOKENIZERS[key] = transformers.AutoTokenizer.from_pretrained(
            source, revision=revision, trust_remote_code=False
        )
    return _TOKENIZERS[key]


def _post(path: str, body: dict, timeout: float = 600.0) -> dict:
    req = urllib.request.Request(
        URL + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def server_props() -> dict:
    with urllib.request.urlopen(URL + "/props", timeout=30) as resp:
        props = json.loads(resp.read())
    return {"model_path": props.get("model_path"), "n_ctx": props.get("default_generation_settings", {}).get("n_ctx")}


def _server_tokenize(text: str, add_special: bool) -> list[int]:
    return _post("/tokenize", {"content": text, "add_special": add_special, "parse_special": True})["tokens"]


def encode_prompt_server(tokenizer, row: dict, max_tokens: int) -> tuple[list[int], list[int], str]:
    """SemIf prompt text, tokenized by the GGUF tokenizer in llama-server.

    Use this when the GGUF vocabulary differs from the HF tokenizer (MiniCPM5-2B GGUF).
    The text is the SemIf prompt (same chat template, thinking off). The HF template
    writes the BOS token as text, so it is removed, and llama-server adds its own BOS
    the same way as in normal use (add_special=True). The answer-slot checks are the
    same as in semif_phase1.direct.encode_prompt, but against the GGUF tokenizer.
    """
    from semif_phase1.core import LETTERS, direct_messages

    prompt = tokenizer.apply_chat_template(
        direct_messages(row), tokenize=False, add_generation_prompt=True, enable_thinking=False
    )
    prompt_hash = digest(prompt)
    bos = tokenizer.bos_token or ""
    text = prompt[len(bos):] if bos and prompt.startswith(bos) else prompt
    ids = _server_tokenize(text, add_special=True)
    if not ids or len(ids) > max_tokens:
        raise ValueError(f"Row {row['id']}: {len(ids)} input tokens exceed limit {max_tokens}; no truncation allowed")
    slots = []
    for letter in LETTERS[: len(row["options"])]:
        encoded = _server_tokenize(letter, add_special=False)
        if len(encoded) != 1:
            raise ValueError(f"Answer slot {letter!r} is not one GGUF token")
        slots.append(encoded[0])
    if len(slots) != len(set(slots)):
        raise ValueError("Answer-slot tokens collide")
    for letter, token in zip(LETTERS, slots):
        if _server_tokenize(text + letter, add_special=True) != ids + [token]:
            raise ValueError(f"Answer boundary changes tokenization for slot {letter}")
    return ids, slots, prompt_hash


# "hf": exact SemIf token IDs from the HF tokenizer. "server": GGUF tokenizer.
# "auto" picks "hf" when check_tokenizer() finds equal IDs, else "server".
TOKENIZE_MODE = os.environ.get("SEMIF_TOKENIZE", "auto")
_RESOLVED_MODE: dict = {}


def tokenize_mode(tokenizer) -> str:
    if TOKENIZE_MODE != "auto":
        return TOKENIZE_MODE
    key = id(tokenizer)
    if key not in _RESOLVED_MODE:
        _RESOLVED_MODE[key] = "hf" if check_tokenizer(tokenizer)["equal"] else "server"
    return _RESOLVED_MODE[key]


def remote_score(tokenizer, row: dict, source: str, revision: str | None) -> dict:
    started = time.perf_counter()
    mode = tokenize_mode(tokenizer)
    encode = encode_prompt if mode == "hf" else encode_prompt_server
    ids, slots, prompt_hash = encode(tokenizer, row, MAX_TOKENS)
    body = {
        "prompt": ids,
        "n_predict": 1,
        "n_probs": N_PROBS,
        "temperature": 0,
        "cache_prompt": False,
        "post_sampling_probs": False,
    }
    forward_start = time.perf_counter()
    out = _post("/completion", body)
    forward_seconds = time.perf_counter() - forward_start
    top = out["completion_probabilities"][0]["top_logprobs"]
    by_id = {entry["id"]: entry["logprob"] for entry in top}
    floor = min(by_id.values())
    missing = [LETTER for LETTER, tok in zip("ABCDEFGHIJKLMNOP", slots) if tok not in by_id]
    selected = [by_id.get(tok, floor) for tok in slots]
    argmax_id = max(by_id, key=by_id.get)
    return {
        "id": row["id"],
        "option_ids": [option["id"] for option in row["options"]],
        "probabilities": softmax(selected),
        "option_logits": selected,
        "answer_token_ids": slots,
        "allowed_token_mass": sum(math.exp(v) for v in selected),
        "full_vocab_argmax_id": argmax_id,
        "missing_letters": missing,
        "input_tokens": len(ids),
        "forward_seconds": forward_seconds,
        "total_seconds": time.perf_counter() - started,
        "prompt_sha256": prompt_hash,
        "prompt_version": PROMPT_VERSION,
        "tokenize_mode": mode,
        "model": {"source": source, "revision": revision, "runtime": "llama-server", **server_props()},
        "readout": "llama-server raw top-N logprobs restricted to declared answer slots",
        "probability_status": "conditional option score; uncalibrated as decision confidence",
    }


def check_tokenizer(tokenizer) -> dict:
    """Make sure the GGUF vocabulary gives the same IDs as the HF tokenizer."""
    text = tokenizer.apply_chat_template(
        [{"role": "system", "content": "Answer with one letter."},
         {"role": "user", "content": '{"evidence": "Die Katze schläft. 2026-09-22, €15,000", "options": ["A", "B"]}'}],
        tokenize=False, add_generation_prompt=True, enable_thinking=False,
    )
    hf = tokenizer.encode(text, add_special_tokens=False)
    gguf = _post("/tokenize", {"content": text, "add_special": False, "parse_special": True})["tokens"]
    return {"equal": hf == gguf, "hf_len": len(hf), "gguf_len": len(gguf)}


def cmd_score(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="remote_semif.py score")
    p.add_argument("--model", required=True)
    p.add_argument("--revision", required=True)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args(argv)
    tok = load_tokenizer(a.model, a.revision)
    print(json.dumps({"tokenizer_check": check_tokenizer(tok), "tokenize_mode": tokenize_mode(tok)}), flush=True)
    rows = [json.loads(line) for line in open(a.input) if line.strip()]
    with open(a.output, "x") as dst:
        for n, row in enumerate(rows, 1):
            dst.write(json.dumps(remote_score(tok, row, a.model, a.revision)) + "\n")
            if n % 25 == 0:
                print(f"[score] {n}/{len(rows)}", flush=True)
    return 0


def cmd_jevbench(argv: list[str]) -> int:
    import jevbench.cli as cli
    from jevbench.adapters.semif_direct import SemIfDirectAdapter

    class RemoteSemIfAdapter(SemIfDirectAdapter):
        name = "semif_direct_remote"
        cost_basis = "self_hosted_gpu"

        def load(self):
            if self._loaded is None:
                tok = load_tokenizer(self.endpoint, self.revision)
                self._loaded = (None, tok, {"source": self.endpoint, "revision": self.revision})
                self.load_s = 0.0
            return self._loaded

        def run(self, task):
            from jevbench.adapters.base import DecisionResult

            res = DecisionResult(adapter=self.name, ok=False, probs_source="native", model=self.model)
            row = self.build_request(task)
            res.request_body = {k: v for k, v in row.items() if k != "state"}
            _, tok, _ = self.load()
            t0 = time.perf_counter()
            try:
                out = remote_score(tok, row, self.endpoint, self.revision)
            except Exception as e:  # noqa: BLE001
                res.latency_s = time.perf_counter() - t0
                res.error = f"{type(e).__name__}: {str(e)[:300]}"
                return res
            res.latency_s = time.perf_counter() - t0
            probs = dict(zip(out["option_ids"], out["probabilities"]))
            res.usage = {"input_tokens": out["input_tokens"], "output_tokens": 0}
            res.raw = {"answer": {k: out[k] for k in ("option_ids", "probabilities", "option_logits",
                                                       "missing_letters", "allowed_token_mass", "tokenize_mode",
                                                       "input_tokens", "forward_seconds",
                                                       "prompt_sha256", "prompt_version")},
                       "runtime": {"model": out["model"], "readout": out["readout"]}}
            res.probs = {"yes": probs["true"], "no": probs["false"]} if task.question["type"] == "noul" else probs
            res.ok = True
            return res

    cli.SemIfDirectAdapter = RemoteSemIfAdapter
    return cli.main(argv)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("score", "jevbench"):
        print(__doc__)
        sys.exit(2)
    args = sys.argv[2:]
    if args and args[0] == "--":
        args = args[1:]
    sys.exit(cmd_score(args) if sys.argv[1] == "score" else cmd_jevbench(args))
