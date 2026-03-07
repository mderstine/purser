#!/usr/bin/env bash
# Ralph-Beads Loop: Autonomous AI development with dependency-aware task tracking
#
# Usage:
#   ./loop.sh              # Build mode, unlimited iterations
#   ./loop.sh 20           # Build mode, max 20 iterations
#   ./loop.sh plan         # Planning mode, unlimited
#   ./loop.sh plan 5       # Planning mode, max 5 iterations
#   ./loop.sh status       # Print iteration stats from logs/summary.jsonl
#   ./loop.sh sync         # Sync beads issues to GitHub (single-shot)
#   ./loop.sh triage       # Triage spec-candidate GitHub Issues (single-shot)
#   ./loop.sh changelog    # Generate changelog from closed issues (single-shot)
#
# Timeout:
#   --timeout=VALUE        # Override per-iteration timeout (timeout(1) format: 900, 15m, 1h)
#   RALPH_TIMEOUT=VALUE    # Same via environment variable
#   Defaults: build=15m, plan=10m

set -euo pipefail

MODE="build"
MAX_ITERATIONS=0
ITERATION=0
CLAUDE_PID=""           # PID of current Claude subshell; empty when idle
SHUTDOWN_REQUESTED=false
SIGNAL_GRACE=30         # Seconds to wait for Claude to exit before force-kill

# Timeout defaults per mode; override via --timeout=VALUE or RALPH_TIMEOUT env var
TIMEOUT_BUILD="${RALPH_TIMEOUT:-900}"   # 15 minutes
TIMEOUT_PLAN="${RALPH_TIMEOUT:-600}"    # 10 minutes
TIMEOUT_OVERRIDE=""

# ─── Signal handling ──────────────────────────────────────────────────────────

print_summary() {
    echo ""
    echo "=== Loop finished after $ITERATION iteration(s) ==="
    bd prime 2>/dev/null || true
}

cleanup() {
    local sig="${1:-SIGINT}"
    SHUTDOWN_REQUESTED=true
    echo ""
    echo "=== Signal received ($sig). Shutting down gracefully... ==="

    if [[ -n "$CLAUDE_PID" ]] && kill -0 "$CLAUDE_PID" 2>/dev/null; then
        echo "Waiting for Claude (PID $CLAUDE_PID) to exit (grace: ${SIGNAL_GRACE}s)..."
        # Kill the entire process group to reach all pipeline members
        kill -TERM -- -"$CLAUDE_PID" 2>/dev/null || kill -TERM "$CLAUDE_PID" 2>/dev/null || true

        local elapsed=0
        while kill -0 "$CLAUDE_PID" 2>/dev/null && [[ $elapsed -lt $SIGNAL_GRACE ]]; do
            sleep 1
            elapsed=$((elapsed + 1))
        done

        if kill -0 "$CLAUDE_PID" 2>/dev/null; then
            echo "Grace period expired. Force-killing Claude..."
            kill -KILL -- -"$CLAUDE_PID" 2>/dev/null || kill -KILL "$CLAUDE_PID" 2>/dev/null || true
        else
            echo "Claude exited cleanly."
        fi
    fi

    print_summary
    exit 130
}

trap 'cleanup SIGINT'  INT
trap 'cleanup SIGTERM' TERM

# ─── Argument parsing ─────────────────────────────────────────────────────────

PASSTHROUGH_ARGS=()
for arg in "$@"; do
    case "$arg" in
        plan)        MODE="plan" ;;
        status)      MODE="status" ;;
        sync)        MODE="sync" ;;
        triage)      MODE="triage" ;;
        changelog)   MODE="changelog" ;;
        --dry-run)   PASSTHROUGH_ARGS+=("$arg") ;;
        --timeout=*) TIMEOUT_OVERRIDE="${arg#--timeout=}" ;;
        *) [[ "$arg" =~ ^[0-9]+$ ]] && MAX_ITERATIONS="$arg" ;;
    esac
done

# ─── Single-shot modes: delegate to scripts and exit ──────────────────────────

case "$MODE" in
    status)
        SUMMARY_FILE="logs/summary.jsonl"
        if [[ ! -f "$SUMMARY_FILE" ]]; then
            echo "No iteration logs found. Run ./loop.sh to generate logs."
            exit 0
        fi
        python3 -c "
import json, sys

entries = []
for line in open('$SUMMARY_FILE'):
    line = line.strip()
    if line:
        entries.append(json.loads(line))

if not entries:
    print('No iteration data found.')
    sys.exit(0)

