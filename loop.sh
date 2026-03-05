#!/usr/bin/env bash
# Ralph-Beads Loop: Autonomous AI development with dependency-aware task tracking
#
# Usage:
#   ./loop.sh              # Build mode, unlimited iterations
#   ./loop.sh 20           # Build mode, max 20 iterations
#   ./loop.sh plan         # Planning mode, unlimited
#   ./loop.sh plan 5       # Planning mode, max 5 iterations

set -euo pipefail

MODE="build"
MAX_ITERATIONS=0
ITERATION=0

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        plan) MODE="plan" ;;
        *[0-9]*) MAX_ITERATIONS="$arg" ;;
    esac
done

PROMPT_FILE="PROMPT_${MODE}.md"

if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "Error: $PROMPT_FILE not found"
    exit 1
fi

# Verify bd is available
if ! command -v bd &>/dev/null; then
    echo "Error: bd (beads) CLI not found. Install with: npm install -g @beads/bd"
    exit 1
fi

echo "=== Ralph-Beads Loop ==="
echo "Mode: $MODE"
echo "Prompt: $PROMPT_FILE"
echo "Max iterations: ${MAX_ITERATIONS:-unlimited}"
echo "========================"

while true; do
    ITERATION=$((ITERATION + 1))

    if [[ "$MAX_ITERATIONS" -gt 0 && "$ITERATION" -gt "$MAX_ITERATIONS" ]]; then
        echo "Reached max iterations ($MAX_ITERATIONS). Stopping."
        break
    fi

    echo ""
    echo "--- Iteration $ITERATION ($(date '+%H:%M:%S')) ---"

    # Check if there's work to do (build mode only)
    if [[ "$MODE" == "build" ]]; then
        READY_COUNT=$(bd ready --json 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
        if [[ "$READY_COUNT" == "0" ]]; then
            echo "No ready work found. All tasks complete or blocked."
            echo "Run './loop.sh plan' to generate new tasks, or check blockers with 'bd list --status open'."
            break
        fi
        echo "Ready work: $READY_COUNT issue(s)"
    fi

    # Feed the prompt to Claude Code
    cat "$PROMPT_FILE" | claude -p \
        --output-format=stream-json \
        --verbose \
        --model opus \
        2>&1 | tee "/tmp/ralph-beads-iter-${ITERATION}.log"

    EXIT_CODE=${PIPESTATUS[1]:-0}

    if [[ "$EXIT_CODE" -ne 0 ]]; then
        echo "Claude exited with code $EXIT_CODE. Pausing for review."
        echo "Press Enter to continue or Ctrl+C to stop."
        read -r
    fi

    # Sync beads after each iteration
    bd sync 2>/dev/null || true

    echo "--- Iteration $ITERATION complete ---"
done

echo ""
echo "=== Loop finished after $ITERATION iteration(s) ==="
bd prime 2>/dev/null || true
