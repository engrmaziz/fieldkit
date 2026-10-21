"""Tests for Project 8 Milestone 4: Helm Umbrella Chart and Manifest Validation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

CHART_DIR = Path(__file__).parent.parent / "deploy" / "helm" / "fieldkit"


def test_helm_chart_yaml_structure() -> None:
    """Verify Chart.yaml has valid metadata and versioning."""
    chart_file = CHART_DIR / "Chart.yaml"
    assert chart_file.exists(), "Chart.yaml must exist"

    with open(chart_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["name"] == "fieldkit"
    assert data["apiVersion"] == "v2"
    assert data["version"] == "1.0.0"
    assert data["appVersion"] == "1.0.0"
    assert "air-gap" in data["keywords"]


def test_helm_lint_passes_cleanly() -> None:
    """Verify helm lint reports 0 failures on the umbrella chart."""
    result = subprocess.run(
        ["helm", "lint", str(CHART_DIR)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"helm lint failed:\n{result.stderr}\n{result.stdout}"
    assert "0 chart(s) failed" in result.stdout


def test_helm_template_renders_all_workloads() -> None:
    """Verify helm template generates all required statefulsets, deployments, ingress, and hooks."""
    result = subprocess.run(
        ["helm", "template", "fieldkit", str(CHART_DIR)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"helm template failed:\n{result.stderr}"
    manifests_text = result.stdout
    assert len(manifests_text) > 5000, "Rendered manifests should be comprehensive"

    docs = list(yaml.safe_load_all(manifests_text))
    doc_kinds = [(d.get("kind"), d.get("metadata", {}).get("name")) for d in docs if d]

    # Verify StatefulSets
    stateful_names = [name for kind, name in doc_kinds if kind == "StatefulSet"]
    assert "fieldkit-postgres" in stateful_names
    assert "fieldkit-minio" in stateful_names
    assert "fieldkit-redis" in stateful_names
    assert "fieldkit-clickhouse" in stateful_names
    assert "fieldkit-redpanda" in stateful_names

    # Verify Workflow Engine Deployment
    deployment_names = [name for kind, name in doc_kinds if kind == "Deployment"]
    assert "fieldkit-workflow-engine" in deployment_names
    assert "fieldkit-foundry" in deployment_names
    assert "fieldkit-assistant" in deployment_names
    assert "fieldkit-copilot" in deployment_names
    assert "fieldkit-docai" in deployment_names
    assert "fieldkit-vision-edge" in deployment_names
    assert "fieldkit-tracehub" in deployment_names
    assert "fieldkit-console" in deployment_names

    # Verify Ingress and Hostnames
    ingresses = [d for d in docs if d and d.get("kind") == "Ingress"]
    assert len(ingresses) >= 1
    ingress = ingresses[0]
    rules = ingress.get("spec", {}).get("rules", [])
    hosts = [r.get("host") for r in rules]
    assert "console.localtest.me" in hosts
    assert "api.localtest.me" in hosts

    # Verify NetworkPolicy
    netpols = [d for d in docs if d and d.get("kind") == "NetworkPolicy"]
    assert len(netpols) >= 1
    assert netpols[0]["metadata"]["name"] == "fieldkit-ot-segmentation"

    # Verify Pre-upgrade Hook Job
    jobs = [d for d in docs if d and d.get("kind") == "Job"]
    assert len(jobs) >= 1
    hook_job = jobs[0]
    annotations = hook_job.get("metadata", {}).get("annotations", {})
    assert "helm.sh/hook" in annotations
    assert "pre-upgrade" in annotations["helm.sh/hook"]