total = len(entries)
success = sum(1 for e in entries if e.get('outcome') == 'success')
fail = sum(1 for e in entries if e.get('outcome') == 'error')
timeout = sum(1 for e in entries if e.get('outcome') == 'timeout')
durations = [e.get('duration_s', 0) for e in entries]
avg_dur = sum(durations) / len(durations) if durations else 0
rate = (success / total * 100) if total else 0

print('=== Ralph-Beads Iteration Stats ===')
print()
print(f'  Total iterations:  {total}')
print(f'  Success:           {success}')
print(f'  Errors:            {fail}')
print(f'  Timeouts:          {timeout}')
print(f'  Success rate:      {rate:.0f}%')
print(f'  Avg duration:      {avg_dur:.0f}s')
print()
print('--- Last 5 iterations ---')
print(f'{\"#\":<5} {\"Mode\":<8} {\"Outcome\":<10} {\"Duration\":<10} {\"Beads Issue\":<20} {\"Started\"}')
print(f'{\"─\"*5} {\"─\"*8} {\"─\"*10} {\"─\"*10} {\"─\"*20} {\"─\"*20}')
for e in entries[-5:]:
    dur = f\"{e.get('duration_s', 0)}s\"
    print(f\"{e.get('iteration', '?'):<5} {e.get('mode', '?'):<8} {e.get('outcome', '?'):<10} {dur:<10} {e.get('beads_issue_id', ''):<20} {e.get('start_time', '?')}\")
"
        exit 0
        ;;
    sync)
        echo "=== Ralph-Beads: GitHub Sync ==="
        exec scripts/gh-sync.sh "${PASSTHROUGH_ARGS[@]}"
        ;;
    triage)
        echo "=== Ralph-Beads: Issue Triage ==="
        exec scripts/gh-triage.sh "${PASSTHROUGH_ARGS[@]}"
        ;;
    changelog)
        echo "=== Ralph-Beads: Changelog ==="
        exec scripts/gh-changelog.sh "${PASSTHROUGH_ARGS[@]}"
        ;;
esac

# Resolve per-iteration timeout
if [[ -n "$TIMEOUT_OVERRIDE" ]]; then
    ITER_TIMEOUT="$TIMEOUT_OVERRIDE"
elif [[ "$MODE" == "plan" ]]; then
    ITER_TIMEOUT="$TIMEOUT_PLAN"
else
    ITER_TIMEOUT="$TIMEOUT_BUILD"
fi

PROMPT_FILE="PROMPT_${MODE}.md"

if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "Error: $PROMPT_FILE not found"
    exit 1
fi

# ─── Pre-flight checks ────────────────────────────────────────────────────────

preflight_checks() {
    local errors=0

    # 1. bd CLI available
    if ! command -v bd &>/dev/null; then
        echo "ERROR: bd (beads) CLI not found. Install with: npm install -g @beads/bd"
        errors=$((errors + 1))
    fi

    # 2. claude CLI available
    if ! command -v claude &>/dev/null; then
        echo "ERROR: claude CLI not found. Install Claude Code to continue."
        errors=$((errors + 1))
    fi

    # 3. beads database accessible
    if ! bd prime &>/dev/null 2>&1; then
        echo "ERROR: bd prime failed — beads database may be corrupted or inaccessible."
        echo "       Run 'bd prime' manually to see the error."
        errors=$((errors + 1))
    fi

    if [[ $errors -gt 0 ]]; then
        echo ""
        echo "Pre-flight failed with $errors error(s). Fix the issues above and retry."
        exit 1
    fi

    # 4. Warn if on main/master branch (non-fatal)
    local branch
    branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
    if [[ "$branch" == "main" || "$branch" == "master" ]]; then
        echo "WARNING: Running on '$branch' branch. Consider working on a feature branch."
    fi

    # 5. Warn about uncommitted changes — may conflict with loop commits (non-fatal)
    if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
        echo "WARNING: Uncommitted changes detected — these may conflict with loop commits:"
        git status --short 2>/dev/null | head -10
    fi
}

preflight_checks

echo "=== Ralph-Beads Loop ==="
echo "Mode: $MODE"
echo "Prompt: $PROMPT_FILE"
echo "Max iterations: ${MAX_ITERATIONS:-unlimited}"
echo "Iteration timeout: ${ITER_TIMEOUT}s"
echo "========================"

# ─── Main loop ────────────────────────────────────────────────────────────────

# Ensure logs directory exists
mkdir -p logs

