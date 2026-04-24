# Pi-native portable Purser refactor

## Summary

Refactor Purser into a **Pi-native orchestration framework** for portable use across arbitrary repositories, with first-class support for planner / executor / reviewer workflows hosted through Pi and a default bias toward open-model-friendly providers and configurations.

Purser should remain compatible with Beads-driven execution and `uv`-based adoption in Python repositories, but the core product direction is now explicitly:

- **Pi-first**
- **portable across repos**
- **open-model-friendly**
- **repo-scaffolding and workflow clarity first**
- **structured orchestration contracts, not prose-only agent behavior**

Legacy `purser-3` should be treated as a source of lessons about portability, scaffolding, and workflow design, not as the target agent integration model. Claude/Codex/Copilot-specific prompt artifacts are not the center of the design. Codex may still be used **through Pi**, but Pi is the primary and only first-class agent host in Purser itself.

## Problem

The current Purser implementation has a promising planner → executor → reviewer runtime loop, but it is not yet a strong portable tool for repo adoption:

- `purser init` is too minimal for real consumer-repo setup.
- Documentation and implementation are out of sync.
- Prompt/file naming and Pi prompt wiring are incomplete.
- Reviewer outcomes rely too much on freeform text parsing.
- Human planning approval is not enforced as a machine-readable state.
- Repo-root detection and repo-aware scaffolding are weak.
- Default model/config posture does not yet reflect the intended Pi-native, open-model-friendly direction.

As a result, Purser is harder to adopt, harder to reason about, and more brittle than it should be for use across multiple repositories.

## Goals

1. Make Purser a **Pi-native orchestration framework** with Pi as the only first-class agent surface.
2. Make Purser **portable across repositories** with robust, idempotent, repo-aware setup.
3. Preserve and strengthen the planner / executor / reviewer workflow, including the reviewer validation step.
4. Bias starter configuration and docs toward **open models and Pi-routed providers**, including local and hosted open-weight options.
5. Cleanly support the user's available Pi-routed models, including:
   - Codex via Pi
   - `gpt-oss`
   - `gemma4`
   - `qwen3.5`
   - Ollama Cloud-backed models exposed through Pi
6. Introduce more **structured runtime contracts** so Purser can reliably validate role outcomes.
7. Improve operator ergonomics with better scaffolding, health checks, and clearer separation of role prompts vs operator workflow prompts.
8. Keep Purser project-agnostic so consumer repos can configure their own gates, models, and conventions.

## Non-goals

1. Re-centering Purser around Claude Code, Codex-native, or Copilot-native prompt export flows.
2. Making non-Pi agent hosts first-class in the core architecture.
3. Reintroducing legacy multi-surface prompt generation as the primary organizing principle.
4. Building a full hosted service or server-based orchestration backend.
5. Solving all possible GitHub sync / mirroring workflows in this refactor.
6. Replacing Beads as the execution/task graph system.
7. Adding broad language-specific intelligence directly into Purser core beyond practical gate detection and scaffolding defaults.

## Users / stakeholders

- **Primary operator / director:** a human driving work in a repo using Purser.
- **Pi-hosted planner role:** decomposes approved specs into Beads.
- **Pi-hosted executor role:** implements one bead at a time.
- **Pi-hosted reviewer role:** validates correctness, atomicity, and elegance before closure.
- **Consumer repository maintainers:** teams or individuals adopting Purser in Python and other repos.

## Scope

This refactor includes:

- CLI redesign and cleanup where needed
- repo-aware initialization and adoption scaffolding
- Pi-native prompt and workflow artifact generation
- config schema evolution
- runtime protocol hardening for planner / executor / reviewer
- open-model-friendly defaults and documentation
- stronger doctor / health checks
- new or expanded tests covering portability and setup behavior
- migration of docs to match the Pi-native direction

This refactor may include modest renaming or restructuring of on-disk prompt artifacts if it improves clarity and portability.

## Product direction

Purser is explicitly:

- **A Pi-native orchestration framework**
- **A repo-local workflow tool**
- **A planner / executor / reviewer conductor around Beads and repo-defined gates**

Purser is not:

- a Claude Code-first framework
- a Codex-native prompt toolkit
- a general prompt-export matrix for many IDE agents
- the product being built inside the consumer repository unless explicitly requested

Codex remains a supported coding model or behavior **through Pi**, not as a separate first-class runtime integration path.

## Functional requirements

### 1. Repo-aware initialization

`purser init` must become a robust adoption command.

