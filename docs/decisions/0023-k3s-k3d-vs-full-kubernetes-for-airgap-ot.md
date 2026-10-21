# ADR 0023: Embedded Lightweight k3s / k3d vs Full-Blown Enterprise Kubernetes for Industrial Air-Gapped OT Plants

- **Status**: Accepted
- **Date**: 2026-10-21
- **Author**: engrmaziz & Tobias Becker

## Context
Deploying multi-service AI platforms (incorporating PostgreSQL, MinIO, Redis, ClickHouse, Redpanda, Next.js, and Python FastAPI microservices) across industrial edge manufacturing plants requires orchestrating containerized workloads reliably without Internet connectivity.
Standard Kubernetes distributions (e.g. OpenShift, standard upstream k8s, or cloud-managed clusters) pose severe operational hurdles in manufacturing plants:
1. **Host Footprint & Over-Provisioning**: Upstream Kubernetes requires dedicated etcd clusters and control plane nodes consuming 8-16 GB of RAM solely for control plane operations.
2. **Offline Installation Fragility**: Setting up standard Kubernetes air-gapped involves complex bootstrap certificates, dynamic DNS lookups, and fragile etcd cluster synchronization.
3. **Operational Maintenance Overhead**: Plant IT administrators like Tobias Becker operate single-server or two-node industrial IPC racks on the factory floor and cannot dedicate hours to Kubernetes cluster debugging.

## Decision
We adopted **k3s (packaged for local developer testing via k3d) as the official container orchestration substrate for Fieldkit in air-gapped production plants**:
1. **Single-Binary Control Plane**:
   - k3s encapsulates the API server, controller manager, scheduler, containerd, Flannel CNI, and CoreDNS into a single binary (< 100 MB).
   - Uses SQLite or embedded etcd, requiring < 512 MB memory for the entire control plane.
2. **Native Traefik Ingress Gateway**:
   - Ships with Traefik ingress pre-integrated, enabling immediate local domain routing (`console.localtest.me`, `api.localtest.me`) with zero external DNS servers required.
3. **Local-Path Storage Provisioner**:
   - Out-of-the-box `local-path` storage class dynamically provisions host persistent volumes without requiring external SAN/NAS storage arrays.
4. **Helm Umbrella Chart Architecture**:
   - The entire platform is deployed via a unified umbrella chart (`deploy/helm/fieldkit`) supporting one-command upgrades, rollbacks, and pre-upgrade schema hooks.

## Consequences
- **Positive**:
  - Control plane memory overhead reduced by > 90% compared to standard Kubernetes.
  - Reproducible single-command setup in air-gapped networks via `fieldkit-ctl` or `scripts/k3d-dev.sh`.
  - Full Kubernetes API compatibility (StatefulSets, PVCs, Deployments, Services, NetworkPolicies, Ingress).
- **Negative**:
  - Advanced enterprise multi-cluster federation or external cloud CSI drivers are not supported out of the box (unnecessary for air-gapped OT plants).
