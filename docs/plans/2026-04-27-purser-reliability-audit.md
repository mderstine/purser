# Purser Reliability Audit and Lifecycle Decision

Date: 2026-04-27
Spec: `specs/2026-04-27-purser-execution-reliability-and-structured-outcomes.md`
Bead: `beads-21r.1`

## Scope audited

This audit covers the current planner, executor, reviewer, prompt, run-record, and Beads integration paths that are affected by the execution reliability spec.

Primary files reviewed:

- `src/purser/planner.py`
- `src/purser/loop.py`
- `src/purser/outcomes.py`
- `src/purser/roles.py`
- `src/purser/artifacts.py`
- `src/purser/beads.py`
- `src/purser/cli.py`
- `src/purser/prompts/planner.md`
- `src/purser/prompts/executor.md`
- `src/purser/prompts/reviewer.md`

## Current flow map

### Pi role invocation

`src/purser/roles.py` defines `PiRunner.run_role()`.

Current behavior:

1. Builds a `pi` command with:
   - `--mode json`
   - `--print`
   - `--no-session`
   - `--append-system-prompt <prompt_path>`
2. Runs Pi via `subprocess.run(..., capture_output=True, timeout=timeout_seconds)`.
3. Parses JSON-mode stdout events with `parse_json_mode_stdout()`.
4. Extracts `final_text` from assistant text in `message_end`, `turn_end`, or `agent_end` events, falling back to streamed deltas.
5. Raises when Pi exits non-zero, emits no JSON events, or has no final assistant text.

Important implication: Purser currently receives Pi JSON event streams, but role outcomes are still parsed from the assistant's free-form final text rather than from a schema-native response field.

### Structured outcome parsing

`src/purser/outcomes.py` defines dataclasses and parsers for planner, executor, and reviewer outcomes.

Current behavior:

1. `_extract_fenced_json()` looks for Markdown fenced JSON blocks using the regex ` ```json ... ``` `.
2. `_parse_json_payload()` parses the last fenced block with `json.loads()`.
3. Per-role parsers require fields by type only:
   - planner: `status`, `created_beads`, `dependencies`, `needs_human_input`, `summary`
   - executor: `status`, `bead_id`, `files_touched`, `new_beads`, `ready_for_review`, `summary`
   - reviewer: `decision`, `bead_id`, `state_transition_performed`, `issues`, `summary`
4. Enum values are only partially enforced outside the parser:
   - planner requires `status == "planned"` in `PlannerService._validate_planner_outcome()`.
   - executor does not validate `status` enum.
   - reviewer later compares `decision == "approve"`; any other value is treated as rejection-like.

Important implication: normal success depends on a Markdown fenced JSON block in free-form final text, and validation errors are type-oriented rather than schema/enum-oriented.

### Planner flow

`src/purser/planner.py` defines `PlannerService`.

#### `planner-intake-spec`

1. Resolves the spec path.
2. Runs the planner role with `_intake_message()`.
3. Optionally writes synthesized final text to a spec output path.
4. Does not create beads.
5. Does not currently write a run artifact for intake.

#### `planner-plan`

1. Resolves the spec path.
2. Enforces approval via `.purser/approvals` when `loop.human_approve_plan = true`.
3. Captures `before_ids = {bead.id for bead in self.beads.list_all()}`.
4. Runs the planner role with tools `read,bash,grep,find,ls`.
5. Captures all beads after the run and computes `created_ids = after_ids - before_ids`.
6. Parses a fenced JSON planner outcome from final text.
7. Writes a run artifact with:
   - role result
   - parsed structured outcome or `None`
   - `created_bead_ids`
   - `before_bead_ids`
   - `after_bead_ids`
   - parse errors, if any
8. Fails when no beads were created, outcome parsing failed, outcome status is not `planned`, or the outcome bead list does not exactly match observed `created_ids`.
9. Validates created beads have matching `spec_id` and non-empty acceptance criteria.

Current recovery gap:

- If the shell or Pi process times out after bead creation, control never reaches the after-state capture/artifact writing path because `PiRunner.run_role()` raises `RoleExecutionError` on `subprocess.TimeoutExpired`.
- Existing beads are detected only by before/after comparison within a successful process. There is no stable planner run ID, spec hash, or metadata-based retry mechanism.

### Executor flow

`src/purser/loop.py` defines `PurserLoop._execute()`.

Current behavior:

1. Gets the executor prompt path.
2. Builds a runtime instruction message that tells the executor to:
   - run `bd show`
   - read the spec when present
   - implement only acceptance criteria
   - run configured gates until all pass
   - leave the bead in progress/open for Purser to mark review-ready
   - not close the bead
   - include a fenced JSON structured outcome with fields `status`, `bead_id`, `files_touched`, `new_beads`, `ready_for_review`, `summary`
