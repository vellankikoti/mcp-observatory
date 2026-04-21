from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.golden._runner import build_fake_ctx, normalise, run_tool

GOLDEN_ROOT = Path("tests/golden")


def _discover() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for tool_dir in sorted(GOLDEN_ROOT.iterdir()):
        if not tool_dir.is_dir() or tool_dir.name.startswith("_") or tool_dir.name == "__pycache__":
            continue
        for scenario_dir in sorted(tool_dir.iterdir()):
            if not scenario_dir.is_dir():
                continue
            if (
                (scenario_dir / "input_prom.json").exists()
                and (scenario_dir / "expected.json").exists()
                and (scenario_dir / "meta.json").exists()
            ):
                out.append((tool_dir.name, scenario_dir.name))
    return out


SCENARIOS = _discover()


@pytest.mark.golden
@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name,scenario", SCENARIOS, ids=[f"{t}/{s}" for t, s in SCENARIOS])
async def test_golden_scenario(tool_name: str, scenario: str) -> None:
    scenario_dir = GOLDEN_ROOT / tool_name / scenario
    canned = json.loads((scenario_dir / "input_prom.json").read_text())
    meta = json.loads((scenario_dir / "meta.json").read_text())
    expected = json.loads((scenario_dir / "expected.json").read_text())

    ctx = build_fake_ctx(canned)
    actual = await run_tool(ctx, meta["tool"], meta.get("args", {}))
    # Convert pydantic/dataclass to JSON-native for diff
    if hasattr(actual, "model_dump"):
        actual_data = actual.model_dump(mode="json")
    elif isinstance(actual, list):
        actual_data = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in actual
        ]
    else:
        actual_data = actual
    actual_norm = normalise(actual_data)
    assert actual_norm == expected
