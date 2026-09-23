"""UNTESTED DRAFT. Needle 3 judge service, in the same shape as the SemIf judge.

Nothing in this file ran. It was written from the documentation and from the
JevBench adapter `jevbench/adapters/needle_local.py`. Read `README.md` first.

Needle 3 (Cactus Compute) is a tool-calling model, not a decision model. It has
no typed-question interface, so every question becomes a tool call:

  noul   -> one tool `record_decision` with one boolean argument
  choice -> one tool `record_decision` with one string argument, typed as an enum
  choice -> or, with NEEDLE_CHOICE_MODE=tools, one tool per option, and the
            called tool is the answer

That mapping is the one JevBench uses, so our numbers stay comparable.

Needle returns one label and one calibrated confidence scalar for the whole
call. It returns no probability per option. This service converts the scalar to
a distribution so that `judge_bench.py` keeps working, and it marks every answer
with `probability_source` so that nobody reads the number as a real
distribution.

Needle keeps the conversation state and the C API holds one process-global
model, so this service serialises every request with a lock and builds a fresh
agent per question.

Environment:
  NEEDLE_CHOICE_MODE   record_decision (the default) or tools
  NEEDLE_MAX_TOKENS    max_new_tokens per call, 128 by default
  NEEDLE_TELEMETRY     0, set in the Containerfile
  HF_HUB_OFFLINE       1, set in the Containerfile
"""

from __future__ import annotations

import json
import os
import threading
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

MODEL = "Cactus-Compute/needle3"
CHOICE_MODE = os.environ.get("NEEDLE_CHOICE_MODE", "record_decision")
MAX_TOKENS = int(os.environ.get("NEEDLE_MAX_TOKENS", "128"))
NO_DISTRIBUTION = "label_only_no_calibrated_distribution"

app = FastAPI(title="needle-judge")
_lock = threading.Lock()
_version = None


def needle_module():
    """Import late, and remember the package version."""
    global _version
    import needle

    if _version is None:
        _version = getattr(needle, "__version__", "unknown")
    return needle


class Ask(BaseModel):
    state: object
    questions: dict
    model: str | None = None


def option_ids(question: dict) -> list[str]:
    if question.get("type") == "noul":
        return ["true", "false"]
    criteria = question.get("criteria") or {}
    if len(criteria) < 2:
        raise HTTPException(400, "a choice question needs 2 or more criteria")
    return [str(key) for key in criteria]


def record_tool(question: dict) -> dict:
    """One tool, one typed argument. The JevBench `record_decision` mapping."""
    instructions = question.get("instructions", "")
    criteria = question.get("criteria") or {}
    if question.get("type") == "noul":
        legend = f" true: {criteria.get('true', '')}; false: {criteria.get('false', '')}"
        parameter = {"type": "boolean", "description": instructions + legend}
    else:
        labels = option_ids(question)
        legend = "; ".join(f"{label}: {criteria.get(label) or label}" for label in labels)
        parameter = {"type": "string", "enum": labels,
                     "description": instructions + " Options: " + legend}
    return {"name": "record_decision",
            "description": "Record the answer to this question about the text: " + instructions,
            "parameters": {"type": "object", "properties": {"decision": parameter},
                           "required": ["decision"]}}


def option_tools(question: dict) -> list[dict]:
    """One tool per option. The JevBench `options_as_tools` mapping."""
    criteria = question.get("criteria") or {}
    return [{"name": label,
             "description": criteria.get(label) or label,
             "parameters": {"type": "object", "properties": {}, "required": []}}
            for label in option_ids(question)]


def to_label(value, question: dict) -> str | None:
    labels = option_ids(question)
    if question.get("type") == "noul":
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str) and value.lower() in ("true", "false", "yes", "no"):
            return "true" if value.lower() in ("true", "yes") else "false"
        return None
    return value if value in labels else None


def spread(label: str | None, confidence: float | None, labels: list[str]) -> dict:
    """Turn 1 scalar into a distribution. This is a conversion, not a measurement.

    The chosen label takes the confidence, and the rest share what is left. When
    Needle abstains, or when the confidence is missing, every option gets the
    same share.
    """
    if label is None or confidence is None or len(labels) < 2:
        equal = 1.0 / max(len(labels), 1)
        return {name: equal for name in labels}
    confidence = min(max(float(confidence), 0.0), 1.0)
    rest = (1.0 - confidence) / (len(labels) - 1)
    return {name: (confidence if name == label else rest) for name in labels}


def ask_needle(text: str, question: dict) -> dict:
    """One question, one Needle agent. The caller holds the lock."""
    module = needle_module()
    as_tools = CHOICE_MODE == "tools" and question.get("type") == "choice"
    tools = option_tools(question) if as_tools else [record_tool(question)]
    instructions = question.get("instructions", "")

    agent = None
    started = time.perf_counter()
    try:
        agent = module.Needle(tools=tools, system=instructions)
        out = agent.complete(text, max_new_tokens=MAX_TOKENS)
    except Exception as error:  # noqa: BLE001
        raise HTTPException(502, f"{type(error).__name__}: {error}") from error
    finally:
        if agent is not None:
            agent.close()
    seconds = time.perf_counter() - started

    calls = out.get("function_calls") or []
    suppressed = out.get("suppressed_calls") or []

    def value_of(call: dict):
        return call.get("name") if as_tools else (call.get("arguments") or {}).get("decision")

    label = to_label(value_of(calls[0]), question) if calls else None
    labels = option_ids(question)
    confidence = out.get("confidence")
    answer = {"seconds": seconds,
              "probabilities": spread(label, confidence, labels),
              "confidence": float(confidence) if confidence is not None else 0.0,
              "probability_source": NO_DISTRIBUTION,
              "mode": "options_as_tools" if as_tools else "record_decision",
              "abstained": not calls,
              "suppressed": bool(not calls and suppressed),
              "usage": {key: out.get(key) for key in ("prefill_tps", "decode_tps", "peak_ram_mb")
                        if key in out}}

    if question.get("type") == "noul":
        # An abstention is a wrong answer, not a missing answer. False is the
        # safe side for "sensitive data", so an abstention must not hide data.
        answer["noul"] = label == "true"
    else:
        # `judge_bench.py` reads a string. An abstention gives the first option,
        # and the flag `abstained` marks it.
        answer["choice"] = label if label is not None else labels[0]
    return answer


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL, "device": "cpu",
            "choice_mode": CHOICE_MODE, "package": _version or "not loaded"}


@app.post("/v1/systemone")
def systemone(ask: Ask) -> dict:
    text = ask.state if isinstance(ask.state, str) else json.dumps(ask.state, ensure_ascii=False)
    answers = {}
    with _lock:  # the engine holds 1 process-global model and 1 conversation
        for qid, question in ask.questions.items():
            answers[qid] = ask_needle(text, question)
    return {"model": MODEL, "answers": answers}


@app.get("/")
def root() -> dict:
    return {"service": "needle-judge", "post": "/v1/systemone", "model": MODEL,
            "choice_mode": CHOICE_MODE, "warning": "untested draft"}
