#!/usr/bin/env bash
# Sync beads issues to GitHub Issues (outbound).
# Beads is source of truth for task state. GitHub is the public mirror.
#
# Usage:
#   scripts/gh-sync.sh              # Sync all beads issues to GitHub
#   scripts/gh-sync.sh --dry-run    # Preview without making changes
#
# Requires: gh (authenticated), bd, python3

set -euo pipefail

for arg in "$@"; do
    case "$arg" in
        --dry-run) ;; # handled by Python
        -h|--help)
            echo "Usage: $0 [--dry-run]"
            echo "Sync beads issues to GitHub Issues."
            exit 0
            ;;
    esac
done

for cmd in gh bd python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: $cmd not found"
        exit 1
    fi
done

if ! gh auth status &>/dev/null; then
    echo "Error: gh CLI not authenticated. Run: gh auth login"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}${PYTHONPATH:+:$PYTHONPATH}"

exec python3 "${SCRIPT_DIR}/gh_sync.py" "$@"
