from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from observatory_server.core.models import Capability

if TYPE_CHECKING:
    from observatory_server.adapters.llm import LLMAdapter
    from observatory_server.adapters.prom import PromAdapter


@dataclass
class ObservatoryContext:
    prom: PromAdapter
    llm: LLMAdapter
    scratch: dict[str, object] = field(default_factory=dict)

    def guard(self, *, needs: frozenset[Capability]) -> GuardedContext:
        return GuardedContext(self, needs)


class GuardedContext:
    def __init__(self, inner: ObservatoryContext, needs: frozenset[Capability]) -> None:
        self._inner = inner
        self._needs = needs

    @property
    def prom(self) -> PromAdapter:
        if Capability.PROM not in self._needs:
            raise PermissionError("capability not declared: prom")
        return self._inner.prom

    @property
    def llm(self) -> LLMAdapter:
        if Capability.LLM not in self._needs:
            raise PermissionError("capability not declared: llm")
        return self._inner.llm

    @property
    def scratch(self) -> dict[str, object]:
        return self._inner.scratch
