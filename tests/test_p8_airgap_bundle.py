"""Tests for Project 8 Milestone 5: Air-Gapped Bundle Packaging and fieldkit-ctl CLI."""

from __future__ import annotations

import json
import subprocess
import tarfile
from pathlib import Path

from scripts.build_bundle import build_airgap_bundle

ROOT_DIR = Path(__file__).parent.parent


def _ensure_ctl_binary() -> Path:
    ctl_exe = ROOT_DIR / "services" / "workflow-engine" / "fieldkit-ctl.exe"
    subprocess.run(
        ["go", "build", "-o", str(ctl_exe), "./cmd/fieldkit-ctl"],
        cwd=str(ROOT_DIR / "services" / "workflow-engine"),
        check=True,
    )
    return ctl_exe


def test_build_bundle_manifest_and_contents(tmp_path: Path) -> None:
    """Verify that build_airgap_bundle packages all required assets and manifests."""
    _ensure_ctl_binary()
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
    ctl_exe = _ensure_ctl_binary()

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


def test_fieldkit_ctl_ecdsa_sign_and_verify(tmp_path: Path) -> None:
    """Verify cryptographic signing and verification via fieldkit-ctl."""
    ctl_exe = _ensure_ctl_binary()

    sample_file = tmp_path / "payload.bin"
    sample_file.write_bytes(b"FIELDKIT_CRITICAL_PAYLOAD_DE_HAM_OT_2026")

    # Sign the file
    sign_res = subprocess.run(
        [str(ctl_exe), "sign", "--file", str(sample_file)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Generated cryptographic signature" in sign_res.stdout

    sig_file = sample_file.with_suffix(sample_file.suffix + ".sig")
    pub_file = sample_file.with_suffix(sample_file.suffix + ".pub")
    assert sig_file.exists()
    assert pub_file.exists()

    # Verify the signature
    verify_res = subprocess.run(
        [str(ctl_exe), "verify", "--file", str(sample_file)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "VERIFIED" in verify_res.stdout


def test_fieldkit_ctl_tampered_bundle_fails_verification(tmp_path: Path) -> None:
    """Verify fail-closed security: tampered bundle signature verification fails."""
    ctl_exe = _ensure_ctl_binary()

    archive, _ = build_airgap_bundle(tmp_path)

    # Tamper with archive
    with open(archive, "r+b") as f:
        f.seek(100)
        original_byte = f.read(1)
        tampered_byte = bytes([(original_byte[0] ^ 0xFF)])
        f.seek(100)
        f.write(tampered_byte)

    # Verification must fail with non-zero exit code
    verify_res = subprocess.run(
        [str(ctl_exe), "verify", "--file", str(archive)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert verify_res.returncode != 0
    assert "FAIL" in verify_res.stdout or "FAIL" in verify_res.stderr


def test_fieldkit_ctl_support_bundle_and_redaction(tmp_path: Path) -> None:
    """Verify support-bundle gathers diagnostics and redacts sensitive credentials."""
    ctl_exe = _ensure_ctl_binary()

    support_dir = tmp_path / "support"
    res = subprocess.run(
        [str(ctl_exe), "support-bundle", "--out", str(support_dir)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Diagnostic support bundle collected" in res.stdout

    tar_files = list(support_dir.glob("fieldkit-support-*.tar.gz"))
    assert len(tar_files) == 1
    support_tar = tar_files[0]

    with tarfile.open(support_tar, "r:gz") as tar:
        names = tar.getnames()
        assert "diagnostics.txt" in names
        assert "env_redacted.txt" in names
        assert "service_status.txt" in names

        # Read env_redacted.txt and check no unredacted secret leak
        env_member = tar.extractfile("env_redacted.txt")
        assert env_member is not None
        env_content = env_member.read().decode("utf-8", errors="ignore")
        for line in env_content.splitlines():
            if any(k in line.upper() for k in ("KEY", "SECRET", "PASSWORD", "TOKEN")):
                assert "[REDACTED]" in line


def test_fieldkit_ctl_status_probe_json() -> None:
    """Verify status probe outputs structured reachability results for all 13 microservices."""
    ctl_exe = _ensure_ctl_binary()

    res = subprocess.run(
        [str(ctl_exe), "status", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    statuses = json.loads(res.stdout)
    assert isinstance(statuses, list)
    assert len(statuses) == 13

    service_names = {s["name"] for s in statuses}
    assert "postgres" in service_names
    assert "minio" in service_names
    assert "redis" in service_names
    assert "clickhouse" in service_names
    assert "redpanda" in service_names
    assert "workflow-engine" in service_names
    assert "foundry" in service_names
    assert "assistant" in service_names
    assert "copilot" in service_names
    assert "docai" in service_names
    assert "vision-edge" in service_names
    assert "tracehub" in service_names
    assert "console" in service_names
