"""Tests for Project 8 Milestone 6: Disaster Recovery and Upgrade Drills."""

from __future__ import annotations

from pathlib import Path

from scripts.drill_dr import (
    run_dr_drill,
    run_failed_upgrade_rollback_drill,
    run_upgrade_drill,
)

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_automated_disaster_recovery_drill(tmp_path: Path) -> None:
    """Verify disaster recovery drill executes within RTO < 60s and RPO = 0."""
    result = run_dr_drill(temp_dir=tmp_path / "dr_test")

    assert result.drill_status == "SUCCESS"
    assert result.rto_sla_met is True, f"RTO took {result.rto_seconds}s (target < 60s)"
    assert result.rpo_sla_met is True
    assert result.rpo_loss_records == 0
    assert result.checksum_verified is True


def test_automated_upgrade_drill_under_traffic() -> None:
    """Verify zero-downtime rolling upgrade maintains request error rate < 0.1%."""
    result = run_upgrade_drill(total_requests=300, max_workers=8)

    assert result.drill_status == "SUCCESS"
    assert result.sla_met is True, f"Error rate was {result.error_rate_pct:.3f}% (target < 0.1%)"
    assert result.failed_requests == 0
    assert result.error_rate_pct == 0.0


def test_automated_failed_upgrade_rollback_drill(tmp_path: Path) -> None:
    """Verify failed database migration triggers atomic rollback and leaves data intact."""
    result = run_failed_upgrade_rollback_drill(temp_dir=tmp_path / "rollback_test")

    assert result.drill_status == "SUCCESS"
    assert result.rollback_triggered is True
    assert result.data_intact is True
    assert "syntax error" in result.fault_injected


def test_runbook_drills_alerts_and_procedures_coverage() -> None:
    """Verify platform runbook documents 10 alarms with exact remediation, secrets, and GPU procedures."""
    runbook_path = ROOT_DIR / "docs" / "runbooks" / "drills.md"
    assert runbook_path.exists()

    content = runbook_path.read_text(encoding="utf-8")
    assert "Secret Rotation Procedure" in content
    assert "GPU Node Provisioning" in content
    assert "10 Common Industrial Alarms" in content

    # Check key alert definitions exist
    for alarm in [
        "DiskStorageCritical80",
        "ClickHouseMemoryPressure",
        "PostgresReplicationLag",
        "WorkerLeaseExpired",
        "OllamaVRAMSpillover",
        "KeycloakCertificateExpiring",
        "RedpandaUnderReplicatedPartitions",
        "WorkflowSuspendedApprovalTimeout",
        "NetworkPolicyEgressBlocked",
        "ModelInferenceLatencySLAExceeded",
    ]:
        assert alarm in content, f"Alarm {alarm} missing from runbook"
