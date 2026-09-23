"""Jev-style router: one judge call, then the request goes to the chosen model.

The decision code follows prismhq/jev-router (MIT): summarize the request,
keep the eligible candidates, ask the judge, fall back on any error. New here:
2 questions instead of 1 (sensitive data and difficulty), a rule order, a
SQLite log, and a web page that shows the decisions.

Rules, in this order:
  1. Sensitive data (personal data, secrets, internal facts) -> the local model.
  2. Difficulty: simple -> the fast local model, medium -> the local model,
     hard -> the cloud model.

Endpoints:
  POST /v1/chat/completions   OpenAI shape. Routes, then proxies. `stream: true`
                              passes every event through. The route then sits in the
                              headers x-jev-route, x-jev-reason and x-jev-difficulty.
  GET  /                      the web page with the decision log
  GET  /api/decisions         the log as JSON
  GET  /health                the state of the judge and each target
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

import httpx
import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

CONFIG = Path(os.environ.get("ROUTER_CONFIG", "/app/router.yaml"))
DB = Path(os.environ.get("ROUTER_DB", "/data/decisions.db"))
JUDGE_URL = os.environ.get("JUDGE_URL", "http://semif-judge:8080")
MAX_SUMMARY_MESSAGES = 8
MAX_SUMMARY_CHARS = 2000

app = FastAPI(title="jev-router-poc")
# Expand ${VAR} from the environment, so no address sits in the policy file.
config = yaml.safe_load(os.path.expandvars(CONFIG.read_text()))
TARGETS = {t["name"]: t for t in config["targets"]}


def db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS decisions (
        id TEXT PRIMARY KEY, ts REAL, preview TEXT, sensitive INTEGER,
        sensitive_p REAL, difficulty TEXT, difficulty_p REAL, chosen TEXT,
        reason TEXT, judge_s REAL, model_s REAL, status INTEGER, error TEXT)""")
    return conn


def content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    parts.append(str(part.get("text", "")))
                elif part.get("type") in ("image_url", "input_image"):
                    parts.append("[image]")
        return " ".join(parts).strip()
    return ""


def summarize(messages: list) -> dict:
    recent = messages[-MAX_SUMMARY_MESSAGES:]
    return {"messages": [{"role": str(m.get("role", "user")),
                          "text": content_text(m.get("content"))[:MAX_SUMMARY_CHARS]}
                         for m in recent],
            "message_count": len(messages)}


async def ask_judge(state: dict) -> dict:
    body = {"state": state, "questions": {
        "sensitive": {"type": "noul", "instructions": config["questions"]["sensitive"],
                      "criteria": {"true": config["questions"]["sensitive_true"],
                                   "false": config["questions"]["sensitive_false"]}},
        "difficulty": {"type": "choice", "instructions": config["questions"]["difficulty"],
                       "criteria": config["questions"]["difficulty_levels"]}}}
    async with httpx.AsyncClient(timeout=config.get("judge_timeout_s", 30)) as client:
        response = await client.post(f"{JUDGE_URL}/v1/systemone", json=body)
    response.raise_for_status()
    return response.json()["answers"]


def decide(answers: dict) -> tuple[str, str]:
    """Return the target name and the reason. Sensitive data never goes to the cloud."""
    if answers["sensitive"]["noul"]:
        return config["routes"]["sensitive"], "sensitive data stays local"
    level = answers["difficulty"]["choice"]
    return config["routes"][level], f"difficulty {level}"


def build_request(name: str, payload: dict, stream: bool) -> tuple[dict, dict, dict]:
    """Return the target, the body and the headers for one call."""
    target = TARGETS[name]
    body = dict(payload)
    body["model"] = target["model"]
    if stream:
        body["stream"] = True
    else:
        body.pop("stream", None)
        body.pop("stream_options", None)
    for key, value in (target.get("params") or {}).items():
        body[key] = value
    headers = {"Content-Type": "application/json", **(target.get("headers") or {})}
    key = os.environ.get(target["api_key_env"], "") if target.get("api_key_env") else ""
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return target, body, headers


