# purser

`purser` is a project-agnostic orchestration CLI for driving Beads-based work with three Pi-hosted roles:

- Planner
- Executor
- Reviewer

It ships as a Python package with these CLIs:

- `purser`
- `purser-planner-intake-spec`
- `purser-planner-plan`
- `purser-exec-build`
- `purser-exec-build-all`

Utilities:
- `purser doctor`

## High-level flow

1. Intake a markdown spec.
2. Optionally synthesize/enhance it with the Planner.
3. Decompose the spec into beads and dependencies.
4. Execute one ready bead or loop until all reviewable beads are closed.
5. Validate each closed bead with a Reviewer and append to `VALIDATION.md`.

## Pi integration

Purser shells out to:

- `bd` for Beads operations
- `pi` in JSON mode for agent execution
- configured gate commands for lint/types/tests

Purser does not embed Pi or Beads as SDKs.

## Config

Project configuration lives at `.purser.toml` in the repo root.

## Health check

Run:

```bash
purser doctor
```

This verifies:
- `bd`, `dolt`, and `pi` are on `PATH`
- local config exists
- prompt files exist
- `bd context` can run in the current repo
