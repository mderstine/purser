#!/usr/bin/env bash
# Generate a changelog from closed beads issues.
# Groups by epic and type, includes commit SHAs and GitHub issue links.
#
# Usage:
#   scripts/gh-changelog.sh                    # All closed issues
#   scripts/gh-changelog.sh --since 2026-03-01 # Since a date
#   scripts/gh-changelog.sh --output CHANGELOG.md  # Write to file
#   scripts/gh-changelog.sh --dry-run          # Preview (same as no --output)
#
# Requires: bd, python3

set -euo pipefail

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            echo "Usage: $0 [--since YYYY-MM-DD] [--output FILE] [--dry-run]"
            echo "Generate a changelog from closed beads issues."
            exit 0
            ;;
    esac
done

for cmd in bd python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: $cmd not found"
        exit 1
    fi
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}${PYTHONPATH:+:$PYTHONPATH}"

exec python3 "${SCRIPT_DIR}/gh_changelog.py" "$@"
