#!/usr/bin/env bash
set -euo pipefail

# Fieldkit Restore Wrapper Script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT"
uv run python scripts/restore.py "$@"