3. Increments `purser_executor_attempts` metadata before running Pi.
4. Runs the executor role.
5. Parses a fenced JSON executor outcome.
6. Writes a run artifact on parse failure or validation failure.
7. Requires `outcome.bead_id == bead.id`.
8. Requires `outcome.ready_for_review == true`.
9. If the executor closed the bead, Purser reopens it and fails the run.
10. If the bead status is neither `in_review` nor `in_progress`, Purser moves it to `in_progress`.
11. Purser runs configured gates after the executor returns.
12. On gate failure, Purser clears review-ready metadata, moves the bead to `open`, writes an artifact, and raises.
13. On green gates, Purser keeps the bead active if needed and sets metadata `purser_review_ready=true`.
14. Writes a successful executor artifact.

Current state-owner model for executor: mostly Purser-owned. The executor may mutate files and create follow-up beads, but Purser enforces no self-close, runs gates, and marks review readiness with metadata.

### Reviewer flow

`src/purser/loop.py` defines `PurserLoop._review()`.

Current behavior:

1. Gets the reviewer prompt path.
2. Builds a runtime instruction message that tells the reviewer to:
   - validate against spec and acceptance criteria
   - avoid source edits
   - close the bead in Beads when approved
   - reopen or move it to open when rejected
   - perform a real Beads transition during the run
   - include a fenced JSON structured outcome with fields `decision`, `bead_id`, `state_transition_performed`, `issues`, `summary`
3. Runs the reviewer role with read-only-ish tools `read,bash,grep,find,ls`.
4. Parses a fenced JSON reviewer outcome.
5. Requires `outcome.bead_id == bead.id`.
6. Requires `outcome.state_transition_performed == true`.
7. Purser runs configured gates after the reviewer returns.
8. On gate failure, Purser clears review-ready metadata, moves the bead to `open`, writes an artifact, and returns.
9. If `outcome.decision == "approve"`, Purser requires that the reviewer already closed the bead.
10. If the decision is anything else, Purser requires that the reviewer did not leave it closed, then clears review-ready metadata and moves it to `open` with `outcome.summary`.
11. On approval, Purser appends a validation record to `VALIDATION.md` and writes a successful reviewer artifact.

Current state-owner model for reviewer: agent-owned approval/rejection transition, with Purser verifying after the fact and doing some cleanup on rejection/gate failure.

### Loop selection and review readiness

`src/purser/beads.py` and `src/purser/loop.py` define the review queue behavior.

Current behavior:

1. `BeadsClient.list_review_ready()` first tries to list beads with status `in_review`.
2. It then scans all beads for metadata `purser_review_ready` in truthy values.
3. Closed beads are not review-ready.
4. `PurserLoop.run_once()` reviews a review-ready bead; otherwise it claims a ready/open bead, executes it, then immediately reviews it.
5. `PurserLoop.run_all()` processes review-ready beads before new ready work and enforces an executor attempt cap.

Important implication: Purser already has a portable metadata-first review-ready mechanism. It does not need agents to invent or rely on custom statuses.

### Run artifacts

`src/purser/artifacts.py` defines `RunArtifacts.write_role_artifact()`.

Current artifact fields:

- `schema_version`
- `timestamp_utc`
- `kind`
- `bead_id`
- `spec_path`
- serialized `role_result`
  - command
  - stdout/stderr
  - transcript
  - final_text
  - provider_error
- serialized `structured_outcome`
- gate results/failure
- before/after state
- errors
- extra

Important implication: artifacts already preserve raw role output and parsed outcomes when the flow reaches artifact writing. Timeout and subprocess exceptions before artifact writing remain weak spots.

### Beads integration

`src/purser/beads.py` defines `BeadsClient`.

Current behavior:

1. Invokes `bd --json --dolt-auto-commit <mode> ...` through `subprocess.run()`.
2. Parses JSON stdout, including JSON-lines fallback.
3. Raises `BeadsError` on non-zero exit using stderr/stdout.
4. Does not currently capture or surface successful-command stderr warnings, such as `Warning: auto-export: git add failed: exit status 1`.
5. Uses shell-safe subprocess argument lists, not shell strings, for its own Beads operations.
6. Planner agents still create beads via shell-visible `bd create` commands from prompts rather than through `BeadsClient.create()`.

Important implication: Purser's own Beads operations avoid shell quoting problems, but model-driven planner bead creation can still lose literals because prompts drive the agent through shell commands.

## Prompt alignment audit

### Executor prompts

Static role prompt: `src/purser/prompts/executor.md`

- Says Purser will mark review readiness with metadata rather than custom Beads status.
- Says do not close beads.
- Says report `ready_for_review: true` when complete.

Runtime executor message: `src/purser/loop.py`

- Says leave the bead in progress/open for Purser to mark review-ready.
- Says do not close the bead and do not rely on custom review statuses.
- Requires fenced JSON outcome.

Assessment: executor lifecycle instructions are aligned around Purser-owned review-readiness and no self-close. The main weakness is fenced JSON, not lifecycle contradiction.

### Reviewer prompts

Static role prompt: `src/purser/prompts/reviewer.md`

- Says close the bead only if correct.
- Says reopen or move it back to open when incomplete.
- Says the reviewer must actually perform a Beads state transition.

Runtime reviewer message: `src/purser/loop.py`

