# Ralph-Beads Framework

Unified agentic AI development protocol combining Geoffrey Huntley's Ralph Loop
with Beads (`bd`) dependency-aware issue tracking.

## How It Works

```
loop.sh → PROMPT.md → Claude Code → bd ready → implement → bd close → git commit → loop restarts
```

Each iteration gets fresh context. Beads replaces IMPLEMENTATION_PLAN.md as the
persistent state machine between loops. The user writes specs, the framework
breaks them into dependency-ordered tasks, and builds them one at a time.

## User's Role

The user directs by writing specs (`specs/`), setting quality gates (`AGENTS.md`),
and tuning prompts (`PROMPT_*.md`). They watch the loop and intervene via `bd` CLI
commands (re-prioritize, add blockers, skip tasks, inject urgent work).

## Key Commands

```bash
./loop.sh              # Build mode (default)
./loop.sh plan         # Planning mode (specs → task graph)
./loop.sh plan 5       # Planning mode, max 5 iterations
./loop.sh 20           # Build mode, max 20 iterations
./loop.sh status       # Print iteration stats from logs/summary.jsonl
./loop.sh sync         # Sync beads issues to GitHub Issues/Project board
./loop.sh triage       # Triage spec-candidate GitHub Issues into specs/
```

Both `sync` and `triage` support `--dry-run` for preview.

## Files

- `PROMPT_plan.md` — Planning mode prompt (specs → beads issues)
- `PROMPT_build.md` — Build mode prompt (bd ready → implement → close)
- `AGENTS.md` — Operational guide loaded every iteration
- `loop.sh` — The Ralph Loop orchestrator
- `specs/` — User's requirements documents (one per topic of concern)
- `scripts/` — GitHub integration scripts (gh-sync.sh, gh-triage.sh, gh-project.sh, gh-labels.sh)
- `.beads/` — Beads database (managed by bd, don't edit)

## Rules

- Use `bd` for ALL task tracking — never markdown TODOs
- One task per loop iteration
- Always run backpressure (tests/lint/build) before committing
- Link discovered work with `discovered-from` dependencies
- Close issues with meaningful reasons
