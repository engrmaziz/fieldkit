# ADR 0024: Cryptographically Signed Offline Tarball Bundles vs Private Container Registry Infrastructure for Air-Gap Deployments

- **Status**: Accepted
- **Date**: 2026-10-21
- **Author**: engrmaziz & Tobias Becker

## Context
Delivering software updates to air-gapped industrial manufacturing plants requires transferring container images, Helm charts, database migrations, and workflow definitions across a strict physical air-gap perimeter (via encrypted industrial USB storage media or transient maintenance jump-boxes).
Two architectural delivery patterns were evaluated:
1. **On-Premises Harbor / Distribution Container Registry**: Deploying and maintaining a local private container registry inside the plant OT network.
2. **Cryptographically Signed Offline Self-Contained Tarball Bundles**: Packaging images, manifests, and charts into a single signed archive (`fieldkit-<version>-airgap.tar.gz`) consumed directly by `fieldkit-ctl`.

Operating a private container registry inside the plant introduces severe maintenance overhead:
- Requires dedicated registry database, TLS certificate management, storage garbage collection, and persistent uptime.
- Plant IT administrators must manually sync images from outside to the jump-box, re-tag images, and push them to the local registry before any Helm deployment can run.

## Decision
We implemented **Cryptographically Signed Offline Tarball Bundles with Cosign/ECDSA Verification**:
1. **Self-Contained Bundle Format (`scripts/build_bundle.py`)**:
   - The release bundle packages all offline container images, Helm umbrella charts, Docker Compose manifests, and standard workflow definitions into a single compressed tarball.
   - Includes `manifest.json` recording cryptographic SHA-256 digests for every embedded artifact.
2. **Cosign & ECDSA P-256 Digital Signatures**:
   - The archive is digitally signed at release time (`fieldkit-<version>-airgap.tar.gz.sig`).
   - `fieldkit-ctl` validates the SHA-256 digest and verifies the cryptographic signature against the embedded public key before loading any image or applying any Kubernetes manifest.
3. **Direct Daemon Ingestion**:
   - `fieldkit-ctl install` streams container images directly into the local containerd/Docker daemon (`k3d image import` or `docker load`), completely eliminating the need for an internal registry server.

## Consequences
- **Positive**:
  - Zero registry infrastructure required inside the air-gapped plant.
  - End-to-end cryptographic provenance guarantees: tamper-evident signature verification prevents supply-chain injection attacks.
  - One-command offline installation and verification (`fieldkit-ctl install --bundle fieldkit-1.0.0-airgap.tar.gz`).
- **Negative**:
  - Bundle file size is proportional to container image footprint (~2-3 GB full release bundle).
