---
applyTo: "**"
---

# Beads Conventions

These conventions apply to all files in this project. Follow them in every Copilot session.

## Task Tracking

- **Use `bd` for everything.** Never use markdown TODOs, task lists, or GitHub issues for tracking work.
- **Before any work:** `bd ready --json` → pick highest priority → `bd update <id> --status=in_progress`
- **After any work:** `bd close <id> --reason "<what was done and how>"`
- **Discovered new work?** File it immediately: `bd create --title="Discovered: ..." --deps discovered-from:<current-id>` — do NOT fix it in the current iteration

## bd CLI Conventions

```bash
# Always use --json for programmatic output
bd ready --json
bd show <id> --json
bd update <id> --status=in_progress --json
bd close <id> --reason "..." --json

# Create issues with full context
bd create \
    --title="<Verb + Object: Fix crash, Add export, Refactor parser>" \
    --description="<Why this matters, not just what to do>" \
    --type=task|bug|feature|epic|chore \
    --priority=<0-4> \
    --json

# Dependencies
bd dep add <blocked-id> <blocker-id>          # B cannot start until A is done
bd dep add <child-id> <epic-id>               # Subtask of an epic
bd dep add <id> <origin-id> --type discovered-from  # Found while working on origin
bd dep cycles                                  # Must show no cycles before committing
```

## Commit Message Format

```
<type>: <short description>

<body explaining why, not what — optional for trivial changes>

Closes: <issue-id>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

Examples:
```
feat: add bd dolt commit to batch-mode flush workflow

Closes: purser-abc

fix: handle empty database in bd ready path

The ready command panicked when no issues existed. Added nil check
before iterating dependency graph.

Closes: purser-xyz
```

## Issue Priorities

| Priority | Label | When |
|----------|-------|------|
| 0 | Critical | Security, data loss, broken builds |
| 1 | High | Core features, blocks other work |
| 2 | Medium | Standard work (default) |
| 3 | Low | Polish, optimization |
| 4 | Backlog | Future ideas |

## Issue Types

| Type | When |
|------|------|
| `bug` | Something is broken or produces wrong results |
| `feature` | New capability |
| `task` | Implementation work (refactor, migration, test coverage) |
| `chore` | Dependencies, tooling, maintenance |
| `epic` | Large feature broken into subtasks |

## Coding Standards

- Python 3.12+, type annotations on public APIs
- Tests for all new functionality
- Functions should be small and focused
- Study existing patterns before writing new code
- Match the style already in place — do not introduce new patterns for one-off needs
