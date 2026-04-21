from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from observatory_server.core.context import ObservatoryContext
from observatory_server.tools.verify_services import NEEDS, verify_services


def _ctx(seen_services: list[str]) -> ObservatoryContext:
    prom = MagicMock()
    prom.query = AsyncMock(
        return_value={
            "result": [{"metric": {"service": s}, "value": [0, "1"]} for s in seen_services]
        }
    )
    return ObservatoryContext(prom=prom, llm=MagicMock())


@pytest.mark.asyncio
async def test_ok_when_all_expected_present() -> None:
    ctx = _ctx(["a", "b", "c"]).guard(needs=NEEDS)
    result = await verify_services(ctx, expected=["a", "b"])
    assert result.ok is True
    assert result.missing == []
    assert result.unexpected == ["c"]
    assert result.expected == ["a", "b"]
    assert result.seen == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_not_ok_when_expected_missing() -> None:
    ctx = _ctx(["a"]).guard(needs=NEEDS)
    result = await verify_services(ctx, expected=["a", "b"])
    assert result.ok is False
    assert result.missing == ["b"]
    assert result.unexpected == []


@pytest.mark.asyncio
async def test_empty_expected_always_ok() -> None:
    ctx = _ctx(["x", "y", "z"]).guard(needs=NEEDS)
    result = await verify_services(ctx, expected=[])
    assert result.ok is True
    assert result.missing == []
    assert result.expected == []
    assert result.seen == ["x", "y", "z"]
