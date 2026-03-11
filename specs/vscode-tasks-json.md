# VS Code Tasks Integration

## Job To Be Done
Give VS Code users one-click access to all Purser loop modes via `.vscode/tasks.json` so the build loop can be launched without leaving the editor.

## Requirements
- `.vscode/tasks.json` defines tasks for all Purser loop modes:
  - **Purser: Build (one iteration)** — `uv run purser-loop 1` — for manual stepping through one task
  - **Purser: Build Loop** — `uv run purser-loop --batch` — runs until no ready work or Ctrl+C
  - **Purser: Plan** — `uv run purser-loop plan 1` — one planning pass
  - **Purser: Status** — `uv run purser-loop status` — print iteration stats
  - **Purser: Sync** — `uv run purser-loop sync` — sync beads → GitHub Issues
- Tasks run in VS Code's integrated terminal (type: `shell`)
- Tasks are grouped under the `build` group; the default build task is `Purser: Build (one iteration)`
- Task labels follow `Purser: <Name>` convention for discoverability via `Tasks: Run Task`
- Problem matchers: use `$tsc` or `[]` (none) — loop output is not compiler errors
- `presentation.reveal`: `always` so the terminal panel opens automatically

## Constraints
- `--batch` flag must exist on `purser-loop` before this spec is buildable (see `loop-batch-mode.md`)
- `.vscode/tasks.json` must be valid JSON (no trailing commas, no comments)
- Working directory for all tasks: `${workspaceFolder}`
- No VS Code extension dependencies — only built-in task runner

## Notes
- VS Code tasks docs: https://code.visualstudio.com/docs/editor/tasks
- Default build task (Ctrl+Shift+B) should be the single-iteration build task for safe interactive use
- The full loop task should use `--batch` so it exits cleanly on errors rather than blocking the terminal
- `uv run purser-loop` is the entry point defined in `pyproject.toml [project.scripts]`
- The loop outputs to stdout/stderr; VS Code terminal captures it naturally
