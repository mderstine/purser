#!/usr/bin/env python3
"""Purser Loop: Autonomous AI development with dependency-aware task tracking.

Cross-platform Python loop orchestrator. Uses only Python stdlib.

Usage:
    python3 scripts/loop.py              # Build mode, unlimited iterations
    python3 scripts/loop.py 20           # Build mode, max 20 iterations
    python3 scripts/loop.py plan         # Planning mode, unlimited
    python3 scripts/loop.py plan 5       # Planning mode, max 5 iterations
    python3 scripts/loop.py status       # Print iteration stats from logs/summary.jsonl
    python3 scripts/loop.py sync         # Sync beads issues to GitHub (single-shot)
    python3 scripts/loop.py triage       # Triage spec-candidate GitHub Issues (single-shot)
    python3 scripts/loop.py changelog    # Generate changelog from closed issues (single-shot)

Timeout:
    --timeout=VALUE         # Override per-iteration timeout in seconds (e.g. 900)
    PURSER_TIMEOUT=VALUE    # Same via environment variable
    Defaults: build=900s (15m), plan=600s (10m)

Batch mode (unattended):
    --batch                 # Exit immediately on timeout or error instead of pausing for input
                            # Useful for VS Code tasks, CI, and cron jobs

Agent backend:
    --agent=claude          # Use Claude Code CLI (default)
    --agent=vscode          # Use VS Code GitHub Copilot Agents (no claude CLI required)
    PURSER_AGENT=vscode     # Same via environment variable (flag takes precedence)
"""

import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cli_utils import setup_logging  # noqa: E402

logger = setup_logging(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

SIGNAL_GRACE = 30  # Seconds to wait for Claude to exit before force-kill
TIMEOUT_BUILD_DEFAULT = 900  # 15 minutes
TIMEOUT_PLAN_DEFAULT = 600  # 10 minutes

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent

# ─── Global state ────────────────────────────────────────────────────────────

_claude_proc: subprocess.Popen | None = None
_shutdown_requested = False
_iteration = 0


# ─── Signal handling ─────────────────────────────────────────────────────────


def _print_summary() -> None:
    logger.info("")
    logger.info("=== Loop finished after %d iteration(s) ===", _iteration)
    with contextlib.suppress(FileNotFoundError, subprocess.TimeoutExpired):
        subprocess.run(["bd", "prime"], capture_output=True, timeout=10)


def _terminate_process(proc: subprocess.Popen) -> None:
    """Terminate a subprocess tree, with grace period then force-kill."""
    # Try graceful termination
    try:
        if sys.platform != "win32":
            # Kill the entire process group on Unix
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        else:
            proc.terminate()
    except (ProcessLookupError, OSError):
        return

    # Wait for grace period
    try:
        proc.wait(timeout=SIGNAL_GRACE)
        logger.info("Claude exited cleanly.")
        return
    except subprocess.TimeoutExpired:
        pass

    # Force kill
    logger.warning("Grace period expired. Force-killing Claude...")
    try:
        if sys.platform != "win32":
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, OSError):
        pass


def _signal_handler(signum: int, _frame: object) -> None:
    global _shutdown_requested
    _shutdown_requested = True
    sig_name = signal.Signals(signum).name
    logger.info("")
    logger.info("=== Signal received (%s). Shutting down gracefully... ===", sig_name)

    if _claude_proc is not None and _claude_proc.poll() is None:
        logger.info(
            "Waiting for Claude (PID %d) to exit (grace: %ds)...",
            _claude_proc.pid,
            SIGNAL_GRACE,
        )
        _terminate_process(_claude_proc)

    _print_summary()
    sys.exit(130)


# ─── Argument parsing ────────────────────────────────────────────────────────


