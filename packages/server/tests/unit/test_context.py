from __future__ import annotations

import pytest
from observatory.adapters.llm import LLMAdapter, LLMConfig
from observatory.adapters.prom import PromAdapter, PromConfig
from observatory.core.context import ObservatoryContext
from observatory.core.models import Capability


def _make_ctx() -> ObservatoryContext:
    prom = PromAdapter(PromConfig(base_url="http://prom:9090"))
    llm = LLMAdapter(LLMConfig(offline=True))
    return ObservatoryContext(prom=prom, llm=llm)


def test_guard_blocks_undeclared_prom() -> None:
    ctx = _make_ctx()
    guarded = ctx.guard(needs=frozenset({Capability.LLM}))
    with pytest.raises(PermissionError, match="capability not declared: prom"):
        _ = guarded.prom


def test_guard_allows_declared_prom() -> None:
    ctx = _make_ctx()
    guarded = ctx.guard(needs=frozenset({Capability.PROM}))
    # Should not raise — just return the adapter
    adapter = guarded.prom
    assert adapter is ctx.prom