It must:

1. Resolve the target repository root, preferably via Git root detection when applicable.
2. Initialize scaffold files in the repo root even when invoked from a subdirectory.
3. Be idempotent by default.
4. Avoid overwriting existing files unless explicitly requested.
5. Produce clear output listing created, updated, skipped, or preserved files.

### 2. Full repo-local scaffold generation

`purser init` must scaffold the repo for Pi-native Purser adoption, including at minimum:

- `.purser.toml`
- `.purser/prompts/`
- `specs/` or equivalent repo-local spec directory if missing
- `.purser/README.md` or equivalent explanatory scaffold file
- Pi prompt-directory integration under `.pi/settings.json`
- `AGENTS.md` creation or merge/update with a Purser-owned section
- optional `.gitignore` additions for local runtime artifacts

### 3. Pi-native prompt layout

Purser must clearly separate:

#### Runtime role prompts
Used internally by the `purser` CLI when invoking Pi:

- planner role prompt
- executor role prompt
- reviewer role prompt

#### Operator workflow prompts
Used manually by humans through Pi prompt templates / slash commands:

- add or refine spec
- plan an approved spec
- execute one bead
- execute the full loop
- optionally review or validate a bead manually

Prompt filenames and generated artifacts must be consistent with the documented Pi slash-command story.

### 4. `.pi/settings.json` integration

Purser must support project-local Pi prompt discovery by ensuring the repo can point Pi at Purser's canonical prompt directory.

Behavior requirements:

1. If `.pi/settings.json` does not exist, initialize it with a `prompts` entry pointing at the Purser prompt directory.
2. If `.pi/settings.json` exists, merge the `prompts` array carefully without overwriting unrelated settings.
3. The prompt directory arrangement must make the generated operator prompts available as Pi slash commands after `/reload`.
4. Documentation and actual filenames must match.

### 5. `AGENTS.md` integration

Purser must be able to create or update `AGENTS.md` with a clearly delimited Purser-owned section that explains:

- Purser is framework/tooling, not the consumer repo's product unless explicitly requested.
- Specs should describe the repo's real work.
- Use local embedded Beads storage only.
- The human approval boundary before planning.
- The planner / executor / reviewer lifecycle.

The update must be idempotent and preserve unrelated existing agent instructions.

### 6. `.gitignore` support

Purser should add missing ignore entries where appropriate for repo-local runtime artifacts such as:

- `.beads/`
- `.purser/`
- `.purser.toml`
- `VALIDATION.md`
- run logs or generated local state if applicable

This must be additive and non-destructive.

### 7. Repo-type detection and starter gate generation

Purser should detect common repo types and prefill starter gates accordingly.

Initial support should include at least:

- Python (`pyproject.toml`)
- Node (`package.json`)
- Rust (`Cargo.toml`)
- Go (`go.mod`)

For Python repos using `uv`, starter gates should prefer `uv run ...` commands.

Where the repo already clearly defines lint/type/test commands, Purser should prefer adapting to those rather than inventing new ones.

### 8. Open-model-friendly default configuration

Purser starter config and docs must reflect a Pi-native, open-model-friendly posture.

Requirements:

1. Starter model guidance must not assume proprietary providers as the default center of gravity.
2. Config examples should be compatible with Pi-routed open or open-weight-friendly providers.
3. Docs should explicitly support Pi-routed models such as:
   - Codex through Pi
   - `gpt-oss`
   - `gemma4`
   - `qwen3.5`
   - Ollama Cloud-backed models surfaced through Pi
4. The config model-routing design must remain fully user-overridable per role.

### 9. Role invocation remains Pi-native

Purser runtime role execution must continue to invoke Pi in JSON mode as the core subprocess protocol.

Purser must continue to:

- run each role in a fresh subprocess
- route models per role through Pi config
- provide role-specific prompts and tool access
- parse Pi JSON output robustly

### 10. Structured role outcome contract

Purser must move toward structured role outcomes rather than relying on freeform text inference.

At minimum, the refactor must define and implement a machine-readable outcome contract for:

- planner
- executor
- reviewer

The contract may be delivered through final JSON snippets embedded in final text or another Pi-compatible structured pattern, but it must be consistently parseable by Purser.

Examples of fields that should be represented include:

- planner: created bead IDs, dependency edges, needs human input, summary
- executor: bead ID, files touched, follow-up beads created, ready for review, summary
- reviewer: decision, bead ID, Beads state transition performed, issues, summary

