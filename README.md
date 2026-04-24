# purser

`purser` is a Pi-native, repo-portable orchestration framework for driving Beads-based work with three Pi-hosted roles:

- Planner
- Executor
- Reviewer

Purser is designed to be adopted inside another repository as workflow tooling. It is not the product of that repository unless explicitly requested.

It ships as a Python package with these CLIs:

- `purser`
- `purser-planner-intake-spec`
- `purser-planner-plan`
- `purser-exec-build`
- `purser-exec-build-all`

Utility:
- `purser doctor`

## Architecture posture

Purser is **Option A** from the refactor plan: a **Pi-native orchestration framework**.

That means:
- Pi is the only first-class agent host
- Purser shells out to `pi` in JSON mode for role execution
- Beads operations go through `bd`
- Codex is supported **through Pi**, not as a separate Purser runtime architecture
- open-model-friendly use through Pi is a first-class posture

Examples of supported Pi-routed model choices include:
- `qwen3.5`
- `gemma4`
- `gpt-oss`
- Codex through Pi
- Ollama Cloud-backed models surfaced through Pi

## High-level flow

1. Write or refine a markdown spec for the repo's actual work.
2. Optionally run planner intake to synthesize a clearer version.
3. Have the director/human explicitly approve planning.
4. Decompose the approved spec into atomic Beads.
5. Execute one ready bead or run the full executor/reviewer loop.
6. Validate closed work and append review evidence to `VALIDATION.md`.
7. Persist runtime artifacts under `.purser/runs/`.

## Pi-native prompt taxonomy

Purser separates prompts into two categories:

### Runtime role prompts
Used internally by Purser when invoking Pi:

- `.purser/prompts/roles/planner-role.md`
- `.purser/prompts/roles/executor-role.md`
- `.purser/prompts/roles/reviewer-role.md`

### Operator workflow prompts
Discovered by Pi as slash commands for human/operator use:

- `.purser/prompts/workflows/purser-add-spec.md`
- `.purser/prompts/workflows/purser-plan.md`
- `.purser/prompts/workflows/purser-build.md`
- `.purser/prompts/workflows/purser-build-all.md`

Purser wires Pi discovery through:

- `.pi/settings.json` → `../.purser/prompts/workflows`

After updating Pi settings, reload Pi:

```text
/reload
```

See also:
- [`docs/architecture/pi-native-prompt-taxonomy.md`](docs/architecture/pi-native-prompt-taxonomy.md)

## Quick start in another repo

```bash
uv tool install git+https://github.com/mderstine/purser.git
cd /path/to/consumer-repo
bd init
purser init
purser doctor
```

Then edit `.purser.toml` for the repo's real gates and any repo-level model pinning you actually want.

## What `purser init` creates

`purser init` is repo-root-aware and idempotent by default. It scaffolds:

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

It also:
- merges `../.purser/prompts/workflows` into `.pi/settings.json`
- upserts a Purser-owned section in `AGENTS.md`
- additively appends local ignore entries to `.gitignore`
- detects common repo signals and pre-fills conservative or strict starter gates
- auto-migrates the legacy `.purser/prompts/*.md` role layout to `.purser/prompts/roles/*.md` when safe

## Legacy layout migration

If a repo still uses the older flat prompt layout:

- role prompts at `.purser/prompts/planner.md`, `.purser/prompts/executor.md`, `.purser/prompts/reviewer.md`
- Pi prompt wiring through `../.purser/prompts`

then `purser init` will safely copy legacy role prompts into `.purser/prompts/roles/`, update `.purser.toml`, and switch `.pi/settings.json` to `../.purser/prompts/workflows`.

If both legacy and canonical role prompt files exist with different contents, Purser stops and asks for a manual choice instead of overwriting user-edited prompts.

## Config and model posture

Project configuration lives at:

- `.purser.toml`

Model resolution is intentionally conservative and honest:

1. `roles.models.<role>`
2. `roles.default_model`
3. Pi ambient/default model selection

If no model is pinned, Purser omits `--model` and lets Pi choose its ambient/default model.

Purser does **not** scaffold fake working model defaults into `.purser.toml`.

## Typical setup + planning flow

```bash
purser init
# edit .purser.toml for real gates/models
purser doctor

purser planner-intake-spec specs/my-spec.md --synthesize false
# human reviews/refines spec and planning approach
purser approve-plan specs/my-spec.md
purser planner-plan specs/my-spec.md
purser exec-build
# or: purser exec-build-all
```

`purser planner-plan` requires explicit approval first when `human_approve_plan = true`.

## Health check

Run:

```bash
purser doctor
```

Doctor reports Pi-native readiness across:
- binaries (`bd`, `dolt`, `pi`)
- config presence
- runtime prompt files
- Pi workflow prompt integration in `.pi/settings.json`
- prompt-layout consistency
- model configuration or Pi-default fallback behavior
- repo-local embedded Beads storage

## Beads storage policy

Purser is intentionally strict: it only runs against a repo-local embedded Beads/Dolt database.

Supported:
- `bd init` default embedded mode

Rejected:
- `bd init --server`
- shared/global server-backed Beads setups

If a repo is configured for non-local/shared Beads storage, `purser doctor` and runtime commands fail fast.

## Runtime hardening

Purser now expects structured role outcomes from planner, executor, and reviewer flows, and persists runtime evidence under:

- `.purser/runs/`

Artifacts include enough information to debug malformed role output, gate failures, and review/planning mismatches.

## Using Purser in another repo

Canonical setup guide:
- [`docs/consumer-repo-setup.md`](docs/consumer-repo-setup.md)

Agent handoff/setup template:
- [`docs/purser-adoption-agent-template.md`](docs/purser-adoption-agent-template.md)
