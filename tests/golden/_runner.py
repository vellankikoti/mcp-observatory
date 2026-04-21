from __future__ import annotations

import json
from typing import Any

from observatory.adapters.llm import LLMAdapter, LLMConfig
from observatory.core.context import ObservatoryContext


class FakePromAdapter:
    """Replays canned Prometheus responses from a scenario's input_prom.json.

    Supports two modes:

    1. Legacy — ``input_prom.json`` has ``"query"`` / ``"query_range"`` keys.
       Every ``.query()`` call returns the same ``"query"`` payload.

    2. Substring-match — ``input_prom.json`` has a ``"queries"`` key whose
       value is a list of ``{"match": "<substring>", "response": {...}}``
       objects.  The first entry whose ``"match"`` string appears in the
       PromQL is returned; if nothing matches, falls back to the legacy
       ``"query"`` key (or an empty result set).
    """

    def __init__(self, canned: dict[str, Any]) -> None:
        self._canned = canned
        self.available = True

    async def query(self, promql: str) -> dict[str, Any]:
        for entry in self._canned.get("queries", []):
            if entry["match"] in promql:
                return entry["response"]
        return self._canned.get("query", {"result": []})

    async def query_range(
        self, promql: str, start: float, end: float, step: float
    ) -> dict[str, Any]:
        return self._canned.get("query_range", {"result": []})

    async def close(self) -> None:
        pass


def build_fake_ctx(canned: dict[str, Any]) -> ObservatoryContext:
    fake_prom = FakePromAdapter(canned)
    llm = LLMAdapter(LLMConfig(offline=True))
    return ObservatoryContext(prom=fake_prom, llm=llm)  # type: ignore[arg-type]


async def run_tool(ctx: ObservatoryContext, tool_name: str, args: dict[str, Any]) -> Any:
    """Dispatch to the tool function by name."""
    if tool_name == "list_mcp_servers":
        from observatory.tools.list_mcp_servers import NEEDS, list_mcp_servers

        return await list_mcp_servers(ctx.guard(needs=NEEDS), **args)
    if tool_name == "get_tool_call_rate":
        from observatory.tools.get_tool_call_rate import NEEDS, get_tool_call_rate

        return await get_tool_call_rate(ctx.guard(needs=NEEDS), **args)
    if tool_name == "detect_tool_abandonment":
        from observatory.tools.detect_tool_abandonment import (
            NEEDS,
            detect_tool_abandonment,
        )

        return await detect_tool_abandonment(ctx.guard(needs=NEEDS), **args)
    raise ValueError(f"unknown tool: {tool_name}")


def normalise(data: Any) -> Any:
    """Replace non-deterministic fields with placeholders."""
    import re

    s = json.dumps(data, default=str)
    # Replace ISO timestamps with placeholder
    s = re.sub(r'"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(\+00:00|Z)"', '"<ts>"', s)
    return json.loads(s)
