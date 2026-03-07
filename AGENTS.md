# Operational Guide

This file is loaded at the start of every Ralph Loop iteration.
It contains project-specific patterns, constraints, and learnings.

## Build & Validate

<!-- TEMPLATE: Replace these with your project's actual build commands -->
```bash
# Run tests
# python -m pytest tests/ -v

# Type checking
# python -m mypy src/ --strict

# Lint
# python -m ruff check src/ tests/

# Build
# python -m build
```

> **Note:** The commands above are examples for a typical Python project.
> Uncomment and customize them for your project's toolchain.

## Beads CLI Reference

```bash
bd ready --json              # Unblocked work — what to do next
bd show <id> --json          # Issue details + dependencies
bd update <id> --claim       # Claim work atomically
bd close <id> --reason "..." # Complete work
bd create "Title" -p <0-4> -t <type> --deps discovered-from:<id> --json
bd dep tree <id>             # Visualize dependency graph
bd dolt commit               # Commit pending Dolt changes (batch mode only)
bd dolt push                 # Push beads to remote
bd prime                     # Session context summary
```

## Coding Standards

- Python 3.12+
- Type annotations on public APIs
- Tests for all new functionality
- Keep functions small and focused

## Known Patterns & Gotchas

<!-- Add learnings here as you discover them -->
<!-- Example: "bd dolt push required after git push to keep remote beads in sync" -->

<!-- BEGIN BEADS INTEGRATION -->
## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- Dependency-aware: Track blockers and relationships between issues
- Git-friendly: Dolt-powered version control with native sync
- Agent-optimized: JSON output, ready work detection, discovered-from links
- Prevents duplicate tracking systems and confusion

### Quick Start

**Check for ready work:**

```bash
bd ready --json
```

**Create new issues:**

```bash
bd create "Issue title" --description="Detailed context" -t bug|feature|task -p 0-4 --json
bd create "Issue title" --description="What this issue is about" -p 1 --deps discovered-from:bd-123 --json
```

**Claim and update:**

```bash
bd update <id> --claim --json
bd update bd-42 --priority 1 --json
```

**Complete work:**

```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task atomically**: `bd update <id> --claim`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   - `bd create "Found bug" --description="Details about what was found" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`

### Auto-Sync

bd automatically commits each write to Dolt history (default mode):

- Use `bd dolt push`/`bd dolt pull` for remote sync
- No manual `bd sync` — that command does not exist
- In `--dolt-auto-commit batch` mode only: use `bd dolt commit` to flush pending changes

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems

For more details, see README.md and docs/QUICKSTART.md.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

<!-- END BEADS INTEGRATION -->
