"""Tests for Project 8 Milestone 5: Air-Gapped Bundle Packaging and fieldkit-ctl CLI."""

from __future__ import annotations

import json
import subprocess
import tarfile
from pathlib import Path

from scripts.build_bundle import build_airgap_bundle

ROOT_DIR = Path(__file__).parent.parent


def test_build_bundle_manifest_and_contents(tmp_path: Path) -> None:
    """Verify that build_airgap_bundle packages all required assets and manifests."""
    archive, sig = build_airgap_bundle(tmp_path)
    assert archive.exists()
    assert sig.exists()

    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()
        # Verify top-level components in bundle
        assert any("manifest.json" in n for n in names)
        assert any("images_manifest.json" in n for n in names)
        assert any("Chart.yaml" in n for n in names)
        assert any("docker-compose.yml" in n for n in names)
        assert any("retrain-promote.yaml" in n for n in names)
        assert any("nightly-ingest.yaml" in n for n in names)

        # Read bundle manifest
        manifest_member = next(m for m in tar.getmembers() if m.name.split("/")[-1] == "manifest.json")
        f = tar.extractfile(manifest_member)
        assert f is not None
        manifest_data = json.load(f)
        assert manifest_data["format"] == "fieldkit-airgap-bundle"
        assert manifest_data["target_plant"] == "DE-HAM-OT"
        assert manifest_data["total_images"] >= 10


def test_fieldkit_ctl_preflight_and_dryrun(tmp_path: Path) -> None:
    """Verify fieldkit-ctl Go binary executes preflight inspection and dry-run install."""
    ctl_exe = ROOT_DIR / "services" / "workflow-engine" / "fieldkit-ctl.exe"
    if not ctl_exe.exists():
        # Build if not already built
        subprocess.run(
            ["go", "build", "-o", str(ctl_exe), "./cmd/fieldkit-ctl"],
            cwd=str(ROOT_DIR / "services" / "workflow-engine"),
            check=True,
        )

    # 1. Test Preflight JSON Output
    res = subprocess.run(
        [str(ctl_exe), "preflight", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(res.stdout)
    assert "cpu_cores" in report
    assert "memory_gb" in report
    assert report["cpu_cores"] >= 1
    assert "gate_results" in report

    # 2. Test Bundle Verification with fieldkit-ctl
    archive, _ = build_airgap_bundle(tmp_path)
    install_res = subprocess.run(
        [str(ctl_exe), "install", "--bundle", str(archive), "--dry-run"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "DRY-RUN COMPLETE" in install_res.stdout
    assert "VERIFIED" in install_res.stdout
