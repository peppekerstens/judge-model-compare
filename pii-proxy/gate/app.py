"""The PII gate as a service.

It speaks the OpenAI chat shape on both sides, so any client can use it.

    POST /v1/chat/completions   the same body as the upstream gateway
    POST /v1/mask               mask only, for a test
    GET  /healthz               the state of both back ends
    GET  /log                   an HTML page with the last 200 decisions

The chain for each request:

  1. Presidio finds the spans in the last user message.
  2. This service replaces every span with a numbered placeholder, and it keeps
     the map in memory for the length of the request only.
  3. The llama.cpp fork reads the masked text and answers 2 fields in 1 call:
     does sensitive data remain, and how hard is the request.
  4. The router rule picks the target. Sensitivity wins over difficulty.
  5. The service calls the target with the MASKED text.
  6. It puts the original values back into the answer.

The map never reaches a disk, and it never reaches the upstream model.
Set LOG_MASKED=0 to keep the masked text out of the log page as well.

Environment:
  PRESIDIO_ANALYZER_URL   for example http://10.0.0.40:5002
  DECISION_FORK_URL       for example http://10.0.0.10:11436
  UPSTREAM_URL            the gateway that serves the target models
  UPSTREAM_KEY            the key for that gateway
  LOG_DB                  the SQLite file for the decision log
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gate  # noqa: E402

ANALYZER = os.environ.get("PRESIDIO_ANALYZER_URL", "")
FORK = os.environ.get("DECISION_FORK_URL", "")
UPSTREAM = os.environ.get("UPSTREAM_URL", "")
UPSTREAM_KEY = os.environ.get("UPSTREAM_KEY", "")
LOG_DB = os.environ.get("LOG_DB", "/data/pii-gate.sqlite")
LOG_MASKED = os.environ.get("LOG_MASKED", "1") == "1"
TIMEOUT_S = float(os.environ.get("TIMEOUT_S", "600"))
HINT = os.environ.get("PLACEHOLDER_HINT", "1") == "1"
HINT_TEXT = (
    "Some words in the request are replaced by a placeholder, for example "
    "<PERSON_1>, <STREET_ADDRESS_1> or <IBAN_CODE_1>. A placeholder stands for a "
    "real value that you do not need. Treat it as the real value, and write it "
    "back in your answer exactly as you see it, with the angle brackets. Do not "
    "refuse, and do not say that information is missing because of a placeholder. "
    "Use only a placeholder that the request holds. Never invent a new one with a "
    "higher number.")

app = FastAPI(title="pii-gate")


def db() -> sqlite3.Connection:
    Path(LOG_DB).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(LOG_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS decision (
        id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, entities INTEGER,
        types TEXT, remains INTEGER, difficulty TEXT, route TEXT, reason TEXT,
        mask_ms INTEGER, audit_ms INTEGER, total_ms INTEGER, masked TEXT)""")
    return conn


def last_user_text(messages: list) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def replace_user_text(messages: list, new_text: str) -> list:
    out = [dict(m) for m in messages]
    for message in reversed(out):
        if message.get("role") == "user":
            message["content"] = new_text
            break
    return out


@app.get("/healthz")
async def healthz() -> dict:
    """A `/health` of 200 on the fork port is not enough.

    `llama-rerank` uses the same port 11436 on the same host, and it is also a
    llama-server, so it answers `/health` with 200. Only `/v1/decision` tells
    the 2 apart. The check therefore sends 1 small decision.
    """
    state = {"service": "pii-gate", "analyzer": ANALYZER, "fork": FORK,
             "upstream": UPSTREAM}
    async with httpx.AsyncClient(timeout=30) as client:
        for name, url in (("analyzer", f"{ANALYZER}/health"), ("fork", f"{FORK}/health")):
            try:
                state[f"{name}_status"] = (await client.get(url)).status_code
            except Exception as error:  # noqa: BLE001
                state[f"{name}_status"] = f"error: {type(error).__name__}"
        try:
            probe = await client.post(f"{FORK}/v1/decision", json={
                "instructions": "Answer the field.",
                "schema": {"ok": {"type": "boolean", "description": "Is this text empty?"}},
                "contexts": ["ping"]})
            state["decision_endpoint"] = probe.status_code == 200
            if probe.status_code != 200:
                state["decision_note"] = (
                    "the port answers, but not with /v1/decision. llama-rerank "
                    "probably holds it. Use pii-proxy/gpu-window.sh open")
        except Exception as error:  # noqa: BLE001
            state["decision_endpoint"] = f"error: {type(error).__name__}"
    return state


