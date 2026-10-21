#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "==> Packaging Fieldkit Air-Gapped Release Bundle..."
uv run python "${ROOT_DIR}/scripts/build_bundle.py" "$@"