async def call_target(name: str, payload: dict) -> tuple[int, dict]:
    target, body, headers = build_request(name, payload, stream=False)
    async with httpx.AsyncClient(timeout=target.get("timeout_s", 600)) as client:
        response = await client.post(f"{target['api_base']}/chat/completions",
                                     json=body, headers=headers)
    try:
        return response.status_code, response.json()
    except json.JSONDecodeError:
        return response.status_code, {"error": response.text[:2000]}


async def stream_target(name: str, payload: dict, row_id: str):
    """Send the request with stream: true, and pass every event through.

    The log row exists before the first event, because the route is known then.
    The status and the model time go into the row when the stream ends.
    """
    target, body, headers = build_request(name, payload, stream=True)
    started = time.perf_counter()
    status, error = None, None
    try:
        async with httpx.AsyncClient(timeout=target.get("timeout_s", 600)) as client:
            async with client.stream("POST", f"{target['api_base']}/chat/completions",
                                     json=body, headers=headers) as response:
                status = response.status_code
                if status != 200:
                    raw = await response.aread()
                    error = raw.decode("utf-8", "replace")[:300]
                    yield b"data: " + json.dumps({"error": error}).encode() + b"\n\n"
                else:
                    tail = b""
                    async for chunk in response.aiter_raw():
                        # Keep the last bytes: the backend can end a stream with an
                        # error event, for example a content filter at the cloud model.
                        tail = (tail + chunk)[-2000:]
                        yield chunk
                    if b'"error"' in tail and b"[DONE]" not in tail:
                        error = "stream ended with an error event: " + \
                                tail.decode("utf-8", "replace")[-200:]
    except Exception as failure:  # noqa: BLE001
        error = f"{type(failure).__name__}: {failure}"[:300]
        yield b"data: " + json.dumps({"error": error}).encode() + b"\n\n"
    finally:
        finish_row(row_id, status, time.perf_counter() - started, error)


def insert_row(row: dict) -> None:
    with db() as conn:
        conn.execute("INSERT INTO decisions VALUES (:id,:ts,:preview,:sensitive,:sensitive_p,"
                     ":difficulty,:difficulty_p,:chosen,:reason,:judge_s,:model_s,:status,:error)", row)


def finish_row(row_id: str, status, model_s: float, error) -> None:
    with db() as conn:
        conn.execute("UPDATE decisions SET status=?, model_s=?, error=COALESCE(?, error) "
                     "WHERE id=?", (status, model_s, error, row_id))


@app.post("/v1/chat/completions")
async def chat(request: Request) -> JSONResponse:
    payload = await request.json()
    messages = payload.get("messages") or []
    if not messages:
        raise HTTPException(400, "messages is empty")
    state = summarize(messages)
    preview = (state["messages"][-1]["text"] or "")[:300]
    row = {"id": str(uuid.uuid4()), "ts": time.time(), "preview": preview,
           "sensitive": 0, "sensitive_p": None, "difficulty": None, "difficulty_p": None,
           "chosen": None, "reason": None, "judge_s": None, "model_s": None,
           "status": None, "error": None}

    started = time.perf_counter()
    try:
        answers = await ask_judge(state)
        row["judge_s"] = time.perf_counter() - started
        row["sensitive"] = int(answers["sensitive"]["noul"])
        row["sensitive_p"] = answers["sensitive"]["probabilities"]["true"]
        row["difficulty"] = answers["difficulty"]["choice"]
        row["difficulty_p"] = answers["difficulty"]["confidence"]
        chosen, reason = decide(answers)
    except Exception as error:  # noqa: BLE001
        row["judge_s"] = time.perf_counter() - started
        chosen, reason = config["routes"]["fallback"], f"judge failed: {type(error).__name__}"
        row["error"] = str(error)[:300]
    row["chosen"], row["reason"] = chosen, reason

    route_headers = {"x-jev-route": chosen, "x-jev-reason": reason,
                     "x-jev-sensitive": str(bool(row["sensitive"])).lower(),
                     "x-jev-difficulty": str(row["difficulty"]),
                     "x-jev-judge-seconds": "%.3f" % (row["judge_s"] or 0)}

    if payload.get("stream"):
        # The answer is a stream, so the route travels in the headers, not in the body.
        insert_row(row)
        return StreamingResponse(stream_target(chosen, payload, row["id"]),
                                 media_type="text/event-stream",
                                 headers={**route_headers, "Cache-Control": "no-store",
                                          "X-Accel-Buffering": "no"})

    started = time.perf_counter()
    status, body = await call_target(chosen, payload)
    row["model_s"] = time.perf_counter() - started
    row["status"] = status
    if status != 200:
        row["error"] = json.dumps(body)[:300]
    insert_row(row)
    if isinstance(body, dict):
        body.setdefault("x_jev_router", {"chosen": chosen, "reason": reason,
                                         "sensitive": bool(row["sensitive"]),
                                         "difficulty": row["difficulty"],
                                         "judge_seconds": row["judge_s"]})
    return JSONResponse(body, status_code=status, headers=route_headers)


