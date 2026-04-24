# Purser consumer-repo setup

This is the canonical guide for integrating **Purser** into another repository.

Use this when Purser is being adopted as workflow tooling inside a repo whose real work may be software delivery, documentation, research, data analysis, data discovery, or other scoped project work.

## Purser's role

Purser is:
- a **Pi-native orchestration framework**
- a planner / executor / reviewer workflow layer
- tooling used to advance the repo's real work

Purser is **not**:
- the product of the consumer repo
- the main feature being built in the consumer repo, unless explicitly requested
- a shared/server Beads deployment manager
- a separate Claude/Codex/Copilot-native runtime architecture

Codex is supported **through Pi**. Open-model-friendly Pi-routed use is a first-class posture.

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

`purser init` is repo-root-aware and idempotent by default.

It creates or merges:
- `.purser.toml`
- `.purser/prompts/roles/planner-role.md`
- `.purser/prompts/roles/executor-role.md`
- `.purser/prompts/roles/reviewer-role.md`
- `.purser/prompts/workflows/purser-add-spec.md`
- `.purser/prompts/workflows/purser-plan.md`
- `.purser/prompts/workflows/purser-build.md`
- `.purser/prompts/workflows/purser-build-all.md`
- `.purser/README.md`
- `specs/.gitkeep`
- `.pi/settings.json`
- `AGENTS.md`
- `.gitignore`

### 4. Customize `.purser.toml`

Edit `.purser.toml` for the consumer repo's real validation commands and any model pinning you actually want.

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
timeout_seconds = 600
```

For starter model posture:
- use `roles.default_model` if the repo wants one shared model default
- use `[roles.models]` only for real per-role overrides
- otherwise leave models unset and let Pi ambient/default selection decide

Examples of Pi-routed model choices you might document or pin if the repo wants them:
- `qwen3.5`
- `gemma4`
- `gpt-oss`
- `codex`

For Python repos using `uv`, Purser prefers strict modern starter gates when repo signals are strong. For example:

```toml
[gates]
lint = "uv run ruff check . && uv run ruff format --check ."
types = "uv run ty check"
tests = "uv run pytest -x --tb=short"
timeout_seconds = 600
```

If the repo does not strongly signal that toolchain, stay conservative and adapt to the repo's actual commands instead of inventing new ones.

### 5. `AGENTS.md` integration

`purser init` creates or updates `AGENTS.md` with a Purser-owned section. That section makes all of the following explicit:
- Purser is a planning / execution / review framework used in this repo.
- Purser is **not** the repo's product or primary deliverable unless explicitly requested.
- The real goal is to advance the repo's actual work.
- Specs should describe the repo's real work, not Purser development work unless explicitly requested.
- Use repo-local embedded Beads storage only.
- Planning requires director/human approval before bead generation.

Purser uses these markers:

```md
<!-- purser:agents begin -->
<!-- purser:agents end -->
```

The update is idempotent and preserves unrelated existing content.

### 6. Configure Pi workflow prompt integration

Purser separates runtime role prompts from operator workflow prompts.

Runtime role prompts are used by the CLI internally:
- `.purser/prompts/roles/planner-role.md`
- `.purser/prompts/roles/executor-role.md`
- `.purser/prompts/roles/reviewer-role.md`

Operator workflow prompts are intended for Pi prompt discovery:
- `.purser/prompts/workflows/purser-add-spec.md`
- `.purser/prompts/workflows/purser-plan.md`
- `.purser/prompts/workflows/purser-build.md`
- `.purser/prompts/workflows/purser-build-all.md`

Purser wires Pi discovery through:

```json
{
  "prompts": ["../.purser/prompts/workflows"]
}
```

That lives at:

```text
.pi/settings.json
```

If `.pi/settings.json` already exists, Purser merges the `prompts` entry instead of overwriting unrelated settings.

Legacy migration notes:
- if the repo still has role prompts in the old flat layout under `.purser/prompts/*.md`, `purser init` copies them into `.purser/prompts/roles/` when that is safe
- if `.pi/settings.json` still points at `../.purser/prompts`, `purser init` rewrites it to `../.purser/prompts/workflows`
- if legacy and canonical prompt files both exist with different contents, Purser fails clearly instead of overwriting user edits

After changing Pi settings, reload Pi:

```text
/reload
```

Expected slash commands after reload include:
- `/purser-add-spec`
- `/purser-plan`
- `/purser-build`
- `/purser-build-all`

Do not duplicate prompts under `.pi/prompts/` unless you intentionally want Pi-only overrides.

### 7. Ignore local/runtime files where appropriate

Purser additively appends the following to `.gitignore` if missing:

```gitignore
.beads/
.purser/
.purser.toml
VALIDATION.md
```

This protects local Beads state, local Purser state, and validation artifacts.

### 8. Verify setup

Run:

```bash
purser doctor
```

A correct setup should report:
- binaries found
- config present
- runtime prompt files present
- Pi workflow prompt integration present or clearly warned about
- model posture/fallback described honestly
- repo-local embedded Beads storage

## Planning and execution flow

After setup, the normal flow is:

```bash
purser planner-intake-spec specs/example.md --synthesize false
# director/human reviews the spec + planning approach
purser approve-plan specs/example.md
purser planner-plan specs/example.md
purser exec-build
# or: purser exec-build-all
```

Important:
- do not run `purser planner-plan` before director/human approval when `human_approve_plan = true`
- Purser stores approval state under `.purser/state/plan-approvals/`
- Purser persists runtime evidence under `.purser/runs/`

## Acceptance criteria for a successful adoption

Consumer-repo adoption is complete only if all of these are true:
- `purser doctor` succeeds
- the repo uses local embedded Beads storage
- `.purser.toml` reflects the repo's real gates and any intentional model pinning
- `AGENTS.md` contains a clear Purser section
- `.pi/settings.json` points Pi prompt discovery at `../.purser/prompts/workflows`
- Purser workflow prompts are available as Pi slash commands after `/reload`

## Suggested next smoke test

Use a deliberately tiny, safe spec for the first live run:

```bash
purser planner-intake-spec specs/example.md --synthesize false
# director/human review
purser approve-plan specs/example.md
purser planner-plan specs/example.md
purser exec-build
```

Only plan after explicit human approval of the refined spec and planning approach.
