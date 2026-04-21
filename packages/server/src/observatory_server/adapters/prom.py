from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class PromConfig:
    base_url: str | None = None
    timeout_s: float = 10.0


class PromAdapter:
    def __init__(self, cfg: PromConfig) -> None:
        self.cfg = cfg
        self._client: httpx.AsyncClient | None = None
        self._cache: dict[tuple[str, str], dict[str, Any]] = {}

    @property
    def available(self) -> bool:
        return self.cfg.base_url is not None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            if self.cfg.base_url is None:
                raise RuntimeError("Prometheus base URL not configured")
            self._client = httpx.AsyncClient(base_url=self.cfg.base_url, timeout=self.cfg.timeout_s)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def query(self, promql: str) -> dict[str, Any]:
        key = ("instant", promql)
        if key in self._cache:
            return self._cache[key]
        client = await self._ensure_client()
        r = await client.get("/api/v1/query", params={"query": promql})
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "success":
            raise RuntimeError(f"Prometheus query failed: {data}")
        result: dict[str, Any] = data["data"]
        self._cache[key] = result
        return result

    async def query_range(
        self, promql: str, start: float, end: float, step: float
    ) -> dict[str, Any]:
        key = ("range", f"{promql}|{start}|{end}|{step}")
        if key in self._cache:
            return self._cache[key]
        client = await self._ensure_client()
        r = await client.get(
            "/api/v1/query_range",
            params={"query": promql, "start": start, "end": end, "step": step},
        )
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "success":
            raise RuntimeError(f"Prometheus range query failed: {data}")
        result: dict[str, Any] = data["data"]
        self._cache[key] = result
        return result
