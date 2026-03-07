#!/usr/bin/env bash
# Generate a PR description from beads issues addressed in the current branch.
# Reads git log to find 'Closes: <bd-id>' references, looks up those issues
# and their GitHub counterparts, and formats a PR body.
#
# Usage:
#   scripts/gh-pr-body.sh              # Compare against main
#   scripts/gh-pr-body.sh --base dev   # Compare against dev branch
#   scripts/gh-pr-body.sh --output pr-body.md  # Write to file
#
# Requires: bd, python3, git

set -euo pipefail

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            echo "Usage: $0 [--base BRANCH] [--output FILE]"
            echo "Generate a PR description from beads issues on the current branch."
            exit 0
            ;;
    esac
done

for cmd in bd python3 git; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: $cmd not found"
        exit 1
    fi
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}${PYTHONPATH:+:$PYTHONPATH}"

exec python3 "${SCRIPT_DIR}/gh_pr_body.py" "$@"