@app.get("/api/decisions")
def decisions(limit: int = 50) -> list:
    with db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM decisions ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


@app.get("/health")
async def health() -> dict:
    out = {"judge": "unknown", "targets": {}}
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            out["judge"] = (await client.get(f"{JUDGE_URL}/health")).json()
        except Exception as error:  # noqa: BLE001
            out["judge"] = f"error: {type(error).__name__}"
        for name, target in TARGETS.items():
            if target.get("api_key_env") and not os.environ.get(target["api_key_env"]):
                out["targets"][name] = "no key"
                continue
            try:
                response = await client.get(f"{target['api_base']}/models",
                                            headers={"Authorization": f"Bearer {os.environ.get(target.get('api_key_env',''),'x')}"})
                out["targets"][name] = response.status_code
            except Exception as error:  # noqa: BLE001
                out["targets"][name] = f"error: {type(error).__name__}"
    return out


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Jev router log</title>
<meta http-equiv="refresh" content="10">
<style>body{font-family:system-ui,sans-serif;margin:2rem;background:#fbfbfa;color:#1a1a1a}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{border-bottom:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f0f0ef}.cloud{color:#b3261e;font-weight:600}.local{color:#1d6b32;font-weight:600}
.pill{border-radius:10px;padding:1px 8px;font-size:12px;background:#eee}code{font-size:13px}</style></head>
<body><h1>Jev router: decision log</h1>
<p>The page refreshes every 10 seconds. The judge model runs on legion-t5.</p>
<table><tr><th>Time</th><th>Request</th><th>Sensitive</th><th>Difficulty</th><th>Model</th>
<th>Reason</th><th>Judge</th><th>Model time</th><th>Status</th></tr>%ROWS%</table></body></html>"""


@app.get("/", response_class=HTMLResponse)
def page() -> str:
    rows = []
    for d in decisions(100):
        cls = "cloud" if TARGETS.get(d["chosen"], {}).get("cloud") else "local"
        rows.append(
            "<tr><td>{ts}</td><td><code>{preview}</code></td><td>{sens}</td><td>{diff}</td>"
            "<td class='{cls}'>{chosen}</td><td>{reason}</td><td>{judge}</td><td>{model}</td>"
            "<td>{status}{err}</td></tr>".format(
                ts=time.strftime("%H:%M:%S", time.localtime(d["ts"])),
                preview=(d["preview"] or "")[:120].replace("<", "&lt;"),
                sens=("%s %.2f" % ("yes" if d["sensitive"] else "no", d["sensitive_p"]))
                     if d["sensitive_p"] is not None else "-",
                diff=("%s %.2f" % (d["difficulty"], d["difficulty_p"])) if d["difficulty"] else "-",
                cls=cls, chosen=d["chosen"], reason=d["reason"] or "",
                judge=("%.2f s" % d["judge_s"]) if d["judge_s"] else "-",
                model=("%.2f s" % d["model_s"]) if d["model_s"] else "-",
                status=d["status"],
                err=(" <span class='pill'>%s</span>" % d["error"][:60].replace("<", "&lt;")) if d["error"] else ""))
    return PAGE.replace("%ROWS%", "".join(rows) or "<tr><td colspan='9'>No request yet.</td></tr>")