@app.post("/v1/mask")
async def mask_only(request: Request) -> JSONResponse:
    body = await request.json()
    text = body.get("text") or last_user_text(body.get("messages", []))
    if not text:
        raise HTTPException(400, "give a text field, or messages with a user role")
    result = gate.mask(text, ANALYZER)
    return JSONResponse({"masked": result.text, "mapping": result.mapping,
                         "entities": [{"type": e["entity_type"], "score": e["score"]}
                                      for e in result.entities],
                         "seconds": round(result.seconds, 4)})


@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    messages = body.get("messages") or []
    text = last_user_text(messages)
    started = time.perf_counter()

    # The fork reads the RAW text first. The traffic test of 2026-09-24 showed
    # why: Presidio marks "France" in "What is the capital of France?" as a
    # location, the model then reads `<LOCATION_1>` and refuses to answer. A
    # clean request must never get a mask. The fork scores 22 of 24 on raw text,
    # so it is the right gate for that question.
    pre = gate.audit(text, FORK, timeout=TIMEOUT_S)
    if pre["sensitive"]:
        masked = gate.mask(text, ANALYZER)
        audit = gate.audit(masked.text, FORK, timeout=TIMEOUT_S)
        audit["seconds"] += pre["seconds"]
        audit["difficulty"] = pre["difficulty"]     # judged on the full text
    else:
        masked = gate.MaskResult(text=text)         # no mask, no map
        audit = pre
    target, reason = gate.route(audit["sensitive"], audit["difficulty"])
    if not pre["sensitive"]:
        reason = "no sensitive data in the request, so no mask"

    upstream_body = dict(body)
    upstream_body["messages"] = replace_user_text(messages, masked.text)
    if masked.mapping and HINT:
        # Without this line the model refuses. The test of 2026-09-24 showed it
        # on case r1-10: it answered "I cannot include personal information
        # such as names", while the raw request gave "Happy Birthday, Jan!".
        upstream_body["messages"] = [{"role": "system", "content": HINT_TEXT}] \
            + upstream_body["messages"]
    upstream_body["model"] = target
    stream = bool(body.get("stream"))

    headers = {"Content-Type": "application/json"}
    if UPSTREAM_KEY:
        headers["Authorization"] = f"Bearer {UPSTREAM_KEY}"
    extra = {"x-pii-route": target, "x-pii-reason": reason,
             "x-pii-entities": str(len(masked.entities)),
             "x-pii-remains": str(audit["sensitive"]).lower(),
             "x-pii-difficulty": str(audit["difficulty"]),
             "x-pii-mask-seconds": f"{masked.seconds:.3f}",
             "x-pii-audit-seconds": f"{audit['seconds']:.3f}"}

    def write_log(total: float) -> None:
        conn = db()
        conn.execute("INSERT INTO decision (at, entities, types, remains, difficulty,"
                     " route, reason, mask_ms, audit_ms, total_ms, masked)"
                     " VALUES (datetime('now'),?,?,?,?,?,?,?,?,?,?)",
                     (len(masked.entities),
                      ",".join(sorted({e["entity_type"] for e in masked.entities})),
                      int(audit["sensitive"]), audit["difficulty"], target, reason,
                      int(masked.seconds * 1000), int(audit["seconds"] * 1000),
                      int(total * 1000), masked.text if LOG_MASKED else ""))
        conn.commit()
        conn.close()

    if not stream:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            answer = await client.post(f"{UPSTREAM}/v1/chat/completions",
                                       json=upstream_body, headers=headers)
        if answer.status_code != 200:
            raise HTTPException(502, f"upstream {answer.status_code}: {answer.text[:300]}")
        payload = answer.json()
        for choice in payload.get("choices", []):
            content = (choice.get("message") or {}).get("content")
            if isinstance(content, str):
                choice["message"]["content"] = gate.restore(content, masked.mapping)
        write_log(time.perf_counter() - started)
        return JSONResponse(payload, headers=extra)

    # The restore must read the decoded content, and not the raw bytes.
    #
    # A first version held back a few raw characters and replaced on the byte
    # stream. The test of 2026-09-24 proved that it fails: the model wrote
    # `<LOCATION` in one chunk and `_1>` in the next, so about 60 characters of
    # SSE framing sat between the 2 halves, and no window of that size helps.
    #
    # This version parses each `data:` frame, holds the decoded content of the
    # last frames in a window as long as the longest placeholder, restores on
    # that window, and writes the text back into the frame. The stream stays a
    # stream, and a split placeholder still restores.
    async def events():
        longest = max((len(k) for k in masked.mapping), default=0)
        raw = ""          # incomplete SSE text between 2 reads
        window = ""       # decoded content that is not sent yet
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            async with client.stream("POST", f"{UPSTREAM}/v1/chat/completions",
                                     json=upstream_body, headers=headers) as answer:
                async for chunk in answer.aiter_text():
                    raw += chunk
                    while "\n\n" in raw:
                        frame, raw = raw.split("\n\n", 1)
                        line = frame.strip()
                        if not line.startswith("data:"):
                            continue
                        body_text = line[5:].strip()
                        if body_text == "[DONE]":
                            continue
                        try:
                            event = json.loads(body_text)
                        except json.JSONDecodeError:
                            yield frame + "\n\n"     # not ours, pass it through
                            continue
                        choices = event.get("choices") or [{}]
                        delta = choices[0].get("delta") or {}
                        window += delta.get("content") or ""
                        # Restore first, then cut at the last `<`. A tail that
                        # starts with `<` can still grow into a placeholder, so
                        # it waits. A fixed window of `longest` characters does
                        # not work: the cut lands inside the placeholder as soon
                        # as 1 more character arrives after it.
                        window = gate.restore(window, masked.mapping)
                        cut = window.rfind("<")
                        if cut != -1 and len(window) - cut > longest:
                            cut = -1        # too long to become a placeholder
                        if cut == -1:
                            send, window = window, ""
                        else:
                            send, window = window[:cut], window[cut:]
                        delta["content"] = send
                        choices[0]["delta"] = delta
                        event["choices"] = choices
                        yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
        if window:
            tail = {"choices": [{"index": 0, "finish_reason": None,
                                 "delta": {"content": gate.restore(window, masked.mapping)}}],
                    "object": "chat.completion.chunk"}
            yield "data: " + json.dumps(tail, ensure_ascii=False) + "\n\n"
        yield "data: [DONE]\n\n"
        write_log(time.perf_counter() - started)

    return StreamingResponse(events(), media_type="text/event-stream", headers=extra)