while true; do
    ITERATION=$((ITERATION + 1))

    if [[ "$MAX_ITERATIONS" -gt 0 && "$ITERATION" -gt "$MAX_ITERATIONS" ]]; then
        echo "Reached max iterations ($MAX_ITERATIONS). Stopping."
        break
    fi

    if [[ "$SHUTDOWN_REQUESTED" == "true" ]]; then
        break
    fi

    # Capture iteration start time and set structured log path
    ITER_START=$(date '+%s')
    START_TIME=$(date '+%Y-%m-%dT%H:%M:%S')
    LOG_FILE="logs/${MODE}-${START_TIME}-iter-${ITERATION}.log"

    echo ""
    echo "--- Iteration $ITERATION (${START_TIME}) ---"

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

    # Snapshot closed issues to detect which beads issue gets closed this iteration
    CLOSED_BEFORE_FILE=$(mktemp)
    bd list --status closed --json 2>/dev/null | \
        python3 -c "import sys,json; [print(i['id']) for i in json.load(sys.stdin)]" \
        2>/dev/null | sort > "$CLOSED_BEFORE_FILE" || true

    # Run Claude via timeout in a tracked background subshell.
    # timeout exits with 124 on timeout, otherwise passes through Claude's exit code.
    # Exit code is captured via inner bash -c PIPESTATUS so we get Claude's actual code.
    CLAUDE_EXITCODE_FILE=$(mktemp)
    (
        timeout --kill-after=10 "$ITER_TIMEOUT" \
            bash -c '
                cat "$1" | claude -p \
                    --output-format=stream-json \
                    --verbose \
                    --model opus \
                    2>&1 | tee "$2"
                exit "${PIPESTATUS[1]:-0}"
            ' -- "$PROMPT_FILE" "$LOG_FILE"
        echo "$?" > "$CLAUDE_EXITCODE_FILE"
    ) &
    CLAUDE_PID=$!

    # Wait for Claude; interruptible by signal handler
    wait "$CLAUDE_PID" 2>/dev/null || true
    EXIT_CODE=$(cat "$CLAUDE_EXITCODE_FILE" 2>/dev/null || echo "1")
    rm -f "$CLAUDE_EXITCODE_FILE"
    CLAUDE_PID=""

    # Compute duration and outcome
    ITER_END=$(date '+%s')
    DURATION=$((ITER_END - ITER_START))
    case "$EXIT_CODE" in
        0)   OUTCOME="success" ;;
        124) OUTCOME="timeout" ;;
        *)   OUTCOME="error" ;;
    esac

    # Detect which beads issue was closed during this iteration
    CLOSED_AFTER_FILE=$(mktemp)
    bd list --status closed --json 2>/dev/null | \
        python3 -c "import sys,json; [print(i['id']) for i in json.load(sys.stdin)]" \
        2>/dev/null | sort > "$CLOSED_AFTER_FILE" || true
    BEADS_ISSUE_ID=$(comm -13 "$CLOSED_BEFORE_FILE" "$CLOSED_AFTER_FILE" | paste -sd ',' 2>/dev/null || echo "")
    rm -f "$CLOSED_BEFORE_FILE" "$CLOSED_AFTER_FILE"

    # Append JSON summary line to logs/summary.jsonl
    python3 -c "
import json
print(json.dumps({
    'iteration': $ITERATION,
    'mode': '$MODE',
    'start_time': '$START_TIME',
    'duration_s': $DURATION,
    'exit_code': $EXIT_CODE,
    'beads_issue_id': '$BEADS_ISSUE_ID',
    'outcome': '$OUTCOME',
    'log_file': '$LOG_FILE',
}))
" >> logs/summary.jsonl 2>/dev/null || true

    if [[ "$SHUTDOWN_REQUESTED" == "true" ]]; then
        break
    fi

    if [[ "$EXIT_CODE" -eq 124 ]]; then
        echo ""
        echo "!!! TIMEOUT: Iteration $ITERATION exceeded ${ITER_TIMEOUT}s limit !!!"
        echo "The claimed beads issue has been left in_progress for retry."
        echo "Press Enter to retry or Ctrl+C to stop."
        read -r
    elif [[ "$EXIT_CODE" -ne 0 ]]; then
        echo "Claude exited with code $EXIT_CODE. Pausing for review."
        echo "Press Enter to continue or Ctrl+C to stop."
        read -r
    fi

    echo "--- Iteration $ITERATION complete (${OUTCOME}, ${DURATION}s) ---"
done

print_summary