def _parse_args(argv: list[str]) -> tuple[str, int, str, bool, str, list[str]]:
    """Parse CLI arguments.

    Returns: (mode, max_iterations, timeout_override, batch, agent, passthrough_args)
    """
    mode = "build"
    max_iterations = 0
    timeout_override = ""
    batch = False
    agent = os.environ.get("PURSER_AGENT", "claude")
    passthrough_args: list[str] = []

    for arg in argv:
        if arg == "plan":
            mode = "plan"
        elif arg == "status":
            mode = "status"
        elif arg == "sync":
            mode = "sync"
        elif arg == "triage":
            mode = "triage"
        elif arg == "changelog":
            mode = "changelog"
        elif arg == "--batch":
            batch = True
        elif arg == "--dry-run":
            passthrough_args.append(arg)
        elif arg.startswith("--timeout="):
            timeout_override = arg.split("=", 1)[1]
        elif arg.startswith("--agent="):
            agent = arg.split("=", 1)[1]
        elif arg.isdigit():
            max_iterations = int(arg)

    return mode, max_iterations, timeout_override, batch, agent, passthrough_args


# ─── Single-shot modes ───────────────────────────────────────────────────────


def _run_status() -> None:
    """Print iteration stats from logs/summary.jsonl."""
    summary_file = REPO_ROOT / "logs" / "summary.jsonl"
    if not summary_file.exists():
        print("No iteration logs found. Run 'uv run purser-loop' to generate logs.")
        return

    entries = []
    for line in summary_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))

    if not entries:
        print("No iteration data found.")
        return

    total = len(entries)
    success = sum(1 for e in entries if e.get("outcome") == "success")
    fail = sum(1 for e in entries if e.get("outcome") == "error")
    timeout = sum(1 for e in entries if e.get("outcome") == "timeout")
    durations = [e.get("duration_s", 0) for e in entries]
    avg_dur = sum(durations) / len(durations) if durations else 0
    rate = (success / total * 100) if total else 0

    print("=== Purser Iteration Stats ===")
    print()
    print(f"  Total iterations:  {total}")
    print(f"  Success:           {success}")
    print(f"  Errors:            {fail}")
    print(f"  Timeouts:          {timeout}")
    print(f"  Success rate:      {rate:.0f}%")
    print(f"  Avg duration:      {avg_dur:.0f}s")
    print()
    print("--- Last 5 iterations ---")
    print(f"{'#':<5} {'Mode':<8} {'Outcome':<10} {'Duration':<10} {'Beads Issue':<20} {'Started'}")
    print(f"{'─' * 5} {'─' * 8} {'─' * 10} {'─' * 10} {'─' * 20} {'─' * 20}")
    for e in entries[-5:]:
        dur = f"{e.get('duration_s', 0)}s"
        print(
            f"{e.get('iteration', '?'):<5} "
            f"{e.get('mode', '?'):<8} "
            f"{e.get('outcome', '?'):<10} "
            f"{dur:<10} "
            f"{e.get('beads_issue_id', ''):<20} "
            f"{e.get('start_time', '?')}"
        )


def _run_delegate(mode: str, passthrough_args: list[str]) -> None:
    """Delegate to a Python script for single-shot modes."""
    script_map = {
        "sync": "gh_sync.py",
        "triage": "gh_triage.py",
        "changelog": "gh_changelog.py",
    }
    script = SCRIPTS_DIR / script_map[mode]
    label = {"sync": "GitHub Sync", "triage": "Issue Triage", "changelog": "Changelog"}[mode]
    logger.info("=== Purser: %s ===", label)
    result = subprocess.run([sys.executable, str(script), *passthrough_args])
    sys.exit(result.returncode)


# ─── Pre-flight checks ───────────────────────────────────────────────────────


