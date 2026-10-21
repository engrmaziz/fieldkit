"""Tests for Project 8 Milestone 6: Disaster Recovery and Upgrade Drills."""

from __future__ import annotations

from pathlib import Path

from scripts.drill_dr import run_dr_drill


def test_automated_disaster_recovery_drill(tmp_path: Path) -> None:
    """Verify disaster recovery drill executes within RTO < 60s and RPO = 0."""
    result = run_dr_drill(temp_dir=tmp_path / "dr_test")

    assert result.drill_status == "SUCCESS"
    assert result.rto_sla_met is True, f"RTO took {result.rto_seconds}s (target < 60s)"
    assert result.rpo_sla_met is True
    assert result.rpo_loss_records == 0
    assert result.checksum_verified is True
