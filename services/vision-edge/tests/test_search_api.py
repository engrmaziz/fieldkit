"""Unit tests for Event Search, Natural Language Query Parsing, and Zone Management APIs."""

import httpx
import pytest
from fieldkit_vision.events import VisionEvent
from fieldkit_vision.main import app, recent_events
from fieldkit_vision.search import (
    EventFilter,
    build_clickhouse_query,
    parse_nl_query_to_filter,
)


def test_nl_query_parser() -> None:
    """Verify natural language queries parse into valid EventFilter models with UI chips."""
    # 1. Proximity + Press + Critical
    q1 = "Show critical forklift proximity alerts in the press zone"
    f1, chips1 = parse_nl_query_to_filter(q1)
    assert f1.camera_id == "cam1_press"
    assert f1.rule_type == "forklift_pedestrian_proximity"
    assert f1.severity == "CRITICAL"
    assert any("Press Bed" in c for c in chips1)
    assert any("Proximity" in c for c in chips1)

    # 2. Helmet + Logistics + Person ID
    q2 = "Missing helmet in logistics corridor for person_0002"
    f2, chips2 = parse_nl_query_to_filter(q2)
    assert f2.camera_id == "cam2_logistics"
    assert f2.rule_type == "zone_ppe_missing"
    assert f2.person_id == "person_0002"

    # 3. Perimeter boundary cross warning
    q3 = "Perimeter boundary cross warning"
    f3, chips3 = parse_nl_query_to_filter(q3)
    assert f3.camera_id == "cam4_perimeter"
    assert f3.rule_type == "line_cross"
    assert f3.severity == "WARNING"

    # 4. Unrestricted query
    q4 = "Show all recent activity"
    f4, chips4 = parse_nl_query_to_filter(q4)
    assert f4.camera_id is None
    assert f4.rule_type is None
    assert f4.severity is None
    assert len(chips4) >= 1


def test_build_clickhouse_query_parameterization() -> None:
    """Verify ClickHouse query generation enforces parameterization."""
    flt = EventFilter(
        camera_id="cam1_press",
        rule_type="zone_ppe_missing",
        severity="CRITICAL",
        limit=25,
    )
    sql, params = build_clickhouse_query(flt)
    assert "SELECT" in sql
    assert "FROM fieldkit_vision.events" in sql
    assert "camera_id = %(camera_id)s" in sql
    assert "rule_type = %(rule_type)s" in sql
    assert "severity = %(severity)s" in sql
    assert params["camera_id"] == "cam1_press"
    assert params["rule_type"] == "zone_ppe_missing"
    assert params["severity"] == "CRITICAL"
    assert params["limit"] == 25


@pytest.mark.asyncio
async def test_get_event_by_id_and_nl_search_endpoint() -> None:
    """Verify single event retrieval and POST /search/nl conversational search."""
    evt = VisionEvent(
        event_id="evt_test_search_123",
        camera_id="cam2_logistics",
        plant_id="DE-HAM",
        rule_id="rule_forklift_prox",
        rule_type="forklift_pedestrian_proximity",
        severity="CRITICAL",
        track_id=88,
        metadata={"confidence": 0.96},
        clip_uri="http://minio:9000/vision-clips/evt_test_search_123.mp4",
    )
    recent_events.appendleft(evt)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. GET /events/{event_id} (Found)
        resp = await client.get("/events/evt_test_search_123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_id"] == "evt_test_search_123"
        assert data["camera_id"] == "cam2_logistics"
        assert data["clip_uri"] == "http://minio:9000/vision-clips/evt_test_search_123.mp4"

        # 2. GET /events/{event_id} (Not Found)
        nf_resp = await client.get("/events/evt_non_existent")
        assert nf_resp.status_code == 404

        # 3. POST /search/nl
        nl_resp = await client.post(
            "/search/nl",
            json={"query": "Show critical forklift proximity incidents in logistics"},
        )
        assert nl_resp.status_code == 200
        nl_data = nl_resp.json()
        assert nl_data["parsed_filter"]["camera_id"] == "cam2_logistics"
        assert nl_data["parsed_filter"]["rule_type"] == "forklift_pedestrian_proximity"
        assert nl_data["parsed_filter"]["severity"] == "CRITICAL"
        assert len(nl_data["filter_chips"]) >= 2
        assert "events" in nl_data


@pytest.mark.asyncio
async def test_zone_management_endpoints() -> None:
    """Verify GET and POST /cameras/{camera_id}/zones."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /cameras/cam1_press/zones
        resp = await client.get("/cameras/cam1_press/zones")
        assert resp.status_code == 200
        zones = resp.json()
        assert isinstance(zones, list)

        # POST /cameras/cam1_press/zones
        update_payload = [
            {
                "id": "zone_test_new",
                "name": "New Safety Zone",
                "type": "danger_zone",
                "polygon": [[100, 100], [400, 100], [400, 400], [100, 400]],
            }
        ]
        post_resp = await client.post("/cameras/cam1_press/zones", json=update_payload)
        assert post_resp.status_code == 200
        res = post_resp.json()
        assert res["camera_id"] == "cam1_press"
        assert res["zone_count"] >= 1


@pytest.mark.asyncio
async def test_parameterized_events_filter() -> None:
    """Verify parameterized GET /events endpoint filters by camera, rule, timestamp, person_id."""
    evt1 = VisionEvent(
        event_id="evt_param_1",
        camera_id="cam1_press",
        plant_id="DE-HAM",
        rule_id="rule_ppe",
        rule_type="zone_ppe_missing",
        severity="WARNING",
        track_id=101,
        timestamp=1000.0,
        metadata={"confidence": 0.92, "global_person_id": "person_0001"},
    )
    evt2 = VisionEvent(
        event_id="evt_param_2",
        camera_id="cam2_logistics",
        plant_id="DE-HAM",
        rule_id="rule_forklift",
        rule_type="forklift_pedestrian_proximity",
        severity="CRITICAL",
        track_id=102,
        timestamp=2000.0,
        metadata={"confidence": 0.98, "global_person_id": "person_0002"},
    )
    recent_events.appendleft(evt1)
    recent_events.appendleft(evt2)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Filter by camera
        r1 = await client.get("/events?camera=cam1_press")
        assert r1.status_code == 200
        assert any(e["event_id"] == "evt_param_1" for e in r1.json())
        assert not any(e["event_id"] == "evt_param_2" for e in r1.json())

        # Filter by rule and severity
        r2 = await client.get("/events?rule=forklift_pedestrian_proximity&severity=CRITICAL")
        assert r2.status_code == 200
        assert any(e["event_id"] == "evt_param_2" for e in r2.json())

        # Filter by person_id
        r3 = await client.get("/events?person_id=person_0001")
        assert r3.status_code == 200
        assert any(e["event_id"] == "evt_param_1" for e in r3.json())

        # Filter by time window
        r4 = await client.get("/events?from=1500&to=2500")
        assert r4.status_code == 200
        assert any(e["event_id"] == "evt_param_2" for e in r4.json())
        assert not any(e["event_id"] == "evt_param_1" for e in r4.json())
