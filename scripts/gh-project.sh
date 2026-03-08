#!/usr/bin/env bash
# Thin wrapper — delegates to Python. See gh_project.py for implementation.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec uv run python3 "${SCRIPT_DIR}/gh_project.py" "$@"
