from __future__ import annotations

from pathlib import Path

import yaml

WF = Path(".github/workflows/release.yml")


def test_release_workflow_publishes_both_packages():
    data = yaml.safe_load(WF.read_text())
    pypi_job = data["jobs"]["pypi"]
    steps = pypi_job["steps"]
    names = [s.get("name", "") for s in steps]
    assert any("Build sdk" in n for n in names)
    assert any("Build server" in n for n in names)
    assert any("Publish sdk" in n for n in names)
    assert any("Publish server" in n for n in names)


def test_release_workflow_signs_and_sboms():
    data = yaml.safe_load(WF.read_text())
    image_job = data["jobs"]["image"]
    steps = image_job["steps"]
    uses = [s.get("uses", "") for s in steps]
    names = [s.get("name", "") for s in steps]
    assert any(u.startswith("sigstore/cosign-installer") for u in uses)
    assert any("Sign image" in n for n in names)
    assert any(u.startswith("anchore/sbom-action") for u in uses)
    assert any("Attach SBOM" in n for n in names)
