from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from .deciders import Candidate, Decider, JevDecider, RulesDecider


@dataclass(frozen=True)
class RouterConfig:
    fallback: str
    candidates: list[Candidate]
    aliases: list[str]
    objective: str
    jev_model: str
    jev_timeout_s: float


def load_config(path: str | os.PathLike[str] | None = None) -> RouterConfig:
    resolved = Path(path or os.environ.get("JEV_ROUTER_CONFIG", "router.yaml"))
    raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    jev = raw.get("jev") or {}
    return RouterConfig(
        fallback=raw["fallback"],
        candidates=[Candidate(**candidate) for candidate in raw["candidates"]],
        aliases=raw.get("aliases", ["jev-router"]),
        objective=raw.get("objective", "quality_per_dollar"),
        jev_model=jev.get("model", "jev-latest"),
        jev_timeout_s=float(jev.get("timeout_ms", 5000)) / 1000,
    )


def build_decider(config: RouterConfig) -> Decider:
    """Use Jev when a TypeSafe key is present, otherwise the rules baseline."""
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if api_key:
        return JevDecider(
            api_key=api_key,
            fallback=config.fallback,
            model=config.jev_model,
            timeout_s=config.jev_timeout_s,
        )
    return RulesDecider(fallback=config.fallback)
