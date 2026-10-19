"""Comprehensive tests for Streaming Anomaly Detectors, Deterministic RCA, and Multi-Channel Alerting."""

from __future__ import annotations

import pytest
from fieldkit_tracehub.anomaly.alerting import AlertManager
from fieldkit_tracehub.anomaly.detectors import (
    CUSUMDetector,
    ErrorRateBurstDetector,
    EWMABandDetector,
    RobustZScoreDetector,
    StreamingAnomalyEngine,
)
from fieldkit_tracehub.anomaly.rca import (
    RootCauseAnalyzer,
    extract_numbers_from_dict,
    extract_numbers_from_text,
    validate_rca_sentence,
)
from fieldkit_tracehub.main import app
from fieldkit_tracehub.schemas import AlertCreate
from starlette.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# =========================================================================
# Detector Tests
# =========================================================================

def test_robust_z_score_detector() -> None:
    detector = RobustZScoreDetector(z_threshold=4.0, consecutive_points=3, min_history=4)

    # Warmup phase: no alert
    for _ in range(3):
        is_anom, _, _ = detector.observe(100.0)
        assert not is_anom

    # Stable points
    for _ in range(10):
        is_anom, _, _ = detector.observe(100.0)
        assert not is_anom

    # Anomaly points: requires 3 consecutive breaches
    is_anom1, _, _ = detector.observe(1500.0)
    assert not is_anom1
    is_anom2, _, _ = detector.observe(1500.0)
    assert not is_anom2
    is_anom3, z, _ = detector.observe(1500.0)
    assert is_anom3
    assert z >= 4.0


def test_ewma_band_detector() -> None:
    detector = EWMABandDetector(alpha=0.3, band_multiplier=3.0, min_history=3)

    # Stable baseline
    for _ in range(10):
        is_anom, _, _ = detector.observe(200.0)
        assert not is_anom

    # Sudden sharp breach
    is_anom, val, bound = detector.observe(1200.0)
    assert is_anom
    assert val == 1200.0
    assert val > bound


def test_cusum_detector() -> None:
    detector = CUSUMDetector(slack_k=0.5, threshold_h=4.0, min_history=4)

    # Stable baseline
    for _ in range(5):
        is_anom, _, _ = detector.observe(50.0)
        assert not is_anom

    # Persistent gradual shift upwards
    res = False
    for _ in range(15):
        is_anom, _, _ = detector.observe(85.0)
        if is_anom:
            res = True
            break
    assert res is True


def test_error_rate_burst_detector() -> None:
    detector = ErrorRateBurstDetector(min_error_rate=0.05, min_error_count=10)

    # Low error rate: no trigger
    is_burst, _, _ = detector.observe(error_count=2, total_count=100)
    assert not is_burst

    # High error rate but low count: no trigger
    is_burst, _, _ = detector.observe(error_count=2, total_count=5)
    assert not is_burst

    # High rate and high count: triggers
    is_burst, rate, _ = detector.observe(error_count=15, total_count=100)
    assert is_burst
    assert rate == 0.15


def test_streaming_anomaly_engine() -> None:
    engine = StreamingAnomalyEngine(warmup_points=3)
    series = "assistant-api:qa:qwen7b"

    # Baseline ingestion
    for _ in range(4):
        anoms = engine.ingest_metric(series, latency_p95=100.0, error_count=0, total_count=100)
        assert len(anoms) == 0

    # Ingest sharp error burst
    bursts = engine.ingest_metric(series, latency_p95=100.0, error_count=20, total_count=100)
    assert len(bursts) >= 1
    assert any(a.detector == "error_burst" for a in bursts)


# =========================================================================
# RCA and Zero-Hallucination Validator Tests
# =========================================================================

def test_extract_numbers() -> None:
    text = "Model qwen2.5:7b has 87.5% share and 1500 ms latency with 3 dropped traces."
    nums = extract_numbers_from_text(text)
    assert 87.5 in nums
    assert 1500.0 in nums
    assert 3.0 in nums

    evidence = {
        "metric": "latency",
        "nested": {"delta": 450.2, "trace_count": 5},
        "tags": ["batch-10"],
    }
    extracted = extract_numbers_from_dict(evidence)
    assert 450.2 in extracted
    assert 5.0 in extracted
    assert 10.0 in extracted


def test_validate_rca_sentence_drops_hallucinations() -> None:
    allowed = {100.0, 500.0, 85.0}

    # Sentence with strictly allowed numbers passes
    valid_sentence = "Latency climbed from 100 to 500 ms, representing 85% of traffic."
    assert validate_rca_sentence(valid_sentence, allowed) is True

    # Sentence with fabricated/hallucinated number fails
    hallucinated_sentence = "Latency climbed from 100 to 999 ms, representing 85% of traffic."
    assert validate_rca_sentence(hallucinated_sentence, allowed) is False


