# Purser consumer-repo setup

This is the canonical guide for integrating **Purser** into another repository.

Use this when Purser is being adopted as a workflow framework inside a repo whose real work may be software delivery, documentation, research, data analysis, data discovery, or other scoped project work.

## Purser's role

Purser is:
- a **project-agnostic orchestration framework**
- a planner / executor / reviewer workflow layer
- tooling used to advance the repo's real work

Purser is **not**:
- the product of the consumer repo
- the main feature being built in the consumer repo, unless explicitly requested
- a shared/server Beads deployment manager

## Preconditions

The following must already be available on `PATH`:
- `uv`
- `bd`
- `dolt`
- `pi`

Pi should already be authenticated/configured for the models the repo intends to use.

## Required setup steps

### 1. Install Purser

Preferred installation:

```bash
uv tool install git+https://github.com/mderstine/purser.git
```

Verify:

```bash
purser --help
```

### 2. Initialize local embedded Beads in the repo

From the consumer repo root:

```bash
bd init
```

Use only **repo-local embedded** Beads storage.

Do **not** use:
- `bd init --server`
- `bd init --shared-server`
- `bd --global`

### 3. Initialize Purser in the repo

From the consumer repo root:

```bash
purser init
```

This creates:
- `.purser.toml`
- `.purser/prompts/planner.md`
- `.purser/prompts/executor.md`
- `.purser/prompts/reviewer.md`

### 4. Customize `.purser.toml`

Edit `.purser.toml` for the consumer repo's real validation commands and preferred models.

Typical fields to customize:
- `[project]`
- `[gates]`
- `[roles]`
- `[roles.models]`
- `[beads]`

Recommended defaults:

```toml
[beads]
auto_commit = "on"

[roles]
timeout_seconds = 240
```

For Python repos using `uv`, prefer:

```toml
[gates]
lint = "uv run ruff check . && uv run ruff format --check ."
types = "uv run pyright"
tests = "uv run pytest -x --tb=short"
timeout_seconds = 600
```

Do not invent gates if the repo already defines them clearly elsewhere.

### 5. Create or update `AGENTS.md`

Create `AGENTS.md` if missing, or append to it if present.

Add a dedicated Purser section that makes all of the following explicit:
- Purser is a planning / execution / review framework used in this repo.
- Purser is **not** the repo's product or primary deliverable unless explicitly requested.
- The real goal is to advance the repo's actual work.
- That work may include software development, documentation, research, data analysis, data discovery, or other repo-native deliverables.
- Specs should describe the repo's real work, not Purser development work unless explicitly requested.
- Use repo-local embedded Beads storage only.

Recommended section:

```md
## Purser workflow

This repository uses **Purser** as a planning / execution / review framework.

Important:
- **Purser is not the product or primary deliverable of this repository.**
- The actual goal is to advance this repository's real work.
- That work may include software development, bug fixing, documentation, research, data analysis, data discovery, or other scoped deliverables relevant to this repo.
- Use Purser only as the orchestration layer for that work.

When working in this repo:
- Treat specs as descriptions of the repository's actual work, not Purser development work unless explicitly requested.
- Use Purser to decompose specs into Beads, execute scoped work, run gates or other validation where applicable, and review outcomes.
- Keep scope focused on the requested deliverable in this repository.
- Respect this repo's actual conventions, workflows, validation methods, and success criteria.
- Use repo-local embedded Beads storage only; do not use shared or server-backed Beads databases.

Typical workflow:
1. Write or refine a spec for the desired work in this repo.
2. Have the director (human driver) review and approve the refined spec / planning approach.
3. Only then use Purser to generate the bead graph and plan the work into atomic beads.
4. Execute one bead at a time against this repo's actual artifacts (code, data, docs, analysis, etc.).
5. Review for accuracy, atomicity, and elegance/fitness to the repo's goals.
6. Record validation results for completed work.
```

### 6. Configure Pi prompt-template integration

To make Purser prompts available as Pi slash commands without duplicating prompt files, create a project-local Pi settings file that points at the canonical Purser prompt directory.

Canonical prompt directory:

```text
.purser/prompts/
```

Create:

```text
.pi/settings.json
```

Use:

```json
{
  "prompts": ["../.purser/prompts"]
}
```

Example prompt filenames and slash commands:

```text
.purser/prompts/purser-planner-intake-spec.md  -> /purser-planner-intake-spec
.purser/prompts/purser-exec-build.md           -> /purser-exec-build
.purser/prompts/purser-exec-build-all.md       -> /purser-exec-build-all
```

After changing Pi settings, reload Pi:

```text
/reload
```

Do not duplicate prompts under `.pi/prompts/` unless intentionally creating Pi-only overrides.

If `.pi/settings.json` already exists, merge the `prompts` entry carefully.

### 7. Ignore local/runtime files where appropriate

Usually add the following to `.gitignore` if missing:

```gitignore
.beads/
.purser/
.purser.toml
VALIDATION.md
```

Adapt to the consumer repo's actual workflow.

### 8. Verify setup

Run:

```bash
purser doctor
```

A correct setup should report:
- binaries found
- config present
- prompt files present
- repo-local embedded Beads storage

## Acceptance criteria for a successful adoption

Consumer-repo adoption is complete only if all of these are true:
- `purser doctor` succeeds
- the repo uses local embedded Beads storage
- `.purser.toml` reflects the repo's real gates and preferred models
- `AGENTS.md` contains a clear Purser section
- `.pi/settings.json` points Pi prompt templates at `.purser/prompts`
- Purser prompt templates are available as Pi slash commands after `/reload`

## Suggested next smoke test

After setup, a small validation sequence is:

```bash
purser planner-intake-spec specs/example.md --synthesize false
# director/human reviews the spec + planning approach
purser planner-plan specs/example.md
purser exec-build
```

Only run `purser planner-plan` after director/human review of the spec/planning approach. Use a deliberately tiny, safe spec for the first live run.