def _preflight_checks(*, agent: str = "claude") -> None:
    """Run pre-flight checks. Exits on fatal errors, warns on non-fatal issues."""
    errors = 0

    # 1. bd CLI available (always required)
    if shutil.which("bd") is None:
        logger.error("bd (beads) CLI not found. Install with: npm install -g @beads/bd")
        errors += 1

    # 2. Agent CLI available
    if agent == "claude":
        if shutil.which("claude") is None:
            logger.error("claude CLI not found. Install Claude Code to continue.")
            logger.error("Alternatively, run with --agent=vscode to use VS Code Copilot.")
            errors += 1
    elif agent == "vscode":
        if shutil.which("code") is None:
            logger.warning(
                "'code' CLI not found on PATH — VS Code may not be installed "
                "or shell integration not enabled."
            )
            logger.warning(
                "The loop will still write session files; open them manually in VS Code Copilot."
            )
    else:
        logger.error("Unknown agent: %r. Supported values: claude, vscode", agent)
        errors += 1

    # 3. beads database accessible
    if errors == 0:
        try:
            result = subprocess.run(["bd", "prime"], capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                logger.error("bd prime failed — beads database may be corrupted or inaccessible.")
                logger.error("Run 'bd prime' manually to see the error.")
                errors += 1
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.error("bd prime failed — could not execute bd command.")
            errors += 1

    if errors > 0:
        logger.error("")
        logger.error("Pre-flight failed with %d error(s). Fix the issues above and retry.", errors)
        sys.exit(1)

    # 4. Warn if on main/master branch (non-fatal)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        branch = result.stdout.strip() if result.returncode == 0 else "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        branch = "unknown"

    if branch in ("main", "master"):
        logger.warning("Running on '%s' branch. Consider working on a feature branch.", branch)

    # 5. Warn about uncommitted changes (non-fatal)
    try:
        diff_result = subprocess.run(["git", "diff", "--quiet"], capture_output=True, timeout=5)
        cached_result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], capture_output=True, timeout=5
        )
        if diff_result.returncode != 0 or cached_result.returncode != 0:
            logger.warning("Uncommitted changes detected — these may conflict with loop commits:")
            status = subprocess.run(
                ["git", "status", "--short"], capture_output=True, text=True, timeout=5
            )
            if status.returncode == 0:
                for line in status.stdout.splitlines()[:10]:
                    logger.warning("  %s", line)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


# ─── Beads helpers ────────────────────────────────────────────────────────────


