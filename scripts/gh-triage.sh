#!/usr/bin/env bash
# Triage GitHub Issues labeled 'spec-candidate' into specs/ files.
# This is the inbound flow: collaborators create GitHub Issues with the
# 'spec-candidate' label, and this script converts them to spec files
# that the planning loop can decompose into beads tasks.
#
# Usage:
#   scripts/gh-triage.sh              # Triage all spec-candidate issues
#   scripts/gh-triage.sh --dry-run    # Preview without making changes
#
# Requires: gh (authenticated), python3

set -euo pipefail

for arg in "$@"; do
    case "$arg" in
        --dry-run) ;; # handled by Python
        -h|--help)
            echo "Usage: $0 [--dry-run]"
            echo "Triage GitHub Issues labeled 'spec-candidate' into specs/ files."
            exit 0
            ;;
    esac
done

for cmd in gh python3; do
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

exec python3 "${SCRIPT_DIR}/gh_triage.py" "$@"
