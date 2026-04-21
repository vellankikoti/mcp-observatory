from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_OLLAMA_PROBE_TIMEOUT = 1.0


class OfflineError(RuntimeError):
    """Raised when an LLM call is attempted in offline mode."""


@dataclass
class LLMConfig:
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    offline: bool = False
    timeout_s: float = 30.0
    extra: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_sources(
        cls,
        *,
        cli_provider: str | None = None,
        cli_base_url: str | None = None,
        cli_api_key: str | None = None,
        cli_offline: bool | None = None,
    ) -> LLMConfig:
        offline = (
            cli_offline if cli_offline is not None else os.environ.get("OBSERVATORY_OFFLINE") == "1"
        )
        return cls(
            provider=cli_provider or os.environ.get("OBSERVATORY_LLM_PROVIDER"),
            base_url=cli_base_url or os.environ.get("OBSERVATORY_LLM_BASE_URL"),
            api_key=cli_api_key or os.environ.get("OBSERVATORY_LLM_API_KEY"),
            offline=offline,
        )


async def _probe_ollama(url: str) -> bool:
    """Return True if Ollama is reachable at *url*."""
    async with asyncio.timeout(_OLLAMA_PROBE_TIMEOUT):
        async with httpx.AsyncClient() as c:
            r = await c.get(url.rstrip("/") + "/api/tags")
            return r.status_code == 200


class LLMAdapter:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._ready = False
        self._effectively_offline = config.offline

    @property
    def effectively_offline(self) -> bool:
        return self._effectively_offline

    async def ensure_ready(self) -> None:
        if self._ready:
            return
        if self.config.offline:
            self._effectively_offline = True
        elif self.config.provider is None:
            url = self.config.base_url or "http://localhost:11434"
            try:
                ok = await _probe_ollama(url)
            except Exception:
                ok = False
            if not ok:
                self._effectively_offline = True
            else:
                self.config.provider = "ollama/qwen2.5:7b"
                self.config.base_url = url
        self._ready = True

    async def structured(
        self,
        prompt: str,
        *,
        response_model: type[T],
        system: str | None = None,
    ) -> T:
        await self.ensure_ready()
        if self._effectively_offline:
            raise OfflineError("LLM unavailable; running in offline mode")
        # Real call happens here. We import lazily so unit tests that mock
        # ensure_ready() can skip the network path.
        import instructor
        from litellm import acompletion

        client = instructor.from_litellm(acompletion)
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await client.chat.completions.create(  # type: ignore[no-any-return]
            model=self.config.provider,
            messages=messages,
            response_model=response_model,
            api_key=self.config.api_key,
            api_base=self.config.base_url,
            timeout=self.config.timeout_s,
        )
