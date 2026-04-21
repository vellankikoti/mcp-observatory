from __future__ import annotations

import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(shutil.which("helm") is None, reason="helm not installed")


def test_chart_lints_clean():
    r = subprocess.run(
        ["helm", "lint", "charts/observatory"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, f"helm lint failed:\n{r.stdout}\n{r.stderr}"