@app.get("/log", response_class=HTMLResponse)
async def log_page() -> str:
    conn = db()
    rows = conn.execute("SELECT at, entities, types, remains, difficulty, route,"
                        " reason, mask_ms, audit_ms, total_ms, masked FROM decision"
                        " ORDER BY id DESC LIMIT 200").fetchall()
    conn.close()
    head = ("at", "entities", "types", "remains", "difficulty", "route", "reason",
            "mask ms", "audit ms", "total ms", "masked text")
    cells = "".join("<tr>" + "".join(f"<td>{str(v)}</td>" for v in row) + "</tr>"
                    for row in rows)
    return ("<html><head><title>pii-gate decisions</title>"
            "<style>body{font-family:sans-serif;margin:2rem}"
            "table{border-collapse:collapse;font-size:13px}"
            "td,th{border:1px solid #ccc;padding:4px 8px;text-align:left}"
            "th{background:#eee}</style></head><body>"
            "<h1>pii-gate decisions</h1><p>The last 200 requests. The original "
            "values are never stored.</p><table><tr>"
            + "".join(f"<th>{h}</th>" for h in head) + "</tr>" + cells
            + "</table></body></html>")


@app.get("/")
async def root() -> dict:
    return {"service": "pii-gate", "post": "/v1/chat/completions",
            "mask_only": "/v1/mask", "log": "/log", "health": "/healthz"}