- Says the reviewer must close the bead on approval.
- Says the reviewer must reopen or move it to open on rejection.
- Says prose without Beads transition is a failure.

Assessment: reviewer static and runtime prompts are internally aligned with each other, but they conflict with the reliability spec's recommended model where Purser orchestration owns lifecycle transitions based on structured reviewer outcomes.

### Planner prompts

Static role prompt: `src/purser/prompts/planner.md`

- Says human approval is required before generating the bead graph.
- Says use local `bd` CLI to create beads and dependencies.
- Says set `--spec-id` on every created bead.
- Says preserve exact literals.

Runtime planner message: `src/purser/planner.py`

- Enforces approval before calling the model.
- Says create beads using `bd create` and `bd dep`.
- Says every created bead must include `--spec-id`.
- Requires fenced JSON outcome.

Assessment: planner prompt alignment is reasonable, but idempotency and literal preservation are weak because the agent is the component creating beads by shelling out to `bd`.

## Lifecycle ownership decision

Decision: Purser orchestration should own Beads lifecycle state transitions for executor and reviewer flows.

Authoritative model for subsequent beads:

1. Planner role proposes or creates planning artifacts as directed by the planner design, but any generated beads must be associated with stable Purser metadata once planner idempotency is implemented.
2. Executor role performs scoped work, records notes/follow-up beads when needed, and emits a structured executor outcome.
3. Executor role must not close beads, mark custom review statuses, or be responsible for review-ready state.
4. Purser validates the executor outcome, runs gates when applicable, and sets/clears `purser_review_ready` metadata or moves the bead to open/blocked based on verified outcome and gate results.
5. Reviewer role inspects work and emits a structured reviewer outcome: approved, rejected, blocked, or failed, with issues and summary.
6. Reviewer role must not close, reopen, or otherwise perform lifecycle transitions as the normal path.
7. Purser validates the reviewer outcome, runs gates when applicable, and closes, reopens, or updates the bead based on the verified outcome.
8. Purser should record lifecycle actions in Beads notes/comments and run artifacts so manual recovery is possible.
9. Custom `in_review` status remains a backwards-compatible queue signal only; the portable primary signal is `purser_review_ready` metadata.

Rationale:

- It gives one component responsibility for state transitions, eliminating prompt contradictions and after-the-fact verification races.
- It lets Purser attach consistent diagnostics when output parsing, gates, or Beads updates fail.
- It matches the existing executor behavior and review-ready metadata mechanism.
- It avoids asking reviewers to mutate state while also asking Purser to validate and run gates.

## Implementation context for dependent beads

### `beads-21r.2`: schema-native executor and reviewer outcome contracts

Start from `src/purser/outcomes.py`, `src/purser/roles.py`, and `src/purser/artifacts.py`.

Current parser depends on fenced JSON in final text. Replace or augment this with a schema-native contract for executor/reviewer outcomes. The new schemas should validate enums, required fields, and nested gate/issue structures. Keep artifact storage of raw Pi output and parsed outcome.

The reviewer schema should use the spec's status values (`approved`, `rejected`, `blocked`, `failed`) rather than the current `decision == "approve"` plus `state_transition_performed` model. The executor schema should include `gates_run` and `blocking_reason` so Purser can own status transitions and diagnostics.

### `beads-21r.4`: prompt and lifecycle alignment

Update `src/purser/prompts/reviewer.md` and the runtime reviewer message in `src/purser/loop.py` to remove instructions requiring the reviewer to close/reopen beads. Update executor prompts only as needed to preserve the Purser-owned model. Document the lifecycle model in user-facing docs.

Expected reviewer prompt direction: review only, do not edit source files, do not close/reopen/update lifecycle status, emit structured outcome, and let Purser orchestrate state transitions.

### `beads-21r.6`: planner idempotency and timeout recovery

Start from `src/purser/planner.py`, `src/purser/roles.py`, and `src/purser/beads.py`.

Current `planner-plan` records before/after IDs only after a successful role process. Add a stable planner run/spec identity, metadata on created beads, and artifact writing for timeout/exception paths. Avoid duplicate bead creation on retry by detecting existing beads with matching spec/run metadata or spec identity.

### `beads-21r.8`: warnings and diagnostics

Start from `src/purser/beads.py`, `src/purser/cli.py`, and `src/purser/artifacts.py`.

`BeadsClient._run()` currently discards stderr on successful commands, so warnings are not surfaced. Capture successful-command stderr warnings, add them to artifacts/summaries, and include failure summaries that print artifact path, bead status, git status summary, and recovery commands.

## Open follow-up risks

- Need to confirm whether Pi exposes a native schema or structured-output parameter that Purser can pass directly. If not, the fallback should be raw JSON from JSON-mode events, not Markdown fences.
- Planner literal preservation may require moving bead creation into Purser itself from a planner-emitted structured graph rather than allowing the model to invoke `bd create` with shell quoting.
- Decision beads should follow the same Purser-owned lifecycle: the decision executor records a decision and emits an outcome; Purser decides whether to mark review-ready or close depending on the selected review policy.