def test_root_cause_analyzer_attribution() -> None:
    analyzer = RootCauseAnalyzer()

    baseline = [
        {"prompt_version": "1.0", "model": "qwen:7b", "plant": "DE-STR", "host": "h1", "task": "qa", "value": 100.0}
        for _ in range(10)
    ]
    # Anomalous window where plant DE-HAM accounts for all elevated values
    anomalous = [
        {"prompt_version": "1.0", "model": "qwen:7b", "plant": "DE-HAM", "host": "h1", "task": "qa", "value": 800.0, "trace_id": "trc-01"}
        for _ in range(7)
    ] + [
        {"prompt_version": "1.0", "model": "qwen:7b", "plant": "DE-STR", "host": "h1", "task": "qa", "value": 100.0, "trace_id": "trc-02"}
        for _ in range(3)
    ]

    rca = analyzer.compute_attribution(
        series="test:qa",
        metric="latency_p95",
        baseline_samples=baseline,
        anomalous_samples=anomalous,
    )

    assert len(rca.top_dimensions) >= 1
    assert rca.top_dimensions[0].dimension == "plant"
    assert rca.top_dimensions[0].value == "DE-HAM"
    assert rca.top_dimensions[0].contribution_pct > 50.0
    assert rca.example_trace_ids == ["trc-01", "trc-02"]

    # Enforce strictly 0 dropped hallucinated sentences because all numbers came from evidence
    assert rca.dropped_hallucinations_count == 0
    assert rca.validated_numbers_count > 0


# =========================================================================
# AlertManager & Notification Tests
# =========================================================================

def test_alert_manager_deduplication_and_cooldown() -> None:
    manager = AlertManager()

    # Initial alert
    a1 = manager.dispatch_anomaly(
        series="assistant-api:qa:qwen7b",
        metric="latency_p95",
        detector="robust_z",
        current_value=1250.0,
        threshold=800.0,
        severity="high",
    )
    assert a1 is not None
    assert a1.status == "active"
    assert a1.current_value == 1250.0

    # Same series and detector within grouping window -> groups into existing alert
    a2 = manager.dispatch_anomaly(
        series="assistant-api:qa:qwen7b",
        metric="latency_p95",
        detector="robust_z",
        current_value=1300.0,
        threshold=800.0,
        severity="high",
    )
    assert a2 is not None
    assert a2.alert_id == a1.alert_id
    assert a2.current_value == 1300.0

    # Resolve alert
    res = manager.resolve_alert(a1.alert_id)
    assert res is not None
    assert res.status == "resolved"
    assert res.resolved_at is not None

    # Cooldown suppresses re-alert immediately after resolution
    suppressed = manager.dispatch_anomaly(
        series="assistant-api:qa:qwen7b",
        metric="latency_p95",
        detector="robust_z",
        current_value=1350.0,
        threshold=800.0,
        severity="high",
    )
    assert suppressed is None


# =========================================================================
# FastAPI Endpoints Tests
# =========================================================================

def test_api_alerts_lifecycle(client: TestClient) -> None:
    # 1. List pre-seeded alerts
    resp = client.get("/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data
    assert data["total_active"] >= 1
    assert data["total_resolved"] >= 1

    # 2. Ingest external alert (e.g. from inspection / copilot)
    payload = AlertCreate(
        source="edge_inspection",
        series="defect-inspect:surface_defect:yolo11",
        service="defect-inspect",
        message="Camera RTSP frame drop exceeded edge threshold",
        severity="high",
    )
    post_resp = client.post("/alerts", json=payload.model_dump())
    assert post_resp.status_code == 200
    created = post_resp.json()
    alert_id = created["alert_id"]
    assert created["detector"] == "edge_inspection"
    assert created["status"] == "active"

    # 3. Get alert by ID
    get_resp = client.get(f"/alerts/{alert_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["alert_id"] == alert_id

    # 4. Resolve alert
    res_resp = client.post(f"/alerts/{alert_id}/resolve")
    assert res_resp.status_code == 200
    resolved = res_resp.json()
    assert resolved["status"] == "resolved"

    # 5. Verify active count decremented
    list_active = client.get("/alerts?status=active").json()
    assert not any(a["alert_id"] == alert_id for a in list_active["alerts"])


def test_api_scan_simulation(client: TestClient) -> None:
    resp = client.post("/alerts/scan/simulate?latency_p95=2200.0&error_count=15")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["detector"] == "error_burst"
