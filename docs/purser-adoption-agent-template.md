# Purser adoption template for a generic coding agent

Use this prompt when you want a general-purpose coding agent to set up **purser** in the current repo as a supporting workflow framework.

---

You are setting up **purser** in the user's current repository. Purser is not the product being built; it is the orchestration framework used to plan, build, and review the repo's actual features.

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
5. Local/runtime artifacts are ignored appropriately in `.gitignore`.
6. `purser doctor` succeeds.
7. Provide a short summary of what was changed and any follow-up the user should know.

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

### 6. Ensure local/runtime files are ignored

Add appropriate `.gitignore` entries if missing. Usually:

```gitignore
.beads/
.purser/
.purser.toml
VALIDATION.md
```

Only add what makes sense for the repo and local workflow.

### 7. Verify health

Run:

```bash
purser doctor
```

Success means:
- required binaries are found
- config exists
- prompts exist
- Beads storage is local embedded mode

### 8. Report final status

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
- `.gitignore` protects local runtime files where appropriate
- your final report is concise and explicit

## Example final report format

- Installed/verified: `purser`, `bd`, `dolt`, `pi`
- Initialized/reused local Beads: yes/no
- Wrote/updated: `.purser.toml`, prompt files, `.gitignore`
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
