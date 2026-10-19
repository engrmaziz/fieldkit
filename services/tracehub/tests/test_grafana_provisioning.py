"""Comprehensive tests for Grafana datasources, dashboard provisioning, and JSON schemas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
GRAFANA_DIR = ROOT_DIR / "deploy" / "grafana"
COMPOSE_FILE = ROOT_DIR / "deploy" / "compose" / "docker-compose.yml"


def test_provisioning_datasources_valid() -> None:
    ds_file = GRAFANA_DIR / "provisioning" / "datasources" / "datasources.yaml"
    assert ds_file.exists(), f"Datasource provisioning file missing at {ds_file}"

    data = yaml.safe_load(ds_file.read_text(encoding="utf-8"))
    assert data.get("apiVersion") == 1
    datasources = data.get("datasources", [])
    assert len(datasources) >= 1

    ch_ds = next((ds for ds in datasources if ds.get("name") == "ClickHouse"), None)
    assert ch_ds is not None, "ClickHouse datasource not found in datasources.yaml"
    assert ch_ds.get("type") == "grafana-clickhouse-datasource"
    assert ch_ds.get("isDefault") is True
    json_data = ch_ds.get("jsonData", {})
    assert json_data.get("defaultDatabase") == "fieldkit_tracehub"
    assert json_data.get("server") == "clickhouse"
    assert json_data.get("port") == 8123


def test_provisioning_dashboards_valid() -> None:
    db_file = GRAFANA_DIR / "provisioning" / "dashboards" / "dashboards.yaml"
    assert db_file.exists(), f"Dashboard provisioning file missing at {db_file}"

    data = yaml.safe_load(db_file.read_text(encoding="utf-8"))
    assert data.get("apiVersion") == 1
    providers = data.get("providers", [])
    assert len(providers) >= 1

    provider = providers[0]
    assert provider.get("type") == "file"
    options = provider.get("options", {})
    assert options.get("path") == "/var/lib/grafana/dashboards"


def test_dashboard_json_files_exist_and_valid() -> None:
    dashboards_dir = GRAFANA_DIR / "dashboards"
    assert dashboards_dir.exists(), f"Dashboards directory missing at {dashboards_dir}"

    expected_dashboards = {
        "llm_overview.json": "fieldkit-llm-overview",
        "service_slos.json": "fieldkit-service-slos",
        "vision_health.json": "fieldkit-vision-health",
        "inspection_drift.json": "fieldkit-inspection-drift",
    }

    seen_uids: set[str] = set()

    for filename, expected_uid in expected_dashboards.items():
        fpath = dashboards_dir / filename
        assert fpath.exists(), f"Required dashboard {filename} missing"

        content = fpath.read_text(encoding="utf-8")
        parsed: dict[str, Any] = json.loads(content)

        # Structure checks
        assert parsed.get("uid") == expected_uid
        assert parsed.get("title") is not None
        assert parsed.get("schemaVersion") is not None
        assert "fieldkit" in parsed.get("tags", [])

        # Unique UIDs across dashboards
        uid = str(parsed.get("uid"))
        assert uid not in seen_uids, f"Duplicate dashboard UID: {uid}"
        seen_uids.add(uid)

        # Panel validation
        panels = parsed.get("panels", [])
        assert len(panels) >= 5, f"Dashboard {filename} must have at least 5 panels"

        panel_ids: set[int] = set()
        data_panels_count = 0

        for p in panels:
            p_id = p.get("id")
            assert p_id is not None
            assert p_id not in panel_ids, f"Duplicate panel id {p_id} in {filename}"
            panel_ids.add(p_id)

            # Check data panel targets
            if p.get("type") not in ("row", "text"):
                data_panels_count += 1
                targets = p.get("targets", [])
                assert len(targets) >= 1, f"Data panel {p.get('title')} in {filename} has no targets"
                for target in targets:
                    assert "rawSql" in target or "expr" in target

        assert data_panels_count >= 4, f"Dashboard {filename} should have >= 4 data panels"


def test_docker_compose_grafana_integration() -> None:
    assert COMPOSE_FILE.exists(), "docker-compose.yml not found"
    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")
    data = yaml.safe_load(compose_text)

    services = data.get("services", {})
    assert "grafana" in services, "grafana service missing from compose"
    grafana = services["grafana"]

    # Plugin check
    env = grafana.get("environment", [])
    has_clickhouse_plugin = any("grafana-clickhouse-datasource" in str(e) for e in env)
    assert has_clickhouse_plugin, "GF_INSTALL_PLUGINS=grafana-clickhouse-datasource missing in compose"

    # Volume mounts check
    volumes = grafana.get("volumes", [])
    has_prov = any("provisioning" in str(v) for v in volumes)
    has_dash = any("dashboards" in str(v) for v in volumes)
    assert has_prov, "Provisioning volume mount missing in compose"
    assert has_dash, "Dashboards volume mount missing in compose"
