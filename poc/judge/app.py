"""SemIf judge service.

It speaks the TypeSafe Jev shape (`POST /v1/systemone`) and answers with the
SemIf readout: one forward pass in llama-server, then softmax over the logits
of the answer letters. The scoring code is `remote_semif.py`, the adapter that
the accuracy test of 2026-09-22 measured. With Qwen3.5-4B Q4_K_M, the model
of this service, that test gave 0.812 on authored144 and 78.8 % on the public
JevBench items. Qwen3.5-9B Q4_K_M scores higher (0.913 and 81.8 %) but needs
5,932 MiB instead of 3,568 MiB.

Request body, the same fields as the TypeSafe API:
  {"state": <text or JSON>, "questions": {"<id>": {"type": "choice"|"noul",
   "instructions": "...", "criteria": {...} } } }

Answer:
  {"model": "...", "answers": {"<id>": {"choice"|"noul": ..., "probabilities": {...},
   "confidence": ..., "seconds": ...}}}

Environment:
  SEMIF_LLAMA_URL   llama-server with the judge model
  JUDGE_MODEL       the Hugging Face model of the tokenizer
  JUDGE_REVISION    the pinned commit of that model
"""

from __future__ import annotations

import json
import os
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import remote_semif

MODEL = os.environ.get("JUDGE_MODEL", "Qwen/Qwen3.5-4B")
REVISION = os.environ.get("JUDGE_REVISION", "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a")

app = FastAPI(title="semif-judge")
_tokenizer = None


def tokenizer():
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = remote_semif.load_tokenizer(MODEL, REVISION)
    return _tokenizer


class Ask(BaseModel):
    state: object
    questions: dict
    model: str | None = None


def options_of(question: dict) -> list[dict]:
    """Build the SemIf options, the same mapping as the JevBench adapter."""
    kind = question.get("type")
    criteria = question.get("criteria") or {}
    if kind == "noul":
        return [{"id": "true", "description": criteria.get("true", "The statement is true.")},
                {"id": "false", "description": criteria.get("false", "The statement is false.")}]
    if kind == "choice":
        if len(criteria) < 2:
            raise HTTPException(400, "a choice question needs 2 or more criteria")
        return [{"id": key, "description": value or key} for key, value in criteria.items()]
    raise HTTPException(400, f"question type {kind!r} is not supported; use choice or noul")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL, "llama": remote_semif.URL}


@app.post("/v1/systemone")
def systemone(ask: Ask) -> dict:
    answers = {}
    for qid, question in ask.questions.items():
        options = options_of(question)
        for option in options:
            option["description"] = option["id"] + ": " + option["description"]
        row = {"id": qid, "state": ask.state, "question": question.get("instructions", ""),
               "options": options}
        started = time.perf_counter()
        try:
            out = remote_semif.remote_score(tokenizer(), row, MODEL, REVISION)
        except Exception as error:  # noqa: BLE001
            raise HTTPException(502, f"{type(error).__name__}: {error}") from error
        probabilities = dict(zip(out["option_ids"], out["probabilities"]))
        best = max(probabilities, key=probabilities.get)
        answer = {"probabilities": probabilities, "confidence": probabilities[best],
                  "seconds": time.perf_counter() - started,
                  "input_tokens": out["input_tokens"]}
        answer["noul" if question.get("type") == "noul" else "choice"] = (
            probabilities["true"] > 0.5 if question.get("type") == "noul" else best)
        answers[qid] = answer
    return {"model": MODEL, "answers": answers}


@app.get("/")
def root() -> dict:
    return json.loads(json.dumps({"service": "semif-judge", "post": "/v1/systemone",
                                  "model": MODEL, "llama": remote_semif.URL}))
