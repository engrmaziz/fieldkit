# ADR 0025: Docker Compose vs. Helm on k3s Support Matrix for Industrial Edge Deployments

- **Status**: Accepted
- **Date**: 2026-10-21
- **Author**: engrmaziz & Tobias Becker

## Context
Fieldkit is forward-deployed across diverse manufacturing topologies ranging from small fabrication cells with a single industrial PC to large multi-building automotive facilities.
Plant IT administrators require a clear, documented deployment tiering strategy that balances simplicity against automated orchestration and rolling zero-downtime upgrades.

We must decide the official support matrix and boundary conditions between **Docker Compose (P8a)** and **Helm on k3s (P8b)**.

## Decision
We established a strict **two-tier support matrix**:

| Dimension | Tier 1: Docker Compose (P8a) | Tier 2: Helm on k3s (P8b) [Recommended] |
| :--- | :--- | :--- |
| **Target Plant Topology** | Pilot cells, single-server PoCs ($< 50$ devices) | Production facilities, multi-camera OT plants ($> 50$ devices) |
| **Host Hardware Minimum** | 4 Cores, 16 GB RAM, single SSD | 8+ Cores, 32 GB RAM, dual SSD / NVMe |
| **Control Plane Overhead** | **0 MB** (Direct Docker Engine) | **~500 MB** (Embedded k3s control plane + Traefik) |
| **Ingress & Networking** | Fixed port host bindings (`:8001`-`:8008`, `:3000`) | Dynamic Traefik Ingress with hostnames (`*.localtest.me`) |
| **Security Segmentation** | Docker network isolation (`fieldkit-network`) | Strict Kubernetes NetworkPolicies (zero egress, intra-namespace) |
| **Upgrade Strategy** | `docker compose pull && docker compose up -d` (brief restart pause) | Rolling update (`maxUnavailable: 0`), zero dropped requests, pre-upgrade Alembic migration hook |
| **Disaster Recovery** | Point-in-time PostgreSQL custom dump + MinIO tarball | Automated PVC volume snapshots + Helm release rollback |
| **Human Governance** | CLI / scripts trigger | `fieldkit-ctl` with cryptographic Cosign bundle verification |

### Lifecycle Rules:
1. **Developer Workstations & Initial Plant PoCs**:
   - Begin with Docker Compose profiles (`make up P=foundry`, `make up P=inspect`). Fast bootstrap with minimal overhead.
2. **Production Air-Gapped Plants (`DE-HAM-OT`)**:
   - Deliver via cryptographically signed `fieldkit-<version>-airgap.tar.gz` bundle installed using `fieldkit-ctl install`.
   - Run on embedded single-node k3s with the official Fieldkit umbrella chart (`deploy/helm/fieldkit`).
3. **Rollback Guarantee**:
   - If a production upgrade fails health gates, Helm automatically aborts and rolls back (`--atomic`) to protect production plant operations.

## Consequences
- **Positive**:
  - Eliminates "Kubernetes everywhere" complexity for small plant pilots while providing enterprise zero-downtime rolling updates for production plants.
  - Consistent artifact structure: both profiles share identical environment variables, volume mount layouts, and database schemas.
- **Negative**:
  - Docker Compose does not support zero-downtime rolling updates without external proxy orchestration.
