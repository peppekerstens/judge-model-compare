"""LiteLLM proxy pre-call hook that routes ``jev-router`` requests with Jev."""

from __future__ import annotations

from typing import Any

from litellm.integrations.custom_logger import CustomLogger

from .config import RouterConfig, build_decider, load_config
from .deciders import Decider, eligible, requested_max_output, summarize


class JevRouterLogger(CustomLogger):
    def __init__(self, config: RouterConfig | None = None) -> None:
        super().__init__()
        self._config = config
        self._decider: Decider | None = None

    def _ensure_ready(self) -> tuple[RouterConfig, Decider]:
        if self._config is None or self._decider is None:
            self._config = self._config or load_config()
            self._decider = build_decider(self._config)
        return self._config, self._decider

    async def async_pre_call_hook(
        self,
        user_api_key_dict: Any = None,
        cache: Any = None,
        data: dict[str, Any] | None = None,
        call_type: str | None = None,
    ) -> dict[str, Any]:
        payload = data or {}
        try:
            config, decider = self._ensure_ready()
        except Exception:
            return payload

        if payload.get("model") not in config.aliases:
            return payload

        try:
            summary = summarize(
                payload.get("messages", []),
                payload.get("tools"),
                requested_max_output(payload),
            )
            candidates = eligible(config.candidates, summary)
            chosen = await decider.decide(summary, candidates)
            payload["model"] = chosen or config.fallback
        except Exception:
            payload["model"] = config.fallback
        return payload


proxy_handler_instance = JevRouterLogger()
