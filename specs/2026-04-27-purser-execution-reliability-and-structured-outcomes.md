# Purser - Execution Reliability and Structured Outcomes

## Status

Accepted for Purser planning. This spec captures consumer-agent diagnostics and recommended enhancements for Purser execution reliability, structured outcomes, planner recoverability, and human diagnostics.

## Context

A Dex repository workflow exposed several Purser reliability issues while planning and executing spec-driven work.

Observed commands and outcomes:

```bash
purser planner-plan specs/dex-v0.2-stable-cli-pi-skill.md
```

This command timed out at the shell level, but still created a Beads graph. The caller had to inspect Beads manually to determine whether planning completed and what was created.

```bash
purser exec-build dex-qna
```

This command failed with:

```text
error: executor did not return a valid structured outcome payload: missing fenced JSON structured outcome payload
```

The saved run record showed that Purser launched Pi with `--mode json`, but the runtime prompt still required the model to include a Markdown fenced JSON block in free-form final text:

````markdown
```json
{
  "status": "completed",
  "bead_id": "...",
  "files_touched": [],
  "new_beads": [],
  "ready_for_review": true,
  "summary": "..."
}
```
````

The executor returned prose instead of the required fenced JSON payload. Purser therefore could not parse the outcome and left the bead in an ambiguous state.

The run also exposed related cleanup opportunities:

- Executor role instructions and runtime instructions disagree about who moves Beads into review state.
- Decision-type beads are routed through a code-build-oriented executor path even when no source code changes or gates are needed.
- Planner-created Beads can lose exact Markdown code literals from the originating spec.
- Planner timeout behavior is not clearly idempotent or self-reporting.
- Beads auto-export may emit `git add failed` warnings in repo-local embedded setups.

## Product goal

Make Purser's planner and executor workflows reliable, machine-parseable, idempotent, and easier to recover when agents or subprocesses return incomplete output.

Purser should not require humans to manually inspect run JSON, infer partial state, or complete beads by hand after a structured-output parsing failure.

## Goals

1. Replace brittle Markdown-fenced JSON outcome parsing with a schema-native structured outcome contract.
2. Add automatic recovery or repair behavior when an executor/reviewer omits or malforms the required structured outcome.
3. Align executor/reviewer prompts and lifecycle responsibilities so status transitions are unambiguous.
4. Add first-class handling for decision beads and other non-code work.
5. Make planner bead generation idempotent and diagnosable after timeouts or partial failures.
6. Preserve exact literals from specs when generating Beads, especially Markdown code spans and shell commands.
7. Improve diagnostics for Beads auto-export/git staging warnings.
8. Improve run summaries so humans can quickly understand what happened, what changed, and what remains blocked.

## Non-goals

- Do not redesign Purser's entire planning model.
- Do not replace Beads as the issue tracker.
- Do not require a specific model provider to make the workflow reliable.
- Do not make Purser product work depend on the Dex repository.
- Do not hide failed or partial executions behind optimistic success messages.

## Required capabilities

### 1. Schema-native structured outcomes

Purser should request and parse structured executor/reviewer outcomes using a native JSON/schema mechanism rather than scraping Markdown code fences from free-form text.

Required behavior:

- Define an explicit outcome schema for executor runs.
- Define an explicit outcome schema for reviewer runs.
- Validate outcomes against those schemas.
- Store both the raw agent output and parsed structured outcome in the run record.
- If structured parsing fails, preserve enough raw context for debugging.

Suggested executor outcome schema:

```json
{
  "status": "completed | blocked | failed",
  "bead_id": "string",
  "files_touched": ["string"],
  "new_beads": ["string"],
  "gates_run": [
    {
      "command": "string",
      "status": "passed | failed | skipped",
      "exit_code": 0,
      "summary": "string"
    }
  ],
  "ready_for_review": true,
  "summary": "string",
  "blocking_reason": "string or null"
}
```

Suggested reviewer outcome schema:

```json
{
  "status": "approved | rejected | blocked | failed",
  "bead_id": "string",
  "issues_found": [
    {
      "severity": "critical | major | minor",
      "summary": "string",
      "file": "string or null"
    }
  ],
  "gates_run": [
    {
      "command": "string",
      "status": "passed | failed | skipped",
      "exit_code": 0,
      "summary": "string"
    }
  ],
  "summary": "string"
}
```

Acceptance criteria:

- Purser no longer depends on a Markdown fenced JSON block for normal executor/reviewer success.
- Missing fields produce a clear validation error naming the missing fields.
- Invalid enum values produce a clear validation error naming the field and invalid value.
- Run records include both raw output and parsed structured outcome.
- Existing successful executor/reviewer flows continue to work after migration.

