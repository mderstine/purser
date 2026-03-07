# Purser Protocol

This project uses the Purser framework for autonomous, dependency-aware development. These instructions apply to every Copilot chat session in this workspace.

## How It Works

```
beads-pm agent → specs → task graph → beads-dev agent → implement → bd close → git commit
```

Each agent invocation gets fresh context. Beads replaces IMPLEMENTATION_PLAN.md as the
persistent state machine between iterations. The user writes specs; the framework breaks
them into dependency-ordered tasks and builds them one at a time.

## User's Role

The user directs by writing specs (`specs/`), setting quality gates (`AGENTS.md`), and
watching agent output. They intervene via `bd` CLI commands to re-prioritize, add blockers,
skip tasks, or inject urgent work.

## First-Time Setup

New to this project? Use the `init` prompt for guided setup:
- Open Copilot Chat and run the `init` prompt
- Or run `./init.sh` directly in the terminal
- This checks prerequisites, initializes beads, and configures GitHub integration

## VS Code Agent Invocations

Instead of running `loop.sh`, invoke agents directly in Copilot Chat:

| Goal | Invocation |
|------|-----------|
| Initialize project (first time) | Use the `init` prompt |
| Convert specs to task graph | Invoke `@beads-pm` agent |
| Implement one ready task | Invoke `@beads-dev` agent |
| Check project status | Run `bd prime` in terminal |
| Create a new issue | Use the `beads-create` skill |
| Triage/prioritize backlog | Use the `beads-triage` skill |
| Sync beads to GitHub Issues | `./loop.sh sync` in terminal |
| Triage GitHub Issues into specs | `./loop.sh triage` in terminal |

## Project Structure

- `PROMPT_plan.md` — Planning mode instructions (specs → beads issues)
- `PROMPT_build.md` — Build mode instructions (bd ready → implement → close)
- `AGENTS.md` — Operational guide loaded every iteration
- `loop.sh` — The Ralph Loop orchestrator (alternative to agent invocations)
- `specs/` — User's requirements documents (one per topic of concern)
- `scripts/` — GitHub integration scripts (gh-sync.sh, gh-triage.sh, gh-project.sh, gh-labels.sh)
- `.github/agents/` — VS Code agents (beads-pm, beads-dev)
- `.github/prompts/` — VS Code prompt files (build, plan, status, add-spec, create-issue)
- `.github/skills/` — Reusable skill definitions (beads-add-spec, beads-create, beads-triage, beads-workflow)
- `.github/instructions/beads-conventions.instructions.md` — Always-on conventions
- `.beads/` — Beads database (managed by bd, do not edit directly)

## Core Rule

Use `bd` (beads CLI) for ALL task tracking. Never use markdown TODOs, task lists, or external issue trackers. Beads is the single source of truth.

## Workflow

Before starting any work:

1. Check for ready work: `bd ready --json`
2. Claim your task atomically: `bd update <id> --claim --json`
3. Read the issue: `bd show <id> --json`
4. Implement the work described in the issue
5. Run validation (see Build & Validate below)
6. Commit on green with a descriptive message
7. Close the issue: `bd close <id> --reason "..." --json`

One task at a time. Do not pick up additional work until the current task is closed.

## Build & Validate

Run ALL quality gates before committing. Check `AGENTS.md` for the project's
actual commands:

```bash
uv run ruff check scripts/
uv run ruff format --check scripts/
uv run ty check scripts/
# uv run pytest tests/ -v
```

Do not commit code that fails validation. Fix issues and re-run until green.

## Beads CLI Quick Reference

```bash
bd ready --json                # Unblocked work — what to do next
bd show <id> --json            # Issue details + dependencies
bd update <id> --claim --json  # Claim work atomically
bd close <id> --reason "..."   # Complete work with context
bd create "Title" -p <0-4> -t <type> --json  # Create new issue
bd dep add <id> <blocker> --type blocks      # Add dependency
bd dep tree <id>               # Visualize dependency graph
bd dep cycles                  # Check for circular dependencies
bd prime                       # Session context summary
```

## Discovering New Work

If you find bugs, missing features, or tech debt while working on a task, file them as new issues linked to the current task. Do not fix them in the current iteration.

```bash
bd create "Discovered: <title>" \
    --description="<context>" \
    -p <priority> -t <type> \
    --deps discovered-from:<current-id> --json
```

## Issue Types and Priorities

Types: `bug`, `feature`, `task`, `epic`, `chore`

Priorities:
- 0: Critical (security, data loss, broken builds)
- 1: High (core features, important bugs)
- 2: Medium (standard features)
- 3: Low (polish, optimization)
- 4: Backlog (future ideas)

## Coding Standards

- Python 3.12+
- Type annotations on public APIs
- Tests for all new functionality
- Keep functions small and focused
- Study existing patterns before writing new code

## Rules

- Use `bd` for ALL task tracking — never markdown TODOs
- One task per agent invocation
- Always run backpressure (tests/lint/build) before committing
- Link discovered work with `discovered-from` dependencies
- Close issues with meaningful reasons

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

1. **File issues for remaining work** — Create beads issues for anything that needs follow-up
2. **Run quality gates** (if code changed) — Tests, linters, builds
3. **Update issue status** — Close finished work, update in-progress items
4. **PUSH TO REMOTE** — This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Verify** — All changes committed AND pushed
6. **Hand off** — Provide context for next session

**CRITICAL:** Work is NOT complete until `git push` succeeds. Never stop before pushing — that leaves work stranded locally.

## Important

- Always use `--json` flag when parsing bd output programmatically
- Link discovered work with `discovered-from` dependencies
- Check `bd ready` before asking "what should I work on?"
- Read AGENTS.md at the start of each session for project-specific patterns
