"""Publish Jinja prompt templates to Tracehub Prompt Registry.

Scans the repository for Jinja prompt templates (*.jinja), parses the version
header `{# version: X.Y.Z #}`, computes template SHA-256 hashes, and registers
each template version with Fieldkit Tracehub.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

import httpx

VERSION_PATTERN = re.compile(r"\{#\s*version:\s*([^\s#]+)\s*#\}")


def parse_prompt_file(path: Path) -> dict[str, Any] | None:
    """Read a Jinja prompt file and extract version, template, and hash."""
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"[ERROR] Failed reading {path}: {exc}", file=sys.stderr)
        return None

    match = VERSION_PATTERN.search(content)
    version = match.group(1).strip() if match else "0.1.0"

    sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()

    # Determine prompt name from file stem
    prompt_name = path.stem

    # Determine package/service owner from relative path parts
    parts = path.parts
    package = "fieldkit"
    if "packages" in parts:
        idx = parts.index("packages")
        if idx + 1 < len(parts):
            package = f"fieldkit_{parts[idx + 1]}"
    elif "services" in parts:
        idx = parts.index("services")
        if idx + 1 < len(parts):
            package = f"service_{parts[idx + 1]}"

    return {
        "name": prompt_name,
        "version": version,
        "template": content,
        "sha256": sha256,
        "package": package,
        "path": str(path),
    }


def find_prompt_files(root: Path) -> list[Path]:
    """Find all *.jinja prompt files under the specified directory."""
    files: list[Path] = []
    for p in root.rglob("*.jinja"):
        parts = p.parts
        if any(ignored in parts for ignored in (".venv", "venv", ".git", "node_modules", "__pycache__", ".next")):
            continue
        if p.is_file() and p not in files:
            files.append(p)
    files.sort()
    return files


def publish_prompts(
    root: Path,
    url: str,
    dry_run: bool = False,
    timeout: float = 10.0,
) -> int:
    """Scan and publish prompt templates to Tracehub."""
    files = find_prompt_files(root)
    if not files:
        print(f"[INFO] No .jinja prompt templates found under {root}")
        return 0

    print(f"[INFO] Found {len(files)} prompt templates under {root}")
    success_count = 0
    failure_count = 0

    endpoint = url.rstrip("/")
    if not endpoint.endswith("/prompts"):
        endpoint = f"{endpoint}/prompts"

    client = httpx.Client(timeout=timeout) if not dry_run else None

    for f in files:
        data = parse_prompt_file(f)
        if not data:
            failure_count += 1
            continue

        print(
            f"  -> {data['name']} (v{data['version']}, package={data['package']}, "
            f"sha256={data['sha256'][:8]}...)"
        )

        if dry_run:
            success_count += 1
            continue

        assert client is not None
        payload = {
            "name": data["name"],
            "version": data["version"],
            "template": data["template"],
            "sha256": data["sha256"],
            "package": data["package"],
        }
        try:
            resp = client.post(endpoint, json=payload)
            if resp.status_code in (200, 201):
                print(f"     [OK] Registered with Tracehub: {endpoint}")
                success_count += 1
            else:
                print(f"     [FAILED] Tracehub HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
                failure_count += 1
        except Exception as exc:
            print(f"     [FAILED] Error sending to {endpoint}: {exc}", file=sys.stderr)
            failure_count += 1

    if client:
        client.close()

    print(f"\n[SUMMARY] {success_count} succeeded, {failure_count} failed.")
    return 1 if failure_count > 0 else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish Jinja prompt templates to Tracehub Prompt Registry")
    parser.add_argument(
        "--dir",
        default=".",
        help="Root directory to search for prompts (default: repository root)",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8006/prompts",
        help="Tracehub prompts API endpoint (default: http://localhost:8006/prompts)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and validate prompts without publishing over HTTP",
    )
    args = parser.parse_args()

    repo_root = Path(args.dir).resolve()
    exit_code = publish_prompts(root=repo_root, url=args.url, dry_run=args.dry_run)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