### 2. Structured-output repair retry

When an agent completes but omits or malforms the structured outcome, Purser should attempt a bounded repair before failing the run.

Required behavior:

- Detect missing structured outcome, malformed JSON, or schema validation failure.
- Re-prompt the model with the raw run transcript and the required schema.
- Ask for only the corrected structured outcome.
- Limit repair attempts, for example to one or two retries.
- Mark the run failed if repair does not produce a valid outcome.

Acceptance criteria:

- A run that returns prose but contains enough information to infer the outcome can be repaired into a valid structured outcome.
- A run that truly lacks enough information fails with a clear error.
- Repair attempts are recorded in the run record.
- Purser does not silently fabricate success when the work cannot be verified.

### 3. Prompt and lifecycle alignment

Purser's static role prompts and runtime prompts must agree on Beads lifecycle responsibilities.

Observed conflict:

- Static executor role: `Move the bead to in-review when complete.`
- Runtime instruction: `leave the bead in progress/open for Purser to mark review-ready.`

Required behavior:

- Choose a single lifecycle model.
- Update executor role prompts, reviewer role prompts, and runtime appended instructions to match.
- Document which component changes Beads status: the agent or Purser orchestration.

Recommended model:

- Executor performs work and emits structured outcome.
- Purser orchestration updates Beads status based on the structured outcome.
- Reviewer reviews work and emits structured outcome.
- Purser orchestration closes/reopens/updates Beads based on review outcome.
- Agents should not invent custom review statuses.

Acceptance criteria:

- No Purser prompt simultaneously tells the agent to both move a bead to review and leave it open for Purser.
- Lifecycle state transitions are documented.
- Failed executor runs leave a clear Beads note or run record explaining whether the bead was untouched, partially modified, or ready for manual recovery.

### 4. Decision bead execution path

Purser should handle decision beads as first-class workflow items rather than forcing them through a code-build path.

Decision beads may require:

- reading a spec,
- recording a decision comment,
- creating follow-up beads,
- updating dependencies,
- closing the decision bead or marking it ready for review,
- running no code gates.

Required behavior:

- Detect `issue_type=decision` or equivalent Beads type.
- Use a decision-specific executor prompt.
- Do not require source code changes.
- Do not require code gates unless the bead explicitly asks for them.
- Require a decision record to be written to Beads.
- Require follow-up beads for intentional deferrals when the bead asks for them.

Acceptance criteria:

- A decision bead can complete successfully without files changed.
- The structured outcome can report `files_touched: []` and `gates_run: []`.
- Decision comments are visible through `bd show <id>`.
- Follow-up beads created by the decision run are listed in the structured outcome.

### 5. Planner idempotency and timeout recovery

Planner runs should be safe to retry after shell timeout, model timeout, or partial Beads creation.

Required behavior:

- Assign a stable planner run ID for each spec planning attempt.
- Record planned bead IDs before or during creation.
- Detect existing beads for the same spec and planning run.
- On retry, avoid duplicate bead creation unless the user explicitly requests regeneration.
- If a timeout occurs after partial creation, summarize what was created and what remains unknown.

Acceptance criteria:

- Retrying `purser planner-plan <spec>` after a timeout does not duplicate previously created beads.
- Purser can report whether planning is complete, partial, failed, or unknown.
- Purser provides a command or run summary that lists all beads created for a spec.
- Planner-created Beads include enough metadata to associate them with the spec and planner run.

### 6. Preserve exact spec literals in generated Beads

Planner-generated Beads must preserve exact file paths, commands, and Markdown code literals from specs.

Observed issue:

Generated acceptance criteria displayed missing literals, for example text resembling:

```text
A decision is recorded for whether v0.2 includes a note creation command such as  so  can stop using a direct Python snippet.
```

The missing text should have preserved code literals such as `dex notes add` and `.pi/skills/dex/scripts/record_note.sh`.

Required behavior:

- Preserve inline code spans from specs in Bead titles, descriptions, and acceptance criteria.
- Preserve fenced code block contents when relevant.
- Escape shell-sensitive characters safely when invoking `bd create`.
- Prefer API/JSON-based Beads creation over shell-quoted strings where possible.

Acceptance criteria:

- Generated Beads retain exact command literals such as `uv run dex profile <file>`.
- Generated Beads retain exact file paths such as `.pi/skills/dex/scripts/record_note.sh`.
- Acceptance criteria do not silently drop backticked content.
- Tests cover specs with inline code spans, fenced code blocks, angle brackets, quotes, and shell metacharacters.

### 7. Beads auto-export diagnostics

Purser should help diagnose Beads warnings that occur during workflow operations.

