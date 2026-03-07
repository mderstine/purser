#!/usr/bin/env bash
# Ralph-Beads Project Initialization
#
# Bootstraps a new Ralph-Beads project from the GitHub template.
# Idempotent — safe to re-run; skips completed steps.
#
# Usage:
#   ./init.sh              # Interactive setup
#   ./init.sh --check      # Check prerequisites only, no prompts
#   ./init.sh --skip-github # Skip all GitHub integration steps
#
# Steps:
#   1. Check prerequisites (git, python3, uv, gh, bd)
#   2. Create Python virtual environment (uv venv + uv sync)
#   3. Initialize beads database if needed
#   4. Detect/create GitHub remote
#   5. Detect/setup GitHub Project
#   6. Bootstrap GitHub labels
#   7. Save configuration to .ralph-beads.yml
#   8. Print summary and next steps

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$SCRIPT_DIR/scripts"
CONFIG_FILE="$SCRIPT_DIR/.ralph-beads.yml"
CHECK_ONLY=false
SKIP_GITHUB=false

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --check) CHECK_ONLY=true ;;
        --skip-github) SKIP_GITHUB=true ;;
        -h|--help)
            echo "Usage: $0 [--check] [--skip-github]"
            echo ""
            echo "Options:"
            echo "  --check         Check prerequisites only, no prompts"
            echo "  --skip-github   Skip GitHub remote, projects, and label setup"
            echo "  -h, --help      Show this help message"
            exit 0
            ;;
    esac
done

# ─── Helpers ─────────────────────────────────────────────────────────────────

print_header() {
    echo ""
    echo "========================================="
    echo "  Ralph-Beads Project Initialization"
    echo "========================================="
    echo ""
}

print_step() {
    local step="$1"
    local desc="$2"
    echo "--- Step $step: $desc ---"
}

print_summary() {
    echo ""
    echo "========================================="
    echo "  Setup Summary"
    echo "========================================="
    echo ""

    # Beads
    if [[ -d "$SCRIPT_DIR/.beads" ]]; then
        echo "  Beads database: initialized"
    else
        echo "  Beads database: not initialized"
    fi

    # Config
    if [[ -f "$CONFIG_FILE" ]]; then
        echo "  Config file: $CONFIG_FILE"
        local owner repo project_number
        owner=$(python3 "$SCRIPTS_DIR/config.py" get github.owner 2>/dev/null || echo "")
        repo=$(python3 "$SCRIPTS_DIR/config.py" get github.repo 2>/dev/null || echo "")
        project_number=$(python3 "$SCRIPTS_DIR/config.py" get github.project_number 2>/dev/null || echo "")
        if [[ -n "$owner" && -n "$repo" ]]; then
            echo "  GitHub repo: $owner/$repo"
        else
            echo "  GitHub repo: not configured"
        fi
        if [[ -n "$project_number" ]]; then
            echo "  GitHub Project: #$project_number"
        else
            echo "  GitHub Project: not configured"
        fi
    else
        echo "  Config file: not created"
    fi

    echo ""
    echo "Next steps:"
    echo "  1. Write specs in specs/ describing what to build"
    echo "  2. Run './loop.sh plan' to generate the task graph"
    echo "  3. Run './loop.sh' to start building"
    echo ""
}

# ─── Step 1: Prerequisites ──────────────────────────────────────────────────

print_header
print_step 1 "Checking prerequisites"

PREREQ_RESULT=$(python3 "$SCRIPTS_DIR/prereqs.py" --json 2>&1) || true
PREREQ_OK=$(echo "$PREREQ_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('all_ok', False))" 2>/dev/null || echo "False")

# Always show the human-readable report
python3 "$SCRIPTS_DIR/prereqs.py" 2>&1 || true
echo ""

