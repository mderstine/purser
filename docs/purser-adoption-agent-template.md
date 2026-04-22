# Purser adoption template for a generic coding agent

Use this prompt when you want a general-purpose coding agent to set up **purser** in the current repo as a supporting workflow framework.

---

You are setting up **purser** in the user's current repository. Purser is not the product being built; it is the orchestration framework used to plan, execute, and review the repo's actual work.

## Goal

Make the current repository Purser-enabled using best practices for a local developer workflow.

## Important constraints

- Work in the **current repo only**.
- Treat this repo as the product repo; **purser is just tooling**.
- Use a **repo-local embedded Beads/Dolt database** only.
- Do **not** configure Beads shared-server mode or external server mode.
- Prefer `uv`-based commands in configured gates when the repo uses Python tooling.
- Do not guess the project's lint/type/test commands if they are discoverable from repo files.
- If the repo already has relevant tooling/config, adapt to it instead of overwriting blindly.
- Minimize unrelated edits.

## Required outcomes

1. `purser` is available to the user via `uv tool` or another explicit, documented mechanism.
2. The current repo is initialized with local Beads (`bd init`, embedded mode only) unless it is already correctly initialized.
3. The current repo has Purser config and prompt files.
4. `.purser.toml` is customized for this repo's actual gates and preferred models.
5. `AGENTS.md` is created or updated with a clearly labeled Purser section explaining Purser's role in the repo.
6. Pi prompt templates are wired so Purser prompts are available as Pi slash commands without duplicating prompt files.
7. Local/runtime artifacts are ignored appropriately in `.gitignore`.
8. `purser doctor` succeeds.
9. Provide a short summary of what was changed and any follow-up the user should know.

## Suggested workflow

### 1. Inspect the repo first

Determine:
- repo root
- language / runtime
- whether it uses Python, Node, Rust, Go, etc.
- existing lint/type/test commands
- whether `uv`, `ruff`, `pyright`, `pytest`, `pnpm`, `cargo`, etc. are already used
- whether `.gitignore` already contains entries for local tooling

Look at files such as:
- `pyproject.toml`
- `package.json`
- `Cargo.toml`
- `go.mod`
- `Makefile`
- `README.md`
- existing CI config

### 2. Ensure Purser is installed for the user

Preferred install method:

```bash
uv tool install git+https://github.com/mderstine/purser.git
```

If already installed, verify availability instead of reinstalling blindly.

### 3. Initialize local Beads in the repo

If the repo does not already have a valid local embedded Beads setup, run:

```bash
bd init
```

Do **not** use:
- `bd init --server`
- `bd init --shared-server`
- `bd --global`

If Beads is already initialized, verify that it is local embedded mode.

### 4. Initialize Purser in the repo

Run:

```bash
purser init
```

If config already exists, inspect before replacing anything. Prefer targeted edits over destructive rewrites.

### 5. Customize `.purser.toml`

Set:
- `[project]` name/language
- `[gates]` based on the repo's real commands
- `[roles.models]` to reasonable defaults or the user's requested models
- `[roles].timeout_seconds` to a sane default like `240` or `600`
- `[beads].auto_commit = "on"`

Best-practice guidance:
- For Python repos using `uv`, prefer:
  - `uv run ruff check . && uv run ruff format --check .`
  - `uv run pyright`
  - `uv run pytest -x --tb=short`
- For Node repos, prefer the repo's actual package-manager scripts
- For Rust repos, prefer `cargo fmt --check`, `cargo clippy`, `cargo test`
- For Go repos, prefer `go test ./...` and the repo's real lint command

Do not invent gates if the repo already defines them clearly.

### 6. Create or update `AGENTS.md`

Create `AGENTS.md` if it does not exist, or append to it if it does.

Add a clearly labeled section such as `## Purser workflow` that makes these points explicit:
- Purser is a planning / execution / review framework used in this repo.
- **Purser is not the repo's product or primary deliverable unless explicitly requested.**
- The real goal is to advance the repo's actual work.
- That work may include software development, bug fixing, documentation, research, data analysis, data discovery, or other scoped deliverables relevant to this repo.
- Specs should describe the repo's real work, not Purser development work unless explicitly requested.
- Use Purser as orchestration around the repo's work, not as the work itself.
- Use repo-local embedded Beads storage only.

A good section to append is:

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
2. Use Purser to plan the work into atomic beads.
3. Execute one bead at a time against this repo's actual artifacts (code, data, docs, analysis, etc.).
4. Review for accuracy, atomicity, and elegance/fitness to the repo's goals.
5. Record validation results for completed work.
```

### 7. Configure Pi prompt-template integration

To make Purser prompts available as Pi slash commands without duplicating files, create a project-local Pi settings file that points at the canonical Purser prompt directory.

Use Purser's canonical prompt directory:

```text
.purser/prompts/
```

Create:

```text
.pi/settings.json
```

Set its contents to:

```json
{
  "prompts": ["../.purser/prompts"]
}
```

Ensure each prompt filename matches the desired Pi slash command name. For example:

```text
.purser/prompts/purser-planner-intake-spec.md
.purser/prompts/purser-exec-build.md
.purser/prompts/purser-exec-build-all.md
```

These become:

```text
/purser-planner-intake-spec
/purser-exec-build
/purser-exec-build-all
```

After setup, tell the user to reload Pi with:

```text
/reload
```

Do not create duplicate copies under `.pi/prompts/` unless you intentionally want Pi-only overrides.

If the repo already has `.pi/settings.json`, merge the `prompts` entry carefully instead of overwriting unrelated settings.

### 8. Ensure local/runtime files are ignored

Add appropriate `.gitignore` entries if missing. Usually:

```gitignore
.beads/
.purser/
.purser.toml
VALIDATION.md
```

Only add what makes sense for the repo and local workflow.

### 9. Verify health

Run:

```bash
purser doctor
```

Success means:
- required binaries are found
- config exists
- prompts exist
- Beads storage is local embedded mode

### 10. Report final status

Provide:
- files created/edited
- detected gate commands
- configured models
- whether Beads was initialized or reused
- result of `purser doctor`
- any manual follow-up needed

## Acceptance criteria for your work

Your setup is complete only if all of these are true:
- `purser doctor` exits successfully
- the repo uses local embedded Beads storage
- `.purser.toml` reflects the repo's actual gates
- prompt files exist
- `AGENTS.md` contains a clear Purser section stating that Purser is framework/tooling rather than the repo's primary product
- `.pi/settings.json` points Pi prompt templates at `.purser/prompts`
- the user can access Purser prompt templates as Pi slash commands after `/reload`
- `.gitignore` protects local runtime files where appropriate
- your final report is concise and explicit

## Example final report format

- Installed/verified: `purser`, `bd`, `dolt`, `pi`
- Initialized/reused local Beads: yes/no
- Wrote/updated: `.purser.toml`, prompt files, `AGENTS.md`, `.pi/settings.json`, `.gitignore`
- Configured gates:
  - lint: `...`
  - types: `...`
  - tests: `...`
- Configured models:
  - planner: `...`
  - executor: `...`
  - reviewer: `...`
- `purser doctor`: passed/failed
- Follow-up: `...`

---

## Optional follow-up after setup

If the user wants, you may also do a smoke test by:

1. creating a tiny sample spec
2. running `purser planner-intake-spec ...`
3. running `purser planner-plan ...`
4. optionally executing one safe sample bead

But do this only if the user asks for live validation after setup.
