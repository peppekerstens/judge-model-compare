"""The PII gate: mask the spans, audit the masked text, route, and restore.

The chain is the one the plan describes.

    requestor -> detector -> replacer -> filtered call out -> restore

  detector  Presidio analyzer. It returns a span for each entity it finds.
  replacer  This module. It replaces every span with a numbered placeholder,
            and it keeps the map. The map never leaves the process.
  audit     The llama.cpp fork with `/v1/decision`. It reads the masked text and
            answers 1 question: does sensitive data remain? A yes keeps the
            request inside the network.
  restore   It puts the original value back into the answer of the model.

Why this module replaces the spans itself, and not the Presidio anonymizer
container: the anonymizer takes 1 rule for each entity type, so 2 people both
become `<PERSON>`. A round trip needs a placeholder for each instance. The
anonymizer container stays deployed, because the LiteLLM guardrail needs it.

Every placeholder is `<TYPE_n>`, with n counted for each type. The same value
always gets the same number inside one request.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field

# Recognizers that Presidio does not ship. They go in the request itself, as
# `ad_hoc_recognizers`, so the analyzer image needs no change.
AD_HOC_RECOGNIZERS = [
    {"name": "aws-access-key", "supported_language": "en",
     "supported_entity": "AWS_ACCESS_KEY",
     "patterns": [{"name": "akia", "regex": r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b", "score": 0.9}]},
    {"name": "aws-secret-key", "supported_language": "en",
     "supported_entity": "AWS_SECRET_KEY",
     "patterns": [{"name": "secret40", "regex": r"\b[A-Za-z0-9/+=]{40}\b", "score": 0.6}],
     "context": ["secret", "aws", "key"]},
    # Presidio finds a place ("Utrecht") but not a Dutch street with a house
    # number. The bench proved it on case r1-10 with "Kerkstraat 12".
    {"name": "dutch-street", "supported_language": "en",
     "supported_entity": "STREET_ADDRESS",
     "patterns": [{"name": "street-and-number",
                   "regex": r"\b[A-Z][a-z]+(?:straat|laan|weg|plein|kade|dijk|"
                            r"singel|gracht|hof|park|baan|steeg|pad)\s+\d+[a-zA-Z]?\b",
                   "score": 0.85}]},
    {"name": "password-after-label", "supported_language": "en",
     "supported_entity": "PASSWORD",
     "patterns": [{"name": "labelled",
                   "regex": r"(?i)(?<=password[:=]\s)\S+", "score": 0.85}]},
]

# A low score means a guess. Presidio gives 0.05 to a weak match, and that
# masks ordinary numbers. 0.4 keeps the real finds and drops the noise.
MIN_SCORE = 0.4

# Entity types that we never mask. A date or an amount breaks a tool call, and
# Presidio marks almost every number as one of these.
SKIP_TYPES = {"DATE_TIME", "US_BANK_NUMBER", "US_DRIVER_LICENSE", "US_ITIN",
              "US_PASSPORT", "US_SSN", "NRP", "URL"}


@dataclass
class MaskResult:
    text: str
    mapping: dict = field(default_factory=dict)   # placeholder -> original
    entities: list = field(default_factory=list)  # the raw Presidio spans we used
    seconds: float = 0.0


def _post(url: str, payload: dict, timeout: float = 60.0) -> dict | list:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return json.loads(fh.read())


def analyze(text: str, analyzer_url: str, language: str = "en") -> list:
    """Ask Presidio for every span. It returns the raw list, unfiltered."""
    return _post(analyzer_url.rstrip("/") + "/analyze",
                 {"text": text, "language": language,
                  "ad_hoc_recognizers": AD_HOC_RECOGNIZERS})


def pick_spans(spans: list, min_score: float = MIN_SCORE) -> list:
    """Drop the weak and the unwanted spans, then drop every overlap.

    Presidio returns overlapping spans for the same characters. The strongest
    span wins, and a span inside a chosen span goes away.
    """
    keep = [s for s in spans
            if s["score"] >= min_score and s["entity_type"] not in SKIP_TYPES]
    keep.sort(key=lambda s: (-s["score"], s["start"] - s["end"]))
    chosen: list = []
    for span in keep:
        if any(span["start"] < c["end"] and c["start"] < span["end"] for c in chosen):
            continue
        chosen.append(span)
    chosen.sort(key=lambda s: s["start"])
    return chosen


def mask(text: str, analyzer_url: str, language: str = "en") -> MaskResult:
    """Replace every span with a numbered placeholder, and keep the map."""
    started = time.perf_counter()
    spans = pick_spans(analyze(text, analyzer_url, language))
    counters: dict = {}
    by_value: dict = {}
    mapping: dict = {}
    out = text
    for span in reversed(spans):          # right to left, so the offsets hold
        original = text[span["start"]:span["end"]]
        etype = span["entity_type"]
        key = (etype, original)
        if key in by_value:
            placeholder = by_value[key]
        else:
            counters[etype] = counters.get(etype, 0) + 1
            placeholder = f"<{etype}_{counters[etype]}>"
            by_value[key] = placeholder
            mapping[placeholder] = original
        out = out[:span["start"]] + placeholder + out[span["end"]:]
    return MaskResult(text=out, mapping=mapping, entities=spans,
                      seconds=time.perf_counter() - started)


# A secret must never come back into the answer. The traffic test of 2026-09-24
# proved the need on case r1-11: the model wrote the real password into its own
# example, and the raw model had used a placeholder and a warning instead.
SECRET_TYPES = {"PASSWORD", "AWS_ACCESS_KEY", "AWS_SECRET_KEY", "API_KEY"}

PLACEHOLDER_RE = re.compile(r"<([A-Z][A-Z_]*)_(\d+)>")


def is_secret(placeholder: str) -> bool:
    found = PLACEHOLDER_RE.fullmatch(placeholder)
    return bool(found) and found.group(1) in SECRET_TYPES


def restore(text: str, mapping: dict, keep_secrets: bool = True) -> str:
    """Put the original value back. A missing placeholder is not an error.

    With `keep_secrets` the placeholder of a secret stays in the answer, so a
    password or a key never reaches the screen again.
    """
    for placeholder, original in mapping.items():
        if keep_secrets and is_secret(placeholder):
            continue
        text = text.replace(placeholder, original)
    return strip_unknown(text, mapping)


def strip_unknown(text: str, mapping: dict) -> str:
    """Replace a placeholder that the model invented with a readable word.

    The traffic test of 2026-09-24 showed it on case r2-01: the map held
    `<IP_ADDRESS_1>` only, and the model wrote `<IP_ADDRESS_2>` for a second
    example address. No map entry can fill that, so the answer kept the raw
    placeholder. A readable word is better than angle brackets.
    """
    def word(found: "re.Match") -> str:
        name = found.group(1)
        if found.group(0) in mapping:
            return found.group(0)          # a real one, and a secret we keep
        return "the " + name.replace("_", " ").lower()
    return PLACEHOLDER_RE.sub(word, text)


# Round 1 of the wording, kept for the record. It scored 18 of 24 on the
# sensitivity question, and it missed both residual values. The words "already
# removed" made the model read the whole text as safe.
AUDIT_SENSITIVE_V1 = (
    "Does the text still contain personal data or sensitive information? A part "
    "between angle brackets, such as <PERSON_1>, is already removed and is not "
    "sensitive. Answer true only for a real name, address, e-mail address, "
    "telephone number, bank detail, medical detail, password, key, internal IP "
    "address or private file path that is still readable.")

# Round 2. It asks the same question as the judge of the router, and it names
# the street and the medical fact, because those are the 2 values that Presidio
# leaves behind.
AUDIT_SENSITIVE = (
    "Does the text contain personal data or sensitive information? Personal data "
    "is a name, a street, a house number, a postal code, a place of residence, an "
    "e-mail address, a telephone number, a bank detail, or a medical fact about a "
    "person. Sensitive information is a password, an API key, an internal IP "
    "address, or a private file path. A part between angle brackets, such as "
    "<PERSON_1>, is a placeholder and is already safe. Answer true when any other "
    "part of the text still shows a real value.")

# The fork needs the level criteria in the field description. Without them it
# scored 12 of 24. The words are the same as `poc/router/router.yaml` uses.
AUDIT_DIFFICULTY = (
    "How hard is this request for a language model? Judge the reasoning that the "
    "answer needs, not the length of the text. simple: a fact, a definition, a "
    "short rewrite, a translation, a greeting, or a question with one clear "
    "answer. medium: a short explanation, a small piece of code, a summary, or a "
    "comparison with 2 or 3 reasoning steps. hard: a multi-step analysis, a design "
    "or an architecture question, a proof, a long piece of code, or a trade-off "
    "between several options.")


def audit(masked_text: str, fork_url: str, timeout: float = 60.0) -> dict:
    """Ask the fork 1 call with 2 fields. It returns the values and the time."""
    started = time.perf_counter()
    out = _post(fork_url.rstrip("/") + "/v1/decision", {
        "instructions": "Read the text and answer both fields.",
        "schema": {
            "sensitive": {"type": "boolean", "description": AUDIT_SENSITIVE},
            "difficulty": {"type": "enum", "choices": ["simple", "medium", "hard"],
                           "description": AUDIT_DIFFICULTY},
        },
        "contexts": [masked_text],
        "cache_prompt": True,
    }, timeout=timeout)
    seconds = time.perf_counter() - started
    fields = out["results"][0]["fields"]
    sensitive = fields["sensitive"]["value"]
    return {"raw": out, "seconds": seconds,
            "sensitive": sensitive in (True, "true", "yes"),
            "sensitive_p": float(fields["sensitive"]["probability"]),
            "difficulty": fields["difficulty"]["value"],
            "difficulty_p": float(fields["difficulty"]["probability"])}


# The target names must match the upstream gateway. LiteLLM holds no cloud tier,
# so ROUTE_HARD points at a local tier there. The proof of concept router on
# port 8081 does hold the cloud tier, and ROUTE_HARD=qwen3.7-max then applies.
def route(sensitive_remains: bool, difficulty: str) -> tuple:
    """The rule of the proof of concept. Sensitivity wins over difficulty."""
    sensitive_target = os.environ.get("ROUTE_SENSITIVE", "qwen3.8-27b-local")
    if sensitive_remains:
        return sensitive_target, "sensitive data remains after the mask"
    table = {
        "simple": (os.environ.get("ROUTE_SIMPLE", "qwen3.8-27b-nothink"),
                   "simple, so the local fast tier"),
        "medium": (os.environ.get("ROUTE_MEDIUM", "qwen3.8-27b-local"),
                   "medium, so the local tier"),
        "hard": (os.environ.get("ROUTE_HARD", "qwen3.7-max"),
                 "hard, so the strongest tier"),
    }
    return table.get(difficulty, (sensitive_target, "unknown difficulty, so the local tier"))


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if not value:
        raise SystemExit(f"{name} is missing. Add it to .env (see .env.example).")
    return value
