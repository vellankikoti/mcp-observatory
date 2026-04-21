from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ACTION = Path("action.yml")


@pytest.fixture(scope="module")
def action():
    assert ACTION.exists()
    return yaml.safe_load(ACTION.read_text())


def test_action_is_composite(action):
    assert action["runs"]["using"] == "composite"


def test_action_declares_expected_inputs(action):
    expected = {"prom-url", "command", "args", "format", "offline", "image"}
    assert set(action["inputs"].keys()) == expected


def test_action_exposes_report_path_output(action):
    assert "report-path" in action["outputs"]


def test_default_image_pins_a_semver_tag(action):
    default_image = action["inputs"]["image"]["default"]
    assert default_image.startswith("ghcr.io/")
    tag = default_image.split(":")[-1]
    assert tag != "latest"
    assert tag.startswith("v")
