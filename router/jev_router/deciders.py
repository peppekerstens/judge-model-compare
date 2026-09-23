"""Routing decisions for jev-router.

The decision layer is dependency-free: it only uses the standard library so it can
be unit-tested and reused outside the LiteLLM proxy. The LiteLLM hook imports it.
"""

from __future__ import annotations

import asyncio
import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Protocol, Sequence

TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_JEV_MODEL = "jev-latest"
MAX_SUMMARY_MESSAGES = 8
MAX_SUMMARY_CHARS = 2000


@dataclass(frozen=True)
class Candidate:
    """A model the router may choose. ``name`` must match a LiteLLM model_name."""

    name: str
    description: str
    vision: bool = False
    tools: bool = True
    context: int | None = None
    max_output: int | None = None
    price_in: float | None = None
    price_out: float | None = None


@dataclass(frozen=True)
class RequestSummary:
    messages: list[dict[str, str]]
    has_image: bool
    has_tools: bool
    requested_max_output: int | None
    message_count: int


class Decider(Protocol):
    async def decide(
        self, summary: RequestSummary, candidates: Sequence[Candidate]
    ) -> str | None: ...


def _part_text(part: Any) -> str:
    if not isinstance(part, dict):
        return ""
    if part.get("type") == "text":
        return str(part.get("text", ""))
    if part.get("type") in ("image_url", "input_image"):
        return "[image]"
    return ""


def _content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(_part_text(part) for part in content).strip()
    return ""


def has_image(messages: Sequence[dict[str, Any]]) -> bool:
    for message in messages:
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, list) and any(
            isinstance(part, dict)
            and part.get("type") in ("image_url", "input_image")
            for part in content
        ):
            return True
    return False


def requested_max_output(payload: dict[str, Any]) -> int | None:
    return payload.get("max_completion_tokens") or payload.get("max_tokens")


def summarize(
    messages: Sequence[dict[str, Any]],
    tools: Any = None,
    max_output: int | None = None,
) -> RequestSummary:
    recent = list(messages)[-MAX_SUMMARY_MESSAGES:]
    minimized = [
        {
            "role": str(message.get("role", "user")),
            "text": _content_text(message.get("content"))[:MAX_SUMMARY_CHARS],
        }
        for message in recent
    ]
    return RequestSummary(
        messages=minimized,
        has_image=has_image(messages),
        has_tools=bool(tools),
        requested_max_output=max_output,
        message_count=len(messages),
    )


def eligible(
    candidates: Sequence[Candidate], summary: RequestSummary
) -> list[Candidate]:
    kept: list[Candidate] = []
    for candidate in candidates:
        if summary.has_image and not candidate.vision:
            continue
        if (
            summary.requested_max_output is not None
            and candidate.max_output is not None
            and summary.requested_max_output > candidate.max_output
        ):
            continue
        if summary.has_tools and not candidate.tools:
            continue
        kept.append(candidate)
    return kept


def _blended_price(candidate: Candidate) -> float:
    return (candidate.price_in or 0.0) + (candidate.price_out or 0.0)


class RulesDecider:
    """Zero-dependency baseline: cheapest eligible model, else the fallback."""

    def __init__(self, fallback: str) -> None:
        self._fallback = fallback

    async def decide(
        self, summary: RequestSummary, candidates: Sequence[Candidate]
    ) -> str | None:
        if not candidates:
            return self._fallback or None
        return min(candidates, key=_blended_price).name


Fetch = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]


def _default_fetch(
    url: str, headers: dict[str, str], body: bytes, timeout_s: float
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        return response.status, response.read()


class JevDecider:
    """Asks TypeSafe's Jev (System One) to pick among the eligible candidates."""

    def __init__(
        self,
        api_key: str,
        fallback: str,
        model: str = DEFAULT_JEV_MODEL,
        url: str = TYPESAFE_URL,
        timeout_s: float = 5.0,
        fetch: Fetch | None = None,
    ) -> None:
        self._api_key = api_key
        self._fallback = fallback
        self._model = model
        self._url = url
        self._timeout_s = timeout_s
        self._fetch = fetch or _default_fetch

    def _payload(
        self, summary: RequestSummary, candidates: Sequence[Candidate]
    ) -> bytes:
        instructions = (
            "Choose the single best model to serve this request. Prefer the "
            "cheapest model that clears the task's quality bar, and choose a "
            "stronger model only when the task is hard enough to justify the "
            "extra cost. Every listed model can serve the request."
        )
        return json.dumps(
            {
                "state": {
                    "messages": summary.messages,
                    "signals": {
                        "image_input": summary.has_image,
                        "tools": summary.has_tools,
                        "message_count": summary.message_count,
                    },
                },
                "model": self._model,
                "questions": {
                    "model": {
                        "type": "choice",
                        "instructions": instructions,
                        "criteria": {
                            candidate.name: candidate.description
                            for candidate in candidates
                        },
                    }
                },
            }
        ).encode("utf-8")

    async def decide(
        self, summary: RequestSummary, candidates: Sequence[Candidate]
    ) -> str | None:
        if not candidates:
            return self._fallback or None
        body = self._payload(summary, candidates)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            status, raw = await asyncio.to_thread(
                self._fetch, self._url, headers, body, self._timeout_s
            )
            if status != 200:
                return self._fallback or candidates[0].name
            parsed = json.loads(raw)
            choice = parsed["answers"]["model"]["choice"]
        except Exception:
            return self._fallback or candidates[0].name

        names = {candidate.name for candidate in candidates}
        return choice if choice in names else (self._fallback or candidates[0].name)
