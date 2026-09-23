"""Laya judge service, in the same shape as the SemIf judge.

Laya (NandhaKishorM/laya) is an encoder model, not a language model. It answers
typed questions in one forward pass on the CPU. This service wraps it in the
TypeSafe `/v1/systemone` shape, so `judge_bench.py` and the router can use it
without a change.

Environment:
  LAYA_MODEL     the Hugging Face checkpoint, for example convaiinnovations/laya-multilingual
  LAYA_DEVICE    cpu (the default) or cuda
"""

from __future__ import annotations

import os
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

MODEL = os.environ.get("LAYA_MODEL", "convaiinnovations/laya-multilingual")
DEVICE = os.environ.get("LAYA_DEVICE", "cpu")

app = FastAPI(title="laya-judge")
_agent = None


def agent():
    global _agent
    if _agent is None:
        from laya import Agent

        _agent = Agent(MODEL, device=DEVICE)
    return _agent


class Ask(BaseModel):
    state: object
    questions: dict
    model: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL, "device": DEVICE}


@app.post("/v1/systemone")
def systemone(ask: Ask) -> dict:
    started = time.perf_counter()
    try:
        result = agent().predict(ask.state, ask.questions)
    except Exception as error:  # noqa: BLE001
        raise HTTPException(502, f"{type(error).__name__}: {error}") from error
    seconds = time.perf_counter() - started

    answers = {}
    for qid, question in ask.questions.items():
        raw = result["answers"][qid]
        out = {"seconds": seconds}
        if question.get("type") == "noul":
            # Laya returns the probability of true as a plain number.
            probability = float(raw["noul"] if isinstance(raw, dict) else raw)
            out["noul"] = probability > 0.5
            out["probabilities"] = {"true": probability, "false": 1.0 - probability}
            out["confidence"] = max(probability, 1.0 - probability)
        else:
            out["choice"] = raw["choice"]
            probabilities = raw.get("probabilities") or {}
            out["probabilities"] = probabilities
            out["confidence"] = raw.get("confidence") or (
                max(probabilities.values()) if probabilities else 0.0)
        answers[qid] = out
    return {"model": MODEL, "answers": answers,
            "routing": result.get("routing", {})}


@app.get("/")
def root() -> dict:
    return {"service": "laya-judge", "post": "/v1/systemone", "model": MODEL}
