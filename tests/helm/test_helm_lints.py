from __future__ import annotations

import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(shutil.which("helm") is None, reason="helm not installed")


def test_chart_lints_clean():
    r = subprocess.run(
        ["helm", "lint", "charts/observatory-server"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, f"helm lint failed:\n{r.stdout}\n{r.stderr}"


def test_deployment_has_observatory_container_with_serve_http():
    import yaml

    r = subprocess.run(
        ["helm", "template", "obs", "charts/observatory-server", "--namespace", "obs"],
        capture_output=True,
        text=True,
        check=True,
    )
    docs = [d for d in yaml.safe_load_all(r.stdout) if d]
    deploy = next(d for d in docs if d.get("kind") == "Deployment")
    container = deploy["spec"]["template"]["spec"]["containers"][0]
    assert container["name"] == "observatory-server"
    assert any("serve-http" in str(a) for a in container["args"])