Observed warning:

```text
Warning: auto-export: git add failed: exit status 1
```

Required behavior:

- Capture Beads warnings emitted during Purser runs.
- Include warnings in run records and human summaries.
- If possible, identify likely causes, such as ignored paths, missing git repository, or conflicting Beads export configuration.
- Do not treat warnings as success if they imply Beads state may not have been exported or persisted as expected.

Acceptance criteria:

- Purser run summaries include Beads warnings.
- Purser diagnostics include enough context to reproduce the failed Beads command.
- Documentation explains expected Beads modes for repo-local embedded usage.

### 8. Human-readable diagnostics and recovery commands

Purser failure output should tell the operator what happened and what to do next.

Required behavior:

- On structured outcome failure, print the run record path.
- Print whether source files changed according to git status, if available.
- Print the current Beads status for the bead.
- Suggest safe next commands.

Example failure summary:

```text
Executor failed: missing structured outcome.
Run record: .purser/runs/<timestamp>-executor-<bead>.json
Bead status: in_progress
Git status: 2 modified files, 1 untracked file
Suggested next steps:
  1. Inspect the run record.
  2. Run `purser repair-outcome <run-id>` or rerun `purser exec-build <bead>`.
  3. If manual recovery is needed, add a Beads comment and update/close the bead explicitly.
```

Acceptance criteria:

- Executor and reviewer failures include actionable diagnostics.
- The user does not need to inspect raw JSON manually for common failures.
- Recovery commands are documented.

## Files and areas likely to change

Exact file paths should be adapted to the Purser repository layout. Likely areas include:

- CLI command implementation for `purser exec-build`
- CLI command implementation for `purser planner-plan`
- executor role prompt templates
- reviewer role prompt templates
- planner prompt templates
- run record schema/types
- structured outcome parser/validator
- Beads integration layer
- tests for planner/executor/reviewer behavior
- documentation for Purser workflows and recovery

Known prompt file from the observed environment:

- `.purser/prompts/roles/executor-role.md`

## Test requirements

Add automated tests for:

1. Successful executor structured outcome parsing.
2. Missing structured outcome repair path.
3. Malformed JSON repair path.
4. Schema validation failure with clear diagnostics.
5. Decision bead execution with no files touched and no gates run.
6. Prompt lifecycle consistency checks.
7. Planner retry after partial bead creation.
8. Planner preservation of inline code literals and fenced code blocks.
9. Beads warning capture in run summaries.
10. Failure summary includes run path, Beads status, git status, and suggested recovery commands.

Where possible, tests should use fake/model-stub responses rather than live model calls.

## Validation commands

Use the Purser project's actual validation commands. If unknown, define or update them during planning.

Suggested validation categories:

```bash
# Unit tests
<project test command>

# Type checks, if configured
<project typecheck command>

# Lint/format checks, if configured
<project lint command>
<project format-check command>

# Integration smoke tests with stubbed model responses
<project integration test command>
```

Manual validation scenarios:

```bash
# Executor returns valid structured outcome
purser exec-build <simple-test-bead>

# Executor returns prose only; repair succeeds
purser exec-build <stubbed-prose-only-bead>

# Decision bead completes without code changes
purser exec-build <decision-bead>

# Planner timeout/partial retry does not duplicate beads
purser planner-plan <test-spec>
purser planner-plan <test-spec>
```

## Acceptance criteria

This spec is complete when:

1. Executor/reviewer outcomes use schema-native structured parsing rather than normal success depending on Markdown-fenced JSON in prose.
2. Missing or malformed structured outcomes trigger bounded repair retries or clear failure diagnostics.
3. Executor/reviewer prompts have no lifecycle contradictions.
4. Decision beads can complete cleanly without source changes or code gates.
5. Planner runs are idempotent or safely recoverable after timeout/partial creation.
6. Planner-generated Beads preserve exact spec literals, including inline code spans and file paths.
7. Beads warnings are captured and surfaced in Purser summaries.
8. Purser failure messages include actionable recovery information.
9. Automated tests cover the reliability cases above.
10. Documentation explains the structured outcome contract, lifecycle responsibilities, and recovery flow.

## Open questions

1. Which component should own Beads status transitions: the agent, Purser orchestration, or a hybrid model?
2. Does Pi expose a schema-native structured output API that Purser can call directly, or should Purser parse raw JSON from `pi --mode json`?
3. Should structured-output repair use the same model as the failed run or a smaller deterministic model?
4. How should Purser identify duplicate planner output: by spec hash, planner run ID, generated bead metadata, title similarity, or a combination?
5. Should decision beads be automatically closed after a valid decision outcome, or routed through review like implementation beads?
