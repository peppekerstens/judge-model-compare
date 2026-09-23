"""Judge service on the llama.cpp fork endpoint `/v1/decision`.

It speaks the same TypeSafe `/v1/systemone` shape as the SemIf judge and the Laya
judge, so `judge_bench.py` and the router use it without a change. Inside, it sends
1 call to the fork: 1 schema with all fields, and 1 context. The fork scores every
allowed value of every field in one forward pass, and it returns a probability that
is normalized over the allowed values only.

Difference with the SemIf judge:
  SemIf judge: 2 calls, letters A and B, probabilities from the top 200 tokens.
  This judge:  1 call, the real words, probabilities over the allowed values.

Environment:
  DECISION_URL   the fork server, for example http://10.0.0.10:11436
  JUDGE_MODEL    the name for the report, for example qwen3.5-4b-decision-fork
"""

from __future__ import annotations

import json
import os
import time

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# The container gets DECISION_URL from the compose file or from docker run.
URL = os.environ.get("DECISION_URL", "http://127.0.0.1:11436").rstrip("/")
# How a noul question becomes a field. The schema holds 1 description per field, so the
# text for the false side needs a place. The wording test of 2026-09-23 compares:
#   true_only  the question plus the text for true (the first version)
#   both       the question plus the text for true and the text for false
#   enum       an enum with the values yes and no, and both texts in the description
NOUL_MODE = os.environ.get("NOUL_MODE", "true_only")  # the best of the 3, measured
MODEL = os.environ.get("JUDGE_MODEL", "qwen3.5-4b-decision-fork")
TIMEOUT_S = float(os.environ.get("DECISION_TIMEOUT_S", "300"))

app = FastAPI(title="decision-judge")


class Ask(BaseModel):
    state: object
    questions: dict
    model: str | None = None


def state_text(state) -> str:
    """The fork takes a string for each context. A JSON state becomes compact JSON."""
    if isinstance(state, str):
        return state
    if isinstance(state, dict) and "messages" in state:
        parts = []
        for message in state.get("messages", []):
            role = message.get("role", "user")
            text = message.get("text") or message.get("content") or ""
            parts.append(f"{role}: {text}")
        return "\n".join(parts)
    return json.dumps(state, ensure_ascii=False)


def build_schema(questions: dict) -> tuple[dict, list[str]]:
    """Our questions become 1 schema. Every field needs a description."""
    schema, order = {}, []
    for qid, question in questions.items():
        kind = question.get("type")
        instructions = (question.get("instructions") or "").strip()
        criteria = question.get("criteria") or {}
        if kind == "noul":
            yes_text, no_text = criteria.get("true", ""), criteria.get("false", "")
            if NOUL_MODE == "enum":
                description = instructions
                if yes_text:
                    description += f" yes: {yes_text}"
                if no_text:
                    description += f" no: {no_text}"
                schema[qid] = {"type": "enum", "choices": ["yes", "no"],
                               "description": description.strip()}
            else:
                description = instructions
                if yes_text:
                    description += f" True means: {yes_text}"
                if no_text and NOUL_MODE == "both":
                    description += f" False means: {no_text}"
                schema[qid] = {"type": "boolean", "description": description.strip()}
        elif kind == "choice":
            if len(criteria) < 2:
                raise HTTPException(400, "a choice question needs 2 or more criteria")
            # The fork takes plain choices, so each option description moves into the
            # field description. That keeps the wording of the bench and the router.
            options = "; ".join(f"{key}: {value}" for key, value in criteria.items())
            schema[qid] = {"type": "enum", "choices": list(criteria),
                           "description": f"{instructions} Meaning of each value: {options}"}
        else:
            raise HTTPException(400, f"question type {kind!r} is not supported")
        order.append(qid)
    return schema, order


@app.get("/health")
async def health() -> dict:
    out = {"status": "ok", "model": f"{MODEL}-{NOUL_MODE}", "decision_url": URL, "noul_mode": NOUL_MODE}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{URL}/health")
        out["server"] = response.status_code
    except Exception as error:  # noqa: BLE001
        out["server"] = f"error: {type(error).__name__}"
    return out


@app.post("/v1/systemone")
async def systemone(ask: Ask) -> dict:
    schema, order = build_schema(ask.questions)
    body = {"instructions": "Answer every field about the request below.",
            "schema": schema, "contexts": [state_text(ask.state)], "cache_prompt": True}
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            response = await client.post(f"{URL}/v1/decision", json=body)
    except Exception as error:  # noqa: BLE001
        raise HTTPException(502, f"{type(error).__name__}: {error}") from error
    if response.status_code != 200:
        raise HTTPException(502, f"decision endpoint {response.status_code}: {response.text[:300]}")
    seconds = time.perf_counter() - started
    result = response.json()["results"][0]

    answers = {}
    for qid in order:
        field = result["fields"][qid]
        value, probability = field["value"], float(field["probability"])
        out = {"seconds": seconds, "confidence": probability}
        if schema[qid]["type"] == "boolean" or set(schema[qid].get("choices", [])) == {"yes", "no"}:
            is_yes = value in (True, "true", "yes")
            yes = probability if is_yes else 1.0 - probability
            out["noul"] = bool(is_yes)
            out["probabilities"] = {"true": yes, "false": 1.0 - yes}
        else:
            out["choice"] = value
            # The fork reports the probability of the chosen value only. The rest of
            # the mass goes to the other values, and we do not know how it splits.
            rest = (1.0 - probability) / max(len(schema[qid]["choices"]) - 1, 1)
            out["probabilities"] = {c: (probability if c == value else rest)
                                    for c in schema[qid]["choices"]}
        answers[qid] = out
    return {"model": f"{MODEL}-{NOUL_MODE}", "answers": answers, "usage": result.get("usage", {}),
            "timings": response.json().get("timings", {})}


@app.get("/")
def root() -> dict:
    return {"service": "decision-judge", "post": "/v1/systemone", "model": MODEL,
            "decision_url": URL}