### 11. Reviewer decision must not rely on regex-only approval parsing

Purser must stop treating prose-only phrases like “approve” or “reject” as the main source of truth for closure behavior.

Purser must validate reviewer results based on structured output and actual Beads state transitions.

Fallback heuristics may exist temporarily during migration, but the target contract must be explicit and machine-readable.

### 12. Explicit human approval boundary for planning

Purser must support a stronger planning approval contract.

Potential acceptable implementations include one of:

- an explicit CLI approval command
- a spec approval marker/frontmatter field
- a repo-local approval state file under `.purser/`

The planner command must be able to enforce approval mechanically when `human_approve_plan = true`.

### 13. Clear role responsibility boundaries

Purser must keep responsibilities clear:

- planner: read/refine/decompose, mutate Beads planning state, no source implementation
- executor: implement exactly one bead, no self-close
- reviewer: inspect and decide, no source edits
- Purser orchestrator: run configured gates, validate transitions, persist logs and validation artifacts

If executor or reviewer behavior overlaps with gate-running instructions, the final contract must clarify what the agent should do versus what Purser itself will do.

### 14. Validation log behavior

Purser must keep the validation log behavior for approved/closed work, but the implementation should be aligned with structured reviewer decisions and stronger runtime evidence.

Validation log entries should continue to capture at least:

- bead ID/title
- spec reference
- reviewer summary
- gate verification results
- executor attempt count

### 15. Run artifact logging

Purser should persist useful runtime artifacts under repo-local Purser state, such as:

- role transcripts or role summaries
- gate outputs
- structured role outcome payloads
- key bead state transitions

This should make debugging and audit easier.

### 16. Improved doctor / health checks

`purser doctor` must validate not only binary presence and config shape, but also practical Pi-native readiness.

It should check at least:

- `bd`, `dolt`, `pi` presence
- config exists and parses
- prompt files exist
- Beads storage is repo-local embedded mode
- Pi prompt-directory integration exists or warn clearly if missing
- configured role model strings are present and non-empty
- optional warnings for suspicious defaults or inconsistent prompt layout

### 17. Commands should work from subdirectories inside the repo

Operational commands like `init`, `doctor`, and runtime workflows should behave sensibly when run from a nested directory inside the repository, not only the repo root.

### 18. Test coverage for portability and setup

The refactor must add or expand tests for:

- repo-root resolution
- idempotent init
- `.pi/settings.json` creation and merge behavior
- `AGENTS.md` append/update behavior
- `.gitignore` append behavior
- repo-type detection and gate defaults
- structured reviewer decision handling
- docs/implementation consistency where practical

## Technical considerations

### Architecture direction

The target architecture should preserve the strong parts of the current implementation:

- `beads.py` as the Beads subprocess wrapper
- `roles.py` as the Pi subprocess wrapper
- `gates.py` for repo-defined validation backpressure
- `loop.py` for orchestration
- `validation.py` for append-only review evidence

But the architecture should be extended with stronger adoption and scaffolding primitives, likely including modules for:

- repo detection / repo root resolution
- scaffold generation / file merge helpers
- prompt catalog generation for Pi-native workflow prompts
- structured role outcome parsing and validation
- run artifact persistence

### Prompt strategy

Prompts should be organized around Pi-native usage rather than legacy agent exports.

The codebase should distinguish between:

1. **role prompts** used by Purser runtime
2. **workflow prompts** exposed to humans via Pi prompt discovery

The repo should maintain one canonical source of truth for shipped prompts/templates where practical, but the canonicality should serve Pi-native operation first.

### Model posture

Purser should assume that users may route models through Pi from multiple backends, including open-weight and cloud-hosted options.

The product must support per-role model routing without baking in provider-specific assumptions.

Examples relevant to this work include:

- Codex through Pi
- `gpt-oss`
- `gemma4`
- `qwen3.5`
- Ollama Cloud models configured via Pi

### Migration strategy

The refactor should be staged so that current users are not forced into a fully breaking migration all at once unless the resulting simplification is clearly worth it.

If prompt names or config fields change, Purser should either:

- migrate old layouts automatically where safe, or
- fail with a clear, actionable message describing what changed

### Backward compatibility

Backward compatibility is desirable where low-cost, but correctness, Pi-native clarity, and portability are more important than preserving every early naming decision.

## Verification strategy

The refactor should be considered successful only if all of the following can be demonstrated:

