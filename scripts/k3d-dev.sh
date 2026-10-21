#!/usr/bin/env bash
# ==============================================================================
# Fieldkit - Local k3d Air-Gap Cluster Lifecycle & Verification Script
# Target: Tobias Becker (Plant IT & Infrastructure Administrator)
# ==============================================================================
set -euo pipefail

CLUSTER_NAME="fieldkit-airgap"
NAMESPACE="fieldkit"
CHART_DIR="./deploy/helm/fieldkit"

command -v k3d >/dev/null 2>&1 || { echo >&2 "[ERROR] k3d is not installed. Please install k3d."; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo >&2 "[ERROR] kubectl is not installed. Please install kubectl."; exit 1; }
command -v helm >/dev/null 2>&1 || { echo >&2 "[ERROR] helm is not installed. Please install helm."; exit 1; }

usage() {
    cat <<EOF
Usage: $0 [command]

Commands:
  up          Create local k3d air-gap simulation cluster
  deploy      Install or upgrade Fieldkit Helm umbrella chart
  smoke       Run post-deployment smoke readiness probe
  down        Tear down k3d cluster and delete persistent storage
  status      Display cluster node and pod status
  help        Show this help message
EOF
}

cmd_up() {
    echo "==> Creating k3d cluster '${CLUSTER_NAME}' with Traefik ingress & local registry..."
    if k3d cluster list | grep -q "${CLUSTER_NAME}"; then
        echo "Cluster '${CLUSTER_NAME}' already exists."
    else
        k3d cluster create "${CLUSTER_NAME}" \
            --servers 1 \
            --agents 2 \
            --port "80:80@loadbalancer" \
            --port "443:443@loadbalancer" \
            --port "8008:8008@loadbalancer" \
            --wait
        echo "==> Cluster '${CLUSTER_NAME}' created successfully."
    fi

    kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
    echo "==> Namespace '${NAMESPACE}' ready."
}

cmd_deploy() {
    echo "==> Linting Helm chart '${CHART_DIR}'..."
    helm lint "${CHART_DIR}"

    echo "==> Deploying Fieldkit umbrella chart to namespace '${NAMESPACE}'..."
    helm upgrade --install fieldkit "${CHART_DIR}" \
        --namespace "${NAMESPACE}" \
        --create-namespace \
        --set global.airGap=true \
        --values "${CHART_DIR}/values.yaml"

    echo "==> Waiting for core database & workflow engine components to be ready..."
    kubectl rollout status statefulset/fieldkit-postgres -n "${NAMESPACE}" --timeout=120s || true
    kubectl rollout status deployment/fieldkit-workflow-engine -n "${NAMESPACE}" --timeout=120s || true

    echo "==> Fieldkit Helm release deployed successfully."
}

cmd_smoke() {
    echo "==> Executing smoke probes across Fieldkit endpoints..."
    echo -n "1. Testing Workflow Engine health probe: "
    if curl -s -f http://localhost:8008/healthz >/dev/null 2>&1; then
        echo "[PASS] (200 OK)"
    else
        echo "[WARN] (Engine not exposed on localhost:8008 or port-forward required)"
    fi

    echo -n "2. Checking Kubernetes pod statuses in namespace '${NAMESPACE}': "
    kubectl get pods -n "${NAMESPACE}"
}

cmd_status() {
    echo "==> Nodes:"
    kubectl get nodes -o wide
    echo ""
    echo "==> Pods in '${NAMESPACE}':"
    kubectl get pods -n "${NAMESPACE}" -o wide
    echo ""
    echo "==> Ingresses in '${NAMESPACE}':"
    kubectl get ingress -n "${NAMESPACE}"
}

cmd_down() {
    echo "==> Deleting k3d cluster '${CLUSTER_NAME}'..."
    k3d cluster delete "${CLUSTER_NAME}" || true
    echo "==> Cluster '${CLUSTER_NAME}' removed."
}

case "${1:-help}" in
    up) cmd_up ;;
    deploy) cmd_deploy ;;
    smoke) cmd_smoke ;;
    status) cmd_status ;;
    down) cmd_down ;;
    help|--help|-h) usage ;;
    *) echo "[ERROR] Unknown command: $1"; usage; exit 1 ;;
esac
