#!/usr/bin/env python3
"""Build and cryptographically sign the Fieldkit Air-Gapped Release Bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
DIST_DIR = ROOT_DIR / "dist"
VERSION = "1.0.0"

OFFLINE_IMAGE_MANIFEST = [
    {"image": "pgvector/pgvector:pg16", "category": "database", "size_mb": 420},
    {"image": "minio/minio:RELEASE.2024-05-10T01-41-38Z", "category": "object_storage", "size_mb": 150},
    {"image": "redis:7.2-alpine", "category": "cache", "size_mb": 35},
    {"image": "clickhouse/clickhouse-server:24.3-alpine", "category": "analytics", "size_mb": 850},
    {"image": "redpandadata/redpanda:v24.1.2", "category": "streaming", "size_mb": 220},
    {"image": "fieldkit/workflow-engine:1.0.0", "category": "platform", "size_mb": 65},
    {"image": "fieldkit/foundry:1.0.0", "category": "platform", "size_mb": 280},
    {"image": "fieldkit/assistant:1.0.0", "category": "platform", "size_mb": 310},
    {"image": "fieldkit/copilot:1.0.0", "category": "platform", "size_mb": 290},
    {"image": "fieldkit/docai:1.0.0", "category": "platform", "size_mb": 410},
    {"image": "fieldkit/vision-edge:1.0.0", "category": "platform", "size_mb": 520},
    {"image": "fieldkit/tracehub:1.0.0", "category": "platform", "size_mb": 190},
    {"image": "fieldkit/console:1.0.0", "category": "frontend", "size_mb": 140},
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def build_airgap_bundle(output_dir: Path | None = None) -> tuple[Path, Path]:
    out = output_dir or DIST_DIR
    out.mkdir(parents=True, exist_ok=True)

    bundle_name = f"fieldkit-{VERSION}-airgap"
    staging_dir = out / f"staging_{bundle_name}"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)

    # 1. Copy Helm umbrella chart
    helm_dest = staging_dir / "helm" / "fieldkit"
    shutil.copytree(ROOT_DIR / "deploy" / "helm" / "fieldkit", helm_dest)

    # 2. Copy Docker Compose definitions
    compose_dest = staging_dir / "compose"
    compose_dest.mkdir(parents=True)
    shutil.copy2(ROOT_DIR / "deploy" / "compose" / "docker-compose.yml", compose_dest / "docker-compose.yml")

    # 3. Copy Standard Shipped Workflows
    workflows_dest = staging_dir / "workflows"
    shutil.copytree(ROOT_DIR / "workflows", workflows_dest)

    # 4. Write Image Manifest
    images_manifest_path = staging_dir / "images_manifest.json"
    with open(images_manifest_path, "w", encoding="utf-8") as f:
        json.dump(OFFLINE_IMAGE_MANIFEST, f, indent=2)

    # 5. Create Bundle Metadata Manifest
    manifest = {
        "format": "fieldkit-airgap-bundle",
        "bundle_version": VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "target_plant": "DE-HAM-OT",
        "total_images": len(OFFLINE_IMAGE_MANIFEST),
        "total_image_size_mb": sum(x["size_mb"] for x in OFFLINE_IMAGE_MANIFEST),
        "components": {
            "helm_chart": "deploy/helm/fieldkit",
            "compose_manifest": "deploy/compose/docker-compose.yml",
            "workflows": [w.name for w in (ROOT_DIR / "workflows").glob("*.yaml")],
        },
    }

    manifest_path = staging_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # 6. Tarball the staging directory into .tar.gz
    archive_path = out / f"{bundle_name}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(staging_dir, arcname=bundle_name)

    # Cleanup staging directory
    shutil.rmtree(staging_dir)

    # 7. Compute SHA-256 Digest
    digest = sha256_file(archive_path)
    checksum_file = out / f"{bundle_name}.sha256"
    with open(checksum_file, "w", encoding="utf-8") as f:
        f.write(f"{digest}  {archive_path.name}\n")

    # 8. Cryptographic Signing via Go fieldkit-ctl or Python cryptography
    sig_path = archive_path.with_suffix(archive_path.suffix + ".sig")
    pub_path = archive_path.with_suffix(archive_path.suffix + ".pub")

    ctl_exe = ROOT_DIR / "services" / "workflow-engine" / "fieldkit-ctl.exe"
    if ctl_exe.exists():
        import subprocess

        res = subprocess.run(
            [str(ctl_exe), "sign", "--file", str(archive_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(f"fieldkit-ctl signing failed: {res.stderr}")
    else:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

        priv_key = ec.generate_private_key(ec.SECP256R1())
        pub_key = priv_key.public_key()

        with open(archive_path, "rb") as f:
            data = f.read()

        der_sig = priv_key.sign(data, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der_sig)
        sig_data = f"{r:x}:{s:x}"
        with open(sig_path, "w", encoding="utf-8") as f:
            f.write(sig_data)

        pub_pem = pub_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        with open(pub_path, "wb") as f:
            f.write(pub_pem)

    return archive_path, sig_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Fieldkit Air-Gap Bundle")
    parser.add_argument("--out-dir", type=Path, default=DIST_DIR, help="Destination directory")
    args = parser.parse_args()

    print(f"==> Building Fieldkit v{VERSION} air-gapped release bundle...")
    archive, sig = build_airgap_bundle(args.out_dir)
    size_mb = os.path.getsize(archive) / (1024 * 1024)

    print(f"[SUCCESS] Air-gapped release bundle created:\n  Archive:   {archive} ({size_mb:.2f} MB)")
    print(f"  Signature: {sig}")
    print(f"  Checksum:  {archive.with_suffix('.sha256')}")


if __name__ == "__main__":
    main()
