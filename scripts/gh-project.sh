#!/usr/bin/env bash
# Manage GitHub Projects v2 board for beads issue tracking.
# Creates/maintains a project board with Status columns (Backlog, Ready,
# In Progress, Done) and custom fields (Priority, Type).
#
# Usage:
#   scripts/gh-project.sh              # Sync issues to project board
#   scripts/gh-project.sh --dry-run    # Preview without making changes
#   scripts/gh-project.sh --setup      # Create/configure project only (no issue sync)
#
# Requires: gh (authenticated with read:project,project scopes), bd, python3

set -euo pipefail

for arg in "$@"; do
    case "$arg" in
        --dry-run|--setup) ;; # handled by Python
        -h|--help)
            echo "Usage: $0 [--dry-run] [--setup]"
            echo "Manage GitHub Projects v2 board for beads issues."
            echo ""
            echo "  --dry-run  Preview without making changes"
            echo "  --setup    Create/configure project only (no issue sync)"
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

# Check for project scopes
if ! gh api graphql -f query='{ viewer { projectsV2(first:1) { totalCount } } }' &>/dev/null; then
    echo "Error: gh token lacks project scopes. Run:"
    echo "  gh auth refresh -h github.com -s read:project,project"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}${PYTHONPATH:+:$PYTHONPATH}"

exec python3 "${SCRIPT_DIR}/gh_project.py" "$@"