if [[ "$PREREQ_OK" != "True" ]]; then
    echo "Some prerequisites are missing. Install them and re-run ./init.sh"
    # Check if the critical ones (git, python3) are missing vs optional (gh, bd)
    HAS_GIT=$(echo "$PREREQ_RESULT" | python3 -c "
import sys, json
tools = {t['name']: t['found'] for t in json.load(sys.stdin)['tools']}
print(tools.get('git', False) and tools.get('python3', False))
" 2>/dev/null || echo "False")
    if [[ "$HAS_GIT" != "True" ]]; then
        echo "ERROR: git and python3 are required. Cannot continue."
        exit 1
    fi
    echo "WARNING: Continuing with available tools (some features may be limited)."
    echo ""
fi

if $CHECK_ONLY; then
    echo "Check complete."
    exit 0
fi

# ─── Step 2: Python Virtual Environment ────────────────────────────────────

print_step 2 "Python virtual environment (uv)"

if command -v uv &>/dev/null; then
    if [[ -d "$SCRIPT_DIR/.venv" ]]; then
        echo "  .venv/ directory exists — syncing dependencies..."
        uv sync --project "$SCRIPT_DIR" 2>&1 || {
            echo "  WARNING: uv sync failed. Dependencies may be out of date."
        }
    else
        echo "  Creating virtual environment..."
        uv venv "$SCRIPT_DIR/.venv" 2>&1 || {
            echo "  WARNING: uv venv failed."
        }
        echo "  Installing dependencies..."
        uv sync --project "$SCRIPT_DIR" 2>&1 || {
            echo "  WARNING: uv sync failed."
        }
    fi
    echo "  Virtual environment ready."
else
    echo "  WARNING: uv not found — skipping virtual environment setup."
    echo "  Install uv and re-run ./init.sh to set up the environment."
fi
echo ""

# ─── Step 3: Beads Database ─────────────────────────────────────────────────

print_step 3 "Beads database"

if [[ -d "$SCRIPT_DIR/.beads" ]]; then
    echo "  .beads/ directory exists — skipping initialization."
    # Check if this looks like template data that should be reset
    ISSUE_COUNT=$(bd list --json 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    echo "  Current issues: $ISSUE_COUNT"
else
    echo "  Initializing beads database..."
    if command -v bd &>/dev/null; then
        bd init 2>&1 || {
            echo "  WARNING: bd init failed. You may need to initialize manually."
        }
        echo "  Beads database initialized."
    else
        echo "  WARNING: bd CLI not found — skipping beads initialization."
        echo "  Install bd and re-run ./init.sh to initialize."
    fi
fi
echo ""

# ─── Step 4: GitHub Remote ──────────────────────────────────────────────────

print_step 4 "GitHub remote"

GITHUB_OWNER=""
GITHUB_REPO=""

if $SKIP_GITHUB; then
    echo "  Skipped (--skip-github)."
else
    # First, detect non-interactively
    REMOTE_RESULT=$(python3 "$SCRIPTS_DIR/gh_remote.py" --check --json 2>&1) || true
    REMOTE_STATUS=$(echo "$REMOTE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status', 'error'))" 2>/dev/null || echo "error")

    if [[ "$REMOTE_STATUS" == "found" ]]; then
        GITHUB_OWNER=$(echo "$REMOTE_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin).get('remote',{}); print(r.get('owner',''))" 2>/dev/null || echo "")
        GITHUB_REPO=$(echo "$REMOTE_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin).get('remote',{}); print(r.get('repo',''))" 2>/dev/null || echo "")
        echo "  GitHub remote: $GITHUB_OWNER/$GITHUB_REPO"
    elif [[ "$REMOTE_STATUS" == "skipped" ]] && ! $CHECK_ONLY; then
        # No remote found — run interactively to allow creation
        python3 "$SCRIPTS_DIR/gh_remote.py" 2>&1 || true
        # Re-check after interactive flow
        REMOTE_RESULT=$(python3 "$SCRIPTS_DIR/gh_remote.py" --check --json 2>&1) || true
        REMOTE_STATUS=$(echo "$REMOTE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status', 'error'))" 2>/dev/null || echo "error")
        if [[ "$REMOTE_STATUS" == "found" ]]; then
            GITHUB_OWNER=$(echo "$REMOTE_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin).get('remote',{}); print(r.get('owner',''))" 2>/dev/null || echo "")
            GITHUB_REPO=$(echo "$REMOTE_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin).get('remote',{}); print(r.get('repo',''))" 2>/dev/null || echo "")
            echo "  GitHub remote: $GITHUB_OWNER/$GITHUB_REPO"
        else
            echo "  GitHub remote: not configured (local-only mode)"
        fi
    else
        echo "  GitHub remote: $REMOTE_STATUS"
    fi
fi
echo ""

# ─── Step 5: GitHub Project ─────────────────────────────────────────────────

print_step 5 "GitHub Project"

GITHUB_PROJECT=""

if $SKIP_GITHUB || [[ -z "$GITHUB_OWNER" || -z "$GITHUB_REPO" ]]; then
    if $SKIP_GITHUB; then
        echo "  Skipped (--skip-github)."
    else
        echo "  Skipped (no GitHub remote configured)."
    fi
else
    # First, check existing state non-interactively
    PROJECT_RESULT=$(python3 "$SCRIPTS_DIR/gh_project_setup.py" --check --json 2>&1) || true
    PROJECT_STATUS=$(echo "$PROJECT_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status', 'error'))" 2>/dev/null || echo "error")

    if [[ "$PROJECT_STATUS" == "found" ]]; then
        GITHUB_PROJECT=$(echo "$PROJECT_RESULT" | python3 -c "import sys,json; p=json.load(sys.stdin).get('project',{}); print(p.get('number',''))" 2>/dev/null || echo "")
        PROJECT_TITLE=$(echo "$PROJECT_RESULT" | python3 -c "import sys,json; p=json.load(sys.stdin).get('project',{}); print(p.get('title',''))" 2>/dev/null || echo "")
        echo "  Found GitHub Project: $PROJECT_TITLE (#$GITHUB_PROJECT)"
    elif [[ "$PROJECT_STATUS" == "skipped" ]] && ! $CHECK_ONLY; then
        # No projects found — offer to create one interactively
        echo "  No GitHub Projects found."
        read -r -p "  Create a new project with default columns? [Y/n]: " CREATE_PROJECT
        CREATE_PROJECT=${CREATE_PROJECT:-Y}
        if [[ "$CREATE_PROJECT" =~ ^[Yy] ]]; then
            CREATE_RESULT=$(python3 - "$SCRIPTS_DIR" "$GITHUB_OWNER" "$GITHUB_REPO" <<'PYEOF'
import sys, json
sys.path.insert(0, sys.argv[1])
import gh_project_setup
result = gh_project_setup.create_project(sys.argv[2], sys.argv[3])
if result:
    print(json.dumps(result))
else:
    print("{}")
PYEOF
            ) || true
            GITHUB_PROJECT=$(echo "$CREATE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('number',''))" 2>/dev/null || echo "")
            if [[ -n "$GITHUB_PROJECT" ]]; then
                echo "  Created GitHub Project #$GITHUB_PROJECT"
            else
                echo "  WARNING: Failed to create project."
            fi
        else
            echo "  Skipped project creation."
        fi
    else
        echo "  GitHub Project: $PROJECT_STATUS"
    fi
fi
echo ""

# ─── Step 6: Label Bootstrap ────────────────────────────────────────────────

print_step 6 "GitHub labels"

if $SKIP_GITHUB || [[ -z "$GITHUB_OWNER" || -z "$GITHUB_REPO" ]]; then
    if $SKIP_GITHUB; then
        echo "  Skipped (--skip-github)."
    else
        echo "  Skipped (no GitHub remote configured)."
    fi
else
    # Check if labels have already been bootstrapped
    LABELS_DONE=$(python3 "$SCRIPTS_DIR/config.py" get labels.bootstrap 2>/dev/null || echo "false")
    if [[ "$LABELS_DONE" == "true" ]]; then
        echo "  Labels already bootstrapped — skipping."
    else
        echo "  Bootstrapping GitHub labels..."
        if [[ -x "$SCRIPTS_DIR/gh-labels.sh" ]] || [[ -f "$SCRIPTS_DIR/gh-labels.sh" ]]; then
            bash "$SCRIPTS_DIR/gh-labels.sh" 2>&1 || {
                echo "  WARNING: Label bootstrap failed (non-fatal)."
            }
        else
            echo "  WARNING: gh-labels.sh not found — skipping."
        fi
    fi
fi
echo ""

# ─── Step 7: Save Configuration ─────────────────────────────────────────────

print_step 7 "Configuration"

# Build config via Python to ensure proper YAML formatting
python3 - "$SCRIPT_DIR" "$SCRIPTS_DIR" "$GITHUB_OWNER" "$GITHUB_REPO" "$GITHUB_PROJECT" "$($SKIP_GITHUB && echo 1 || echo 0)" <<'PYEOF'
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
sys.path.insert(0, sys.argv[2])
import config

owner = sys.argv[3]
repo = sys.argv[4]
project = sys.argv[5]
skip_github = sys.argv[6] == "1"

cfg = config.load_config(repo_root)

if owner:
    cfg["github"]["owner"] = owner
if repo:
    cfg["github"]["repo"] = repo
if project:
    cfg["github"]["project_number"] = project
if owner and repo and not skip_github:
    cfg["labels"]["bootstrap"] = "true"

config.save_config(cfg, repo_root)
print("  Configuration saved to .ralph-beads.yml")
PYEOF
if [[ $? -ne 0 ]]; then
    echo "  WARNING: Failed to save configuration."
fi

echo ""

# ─── Step 8: Summary ────────────────────────────────────────────────────────

print_summary