def _get_closed_issue_ids() -> set[str]:
    """Get the set of currently-closed beads issue IDs."""
    try:
        result = subprocess.run(
            ["bd", "list", "--status", "closed", "--json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            issues = json.loads(result.stdout)
            return {i["id"] for i in issues}
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return set()


def _get_ready_count() -> int:
    """Get the count of ready (unblocked) beads issues."""
    try:
        result = subprocess.run(
            ["bd", "ready", "--json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return len(json.loads(result.stdout))
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return 0


# ─── VS Code executor ─────────────────────────────────────────────────────────


def _run_vscode_executor(
    mode: str,
    prompt_file: Path,
    logs_dir: Path,
    iteration: int,
    iter_timeout: int,
    batch: bool,
) -> tuple[int, bool]:
    """Run one iteration using VS Code GitHub Copilot Agents.

    Writes a session context file for the user to open in VS Code Copilot.
    In batch mode, exits immediately after writing the file (single-shot).
    In interactive mode, polls for a sentinel file or waits for user input.

    Returns: (exit_code, timed_out)
    """
    # Gather project context from bd prime
    bd_prime_output = "(bd prime unavailable)"
    try:
        result = subprocess.run(["bd", "prime"], capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            bd_prime_output = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Build session file content
    prompt_content = prompt_file.read_text(encoding="utf-8")
    session_file = logs_dir / f"vscode-session-{iteration}.md"
    sentinel_file = logs_dir / f"vscode-done-{iteration}"

    session_content = (
        f"---\n"
        f"iteration: {iteration}\n"
        f"mode: {mode}\n"
        f"prompt: {prompt_file.name}\n"
        f"sentinel: {sentinel_file.name}\n"
        f"---\n\n"
        f"# Purser VS Code Session — Iteration {iteration}\n\n"
        f"## How to use this file\n\n"
        f"1. Open this file in VS Code Copilot agent mode\n"
        f"2. The agent will read the prompt below and execute one iteration\n"
        f"3. When the agent finishes, create the sentinel file to signal completion:\n"
        f"   ```\n"
        f"   touch {sentinel_file}\n"
        f"   ```\n\n"
        f"## Project Context (bd prime)\n\n"
        f"```\n{bd_prime_output}\n```\n\n"
        f"## Prompt\n\n"
        f"{prompt_content}\n"
    )
    session_file.write_text(session_content, encoding="utf-8")
    logger.info("VS Code session file: %s", session_file)
    logger.info("Sentinel (create when done): %s", sentinel_file)

    # Try to open in VS Code if available
    if shutil.which("code"):
        try:
            subprocess.Popen(["code", str(session_file)])
            logger.info("Opened session file in VS Code.")
        except OSError:
            pass

    # Batch mode: write file and signal caller to stop the loop
    if batch:
        logger.info(
            "Batch mode: session file written. "
            "Open it in VS Code Copilot to run the agent, then trigger the next iteration."
        )
        return 0, False

    # Interactive mode: race between sentinel file appearing and user pressing Enter
    logger.info("")
    logger.info("Waiting for VS Code Copilot agent to complete...")
    logger.info("  Option 1: Create sentinel file when done: touch %s", sentinel_file)
    logger.info("  Option 2: Press Enter here to signal completion manually.")

    done_event = threading.Event()

    def _poll_sentinel() -> None:
        deadline = time.time() + iter_timeout
        while time.time() < deadline:
            if sentinel_file.exists() or done_event.is_set():
                done_event.set()
                return
            time.sleep(2)
        done_event.set()

    def _wait_input() -> None:
        with contextlib.suppress(EOFError, KeyboardInterrupt, OSError):
            input()
        done_event.set()

    threading.Thread(target=_poll_sentinel, daemon=True).start()
    threading.Thread(target=_wait_input, daemon=True).start()

    start = time.time()
    done_event.wait(timeout=iter_timeout + 1)
    elapsed = time.time() - start

    timed_out = elapsed >= iter_timeout and not sentinel_file.exists()
    exit_code = 124 if timed_out else 0

    if sentinel_file.exists():
        logger.info("Sentinel file detected — agent session complete.")
    elif not timed_out:
        logger.info("Agent session signalled complete.")

    return exit_code, timed_out


# ─── Main loop ────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    global _claude_proc, _shutdown_requested, _iteration

    if argv is None:
        argv = sys.argv[1:]

    mode, max_iterations, timeout_override, batch, agent, passthrough_args = _parse_args(argv)

    # Install signal handlers (Unix only — Windows doesn't support SIGTERM handler well)
    signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _signal_handler)

    # ─── Single-shot modes ───────────────────────────────────────────────
    if mode == "status":
        _run_status()
        return

    if mode in ("sync", "triage", "changelog"):
        _run_delegate(mode, passthrough_args)
        return

    # ─── Resolve timeout ─────────────────────────────────────────────────
    if timeout_override:
        iter_timeout = int(timeout_override)
    else:
        env_timeout = os.environ.get("PURSER_TIMEOUT")
        if env_timeout:
            iter_timeout = int(env_timeout)
        elif mode == "plan":
            iter_timeout = TIMEOUT_PLAN_DEFAULT
        else:
            iter_timeout = TIMEOUT_BUILD_DEFAULT

    prompt_file = REPO_ROOT / f"PROMPT_{mode}.md"
    if not prompt_file.exists():
        logger.error("Error: %s not found", prompt_file.name)
        sys.exit(1)

    # ─── Pre-flight ──────────────────────────────────────────────────────
    _preflight_checks(agent=agent)

    logger.info("=== Purser Loop ===")
    logger.info("Mode: %s", mode)
    logger.info("Agent: %s", agent)
    logger.info("Prompt: %s", prompt_file.name)
    logger.info("Max iterations: %s", max_iterations or "unlimited")
    logger.info("Iteration timeout: %ds", iter_timeout)
    if batch:
        logger.info("Batch mode: enabled (exit on timeout/error)")
    logger.info("========================")

    # Ensure logs directory exists
    logs_dir = REPO_ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)

    # ─── Loop ────────────────────────────────────────────────────────────
    while True:
        _iteration += 1

        if max_iterations > 0 and _iteration > max_iterations:
            logger.info("Reached max iterations (%d). Stopping.", max_iterations)
            break

        if _shutdown_requested:
            break

        # Capture iteration start time
        iter_start = time.time()
        start_time = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S")
        log_file = logs_dir / f"{mode}-{start_time}-iter-{_iteration}.log"

        logger.info("")
        logger.info("--- Iteration %d (%s) ---", _iteration, start_time)

        # Check if there's work to do (build mode only)
        if mode == "build":
            ready_count = _get_ready_count()
            if ready_count == 0:
                logger.info("No ready work found. All tasks complete or blocked.")
                logger.info(
                    "Run 'uv run purser-loop plan' to generate new tasks, "
                    "or check blockers with 'bd list --status open'."
                )
                break
            logger.info("Ready work: %d issue(s)", ready_count)

        # Snapshot closed issues before this iteration
        closed_before = _get_closed_issue_ids()

        exit_code = 1
        timed_out = False

        if agent == "vscode":
            exit_code, timed_out = _run_vscode_executor(
                mode=mode,
                prompt_file=prompt_file,
                logs_dir=logs_dir,
                iteration=_iteration,
                iter_timeout=iter_timeout,
                batch=batch,
            )
            # In batch mode the vscode executor writes one session file then returns;
            # break the loop so the VS Code task exits cleanly.
            if batch:
                logger.info("--- Iteration %d complete (vscode-batch) ---", _iteration)
                break
        else:
            # Run Claude with timeout
            prompt_content = prompt_file.read_text(encoding="utf-8")
            claude_cmd = [
                "claude",
                "-p",
                "--output-format=stream-json",
                "--verbose",
                "--model",
                "opus",
            ]

            try:
                # Create process group on Unix for clean group termination
                kwargs: dict = {}
                if sys.platform != "win32":
                    kwargs["start_new_session"] = True

                with open(log_file, "w", encoding="utf-8") as log_fh:
                    _claude_proc = subprocess.Popen(
                        claude_cmd,
                        stdin=subprocess.PIPE,
                        stdout=log_fh,
                        stderr=subprocess.STDOUT,
                        text=True,
                        **kwargs,
                    )
                    # Feed the prompt via stdin
                    try:
                        if _claude_proc.stdin is not None:
                            _claude_proc.stdin.write(prompt_content)
                            _claude_proc.stdin.close()
                    except BrokenPipeError:
                        pass

                    try:
                        _claude_proc.wait(timeout=iter_timeout)
                        exit_code = _claude_proc.returncode
                    except subprocess.TimeoutExpired:
                        timed_out = True
                        exit_code = 124
                        _terminate_process(_claude_proc)
            except FileNotFoundError:
                logger.error("ERROR: claude CLI not found during execution.")
                exit_code = 1
            finally:
                _claude_proc = None

        # Compute duration and outcome
        duration = int(time.time() - iter_start)
        if timed_out:
            outcome = "timeout"
        elif exit_code == 0:
            outcome = "success"
        else:
            outcome = "error"

        # Detect which beads issue was closed during this iteration
        closed_after = _get_closed_issue_ids()
        newly_closed = closed_after - closed_before
        beads_issue_id = ",".join(sorted(newly_closed))

        # Append JSON summary line to logs/summary.jsonl
        summary_entry = {
            "iteration": _iteration,
            "mode": mode,
            "start_time": start_time,
            "duration_s": duration,
            "exit_code": exit_code,
            "beads_issue_id": beads_issue_id,
            "outcome": outcome,
            "log_file": str(log_file),
        }
        summary_file = logs_dir / "summary.jsonl"
        try:
            with open(summary_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(summary_entry) + "\n")
        except OSError:
            pass

        if _shutdown_requested:
            break

        if timed_out:
            logger.info("")
            logger.warning(
                "!!! TIMEOUT: Iteration %d exceeded %ds limit !!!", _iteration, iter_timeout
            )
            logger.info("The claimed beads issue has been left in_progress for retry.")
            if batch:
                logger.info("Batch mode: exiting on timeout.")
                break
            print("Press Enter to retry or Ctrl+C to stop.")
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                break
        elif exit_code != 0:
            logger.warning("Agent exited with code %d. Pausing for review.", exit_code)
            if batch:
                logger.info("Batch mode: exiting on error.")
                break
            print("Press Enter to continue or Ctrl+C to stop.")
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                break

        logger.info("--- Iteration %d complete (%s, %ds) ---", _iteration, outcome, duration)

    _print_summary()


if __name__ == "__main__":
    main()
