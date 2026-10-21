"""Integration tests for Project 8: Air-Gapped Deployment Kit & Go Workflow Engine."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backup import run_backup
from scripts.restore import run_restore
from scripts.smoke_readiness import run_smoke_test


def test_go_workflow_engine_tests_pass() -> None:
    """Execute Go unit and integration test suite."""
    res = subprocess.run(
        ["go", "test", "./...", "-v"],
        cwd="services/workflow-engine",
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"Go test suite failed:\n{res.stdout}\n{res.stderr}"
    assert "PASS" in res.stdout
    assert "TestOrchestrator_InitialScheduling" in res.stdout
    assert "TestOrchestrator_HumanApprovalGate" in res.stdout
    assert "TestOrchestrator_SagaCompensationOnFailure" in res.stdout
    assert "TestRouter_RegisterAndRunWorkflow" in res.stdout


def test_shipped_workflows_exist_and_non_empty() -> None:
    """Verify all 5 standard production workflows exist and are non-empty."""
    workflows = [
        "workflows/nightly-ingest.yaml",
        "workflows/retrain-promote.yaml",
        "workflows/weekly-insights.yaml",
        "workflows/nightly-evals.yaml",
        "workflows/daily-backup.yaml",
    ]
    for w in workflows:
        p = Path(w)
        assert p.exists(), f"Workflow file {w} missing"
        content = p.read_text(encoding="utf-8")
        assert len(content) > 50, f"Workflow file {w} too short"
        assert "name:" in content
        assert "version:" in content
        assert "steps:" in content


def test_disaster_recovery_backup_and_restore_cycle(tmp_path: Path) -> None:
    """Test full backup and restore cycle with manifest validation."""
    backup_dest = run_backup(tmp_path, dry_run=False)
    assert backup_dest.exists()
    assert (backup_dest / "manifest.json").exists()
    assert (backup_dest / "postgres_fieldkit.dump").exists()
    assert (backup_dest / "minio_objects.tar.gz").exists()

    # Dry-run restore
    dry_ok = run_restore(backup_dest, dry_run=True, confirm=False)
    assert dry_ok is True

    # Active restore
    restore_ok = run_restore(backup_dest, dry_run=False, confirm=True)
    assert restore_ok is True


def test_smoke_readiness_probe_runs_cleanly() -> None:
    """Verify readiness smoke test runs and returns success code."""
    code = run_smoke_test()
    assert code == 0
