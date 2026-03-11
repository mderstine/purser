# Loop Batch Mode

## Job To Be Done
Add a `--batch` flag to `purser-loop` that exits immediately on timeout or error instead of pausing for user input, enabling unattended execution from VS Code tasks, CI, and cron jobs.

## Requirements
- `uv run purser-loop --batch` (or `purser-loop build --batch`) suppresses all `input()` prompts
- On timeout: log the warning and **exit** rather than `Press Enter to retry`
- On non-zero Claude exit code: log the warning and **exit** rather than `Press Enter to continue`
- Exit code is non-zero when the loop terminates due to a timeout or error (distinguishable from clean "no ready work" exit)
- `--batch` is accepted in any position alongside existing args (e.g., `purser-loop 20 --batch`, `purser-loop plan --batch`)
- Non-batch behavior (default) is unchanged — interactive prompts still appear when stdin is a TTY
- Help text (`purser-loop --help` or `-h`) documents the flag

## Constraints
- Stdlib only — no new dependencies
- Must not affect the `status`, `sync`, `triage`, `changelog` single-shot modes (those have no interactive prompts)
- Backward-compatible: existing callers that don't pass `--batch` see no behavior change

## Notes
- The two `input()` calls are in `scripts/loop.py` around lines 498–505 (timeout) and 503–509 (non-zero exit)
- `EOFError` already exits cleanly when stdin is redirected (non-TTY pipe), so `--batch` just makes it explicit and avoids relying on EOF
- VS Code's integrated terminal IS a TTY, so without `--batch` the prompts would block the task panel waiting for user keypress
- CI usage: `uv run purser-loop --batch` in GitHub Actions would fail-fast on any Claude error
