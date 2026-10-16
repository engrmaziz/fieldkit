"""Unit tests for LandingZone idempotency."""

from pathlib import Path

from fieldkit_ingest.landing import LandingZone


def test_landing_idempotency_skips_duplicate(tmp_path: Path) -> None:
    landing = LandingZone(local_landing_dir=tmp_path / "landing")
    raw_payload = b"vendor_id;name\nERP-001;Halden Hydraulik\n"

    # First landing
    obj_key_1, sha_1, skipped_1 = landing.land("erp", "run_1", "test.csv", raw_payload)
    assert not skipped_1
    assert obj_key_1 == "landing/erp/run_1/test.csv"
    assert sha_1 != ""

    # Second landing with same payload in a new run
    obj_key_2, sha_2, skipped_2 = landing.land("erp", "run_2", "test.csv", raw_payload)
    assert skipped_2  # Must be skipped
    assert sha_2 == sha_1
    assert obj_key_2 == obj_key_1  # References existing landed object