1. Tests pass locally.
2. `purser init` can be run in a sample repo from a nested subdirectory and scaffolds the repo root correctly.
3. `purser init` is idempotent and preserves existing unrelated config in `AGENTS.md` and `.pi/settings.json`.
4. A Python repo using `uv` receives correct starter gates by default.
5. `purser doctor` reports meaningful readiness information for Pi-native adoption.
6. Planner / executor / reviewer role outcomes can be parsed through a structured contract.
7. Reviewer approval/rejection no longer depends primarily on regex matching of prose.
8. Prompt files generated for Pi slash-command use are discoverable after `.pi/settings.json` wiring and Pi reload.
9. The docs match the actual CLI behavior and generated artifact layout.

## Acceptance criteria

### Product and architecture

- Purser is clearly positioned and documented as a **Pi-native orchestration framework**.
- Pi is the only first-class agent host in Purser core.
- Legacy Claude/Codex/Copilot export concerns do not define the core architecture.
- Codex remains usable through Pi routing.

### Setup and portability

- `purser init` resolves repo root correctly.
- `purser init` scaffolds the required repo-local files for adoption.
- `purser init` safely updates `AGENTS.md`, `.pi/settings.json`, and `.gitignore`.
- `purser init` can infer a good starter config for common repo types.
- Commands work from nested directories inside the repo.

### Pi-native workflow support

- Purser ships Pi-native runtime role prompts.
- Purser ships Pi-native operator workflow prompts.
- `.pi/settings.json` wiring makes workflow prompts discoverable in Pi after reload.
- Naming in docs and generated files is consistent.

### Runtime robustness

- Planner / executor / reviewer results have a structured, machine-readable contract.
- Reviewer approval/rejection is not primarily regex-derived.
- Planning approval can be enforced when configured.
- Validation logging still works correctly.
- Runtime artifacts are persisted in a useful local location.

### Open-model-friendly posture

- Starter config and docs support Pi-routed open-model use.
- The documented example posture includes Codex-through-Pi and Pi-routed `gpt-oss`, `gemma4`, and `qwen3.5` / Ollama Cloud options.
- Per-role model routing remains configurable.

### Quality

- Existing and new tests pass.
- The docs accurately describe setup and behavior.
- The refactor reduces drift between implementation, tests, and adoption docs.

## Risks / unknowns

1. The exact best structured-output pattern for Pi may require experimentation to balance reliability and simplicity.
2. Pi model naming conventions for Ollama Cloud-backed models may vary by local configuration, so starter defaults may need to be examples rather than strict assumptions.
3. Safe merging of `.pi/settings.json`, `AGENTS.md`, and `.gitignore` requires careful file-edit logic and tests.
4. There may be migration friction if prompt filenames or config conventions change.
5. Some consumer repos may have nonstandard validation workflows that resist automatic gate detection.
6. If role prompts become too elaborate, they may become harder to maintain than necessary; prompt structure should remain disciplined.

## Suggested milestones

### Milestone 1: alignment and baseline stability
- Fix failing tests and implementation/doc drift.
- Confirm public CLI and prompt naming direction.
- Decide final prompt layout and config evolution path.

### Milestone 2: Pi-native scaffold and adoption layer
- Implement repo-root detection.
- Expand `purser init` to scaffold full Pi-native repo setup.
- Add merge/update behavior for `AGENTS.md`, `.pi/settings.json`, `.gitignore`.
- Add repo-type detection and starter gate generation.

### Milestone 3: role protocol hardening
- Introduce structured planner/executor/reviewer outcome parsing.
- Add explicit planning approval enforcement.
- Improve run logging and runtime evidence persistence.

### Milestone 4: docs and operator polish
- Rewrite setup docs around Pi-native usage.
- Add clearer model guidance for open-model-friendly Pi routing.
- Improve `doctor` output and operator troubleshooting guidance.

### Milestone 5: validation and cleanup
- Expand portability/setup tests.
- Add integration-style smoke coverage where feasible.
- Remove obsolete legacy assumptions and dead paths.

## Open questions

1. What exact on-disk naming should be used for Pi workflow prompt files so they are both readable and stable?
2. Should structured role output be embedded in final text, written to files, or both?
3. What is the preferred explicit planning approval mechanism: CLI command, spec marker, or local state file?
4. Should starter model fields be omitted by default, or populated with open-model examples tailored to the local Pi environment?
5. Should `purser init` also attempt Beads bootstrap automatically when `.beads/` is missing, or only validate and instruct?
6. What minimum set of runtime artifacts should be persisted to avoid noise while preserving debuggability?
