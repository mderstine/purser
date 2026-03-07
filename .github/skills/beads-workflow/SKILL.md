# /beads-workflow

Execute the standard Purser claim-implement-close cycle for one task. This is the core build loop procedure used by the beads-dev agent and can be invoked directly for a single work iteration.

## Steps

### 1. Find ready work

```bash
bd ready --json
```

Pick the highest-priority issue from the results. If a specific issue ID was provided, use that instead (after verifying it's not blocked).

### 2. Claim the issue

```bash
bd update <id> --status=in_progress --json
bd show <id> --json
```

Read the full issue: title, description, and any linked issues. Understand what done looks like before writing a single line.

### 3. Implement

- Study related code before writing anything new
- Follow existing patterns and conventions from `AGENTS.md`
- Implement only what the issue describes — nothing more

### 4. Validate (backpressure)

Run the project's quality gates from `AGENTS.md`:

```bash
uv run ruff check scripts/
uv run ruff format --check scripts/
uv run ty check scripts/
# uv run pytest tests/ -v
```

If any gate fails: read the error, fix it, re-run. Do not commit failing code.

### 5. Discover new work (if any)

If you find bugs, missing features, or tech debt while working — file them, do NOT fix them now:

```bash
bd create \
    --title="Discovered: <clear title>" \
    --description="<what was found and why it matters>" \
    --type=bug|task|feature \
    --priority=<0-4> \
    --deps discovered-from:<current-id>
```

### 6. Commit

Stage only relevant files and commit on green:

```bash
git add <specific files>
git commit -m "<descriptive message>

Closes: <issue-id>"
```

### 7. Close

```bash
bd close <id> --reason "<what was implemented and how>" --json
```

The close reason should be useful to future agents reading the history.

## Rules

- **One task only** — do not pick up another issue after closing
- **Claim before coding** — always mark in_progress first
- **No green, no commit** — validation gates are mandatory
- **File, don't fix** — discovered issues go into beads, not this iteration
- **Close with context** — the reason field is not a formality
