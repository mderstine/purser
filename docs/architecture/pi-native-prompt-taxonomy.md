# Pi-native prompt taxonomy and naming contract

Status: accepted design note
Related spec: `specs/2026-04-23-pi-native-portable-purser-refactor.md`
Related plan: `docs/plans/2026-04-23-pi-native-portable-purser-refactor-plan.md`

## Purpose

This document defines the prompt taxonomy and naming contract for Purser's Pi-native architecture.

It exists to lock the naming and layout model before scaffold-generation and migration work proceeds.

## Core decision

Purser uses **two distinct prompt classes**:

1. **Runtime role prompts**
2. **Operator workflow prompts**

These classes are intentionally separated because they serve different purposes.

### Runtime role prompts

Runtime role prompts are used internally by the `purser` CLI when it invokes Pi for orchestration.

They are:

- machine-oriented
- stable orchestration contracts
- not the primary user-facing slash-command surface

### Operator workflow prompts

Operator workflow prompts are used manually by a human through Pi prompt discovery / slash-command usage.

They are:

- user-facing workflow entry points
- optimized for human operation and repo-local guidance
- the prompts intended to be exposed through `.pi/settings.json`

## On-disk layout contract

Purser's prompt layout under `.purser/` should be:

```text
.purser/
  prompts/
    roles/
      planner-role.md
      executor-role.md
      reviewer-role.md
    workflows/
      purser-add-spec.md
      purser-plan.md
      purser-build.md
      purser-build-all.md
```

### Notes

- `roles/` is the canonical location for runtime role prompts.
- `workflows/` is the canonical location for operator workflow prompts.
- Pi prompt-template discovery should point at the **workflow** prompt directory, not at the role prompt directory.
- This keeps internal orchestration prompts separate from user-facing slash commands.

## Runtime role prompt contract

The runtime role prompt filenames are:

- `planner-role.md`
- `executor-role.md`
- `reviewer-role.md`

These names are explicit on purpose:

- they distinguish runtime prompts from workflow prompts
- they remain readable in config and logs
- they avoid ambiguous overlap with slash-command-oriented prompt names

These prompts are used by Purser runtime configuration, for example:

```toml
[roles]
planner_prompt = ".purser/prompts/roles/planner-role.md"
executor_prompt = ".purser/prompts/roles/executor-role.md"
reviewer_prompt = ".purser/prompts/roles/reviewer-role.md"
```

## Operator workflow prompt contract

The operator workflow prompt filenames are:

- `purser-add-spec.md`
- `purser-plan.md`
- `purser-build.md`
- `purser-build-all.md`

These prompts represent the human-visible workflow surface for Pi.

### Slash-command mapping

When `.pi/settings.json` points at:

```json
{
  "prompts": ["../.purser/prompts/workflows"]
}
```

The intended prompt-template / slash-command mapping is:

```text
.purser/prompts/workflows/purser-add-spec.md   -> /purser-add-spec
.purser/prompts/workflows/purser-plan.md       -> /purser-plan
.purser/prompts/workflows/purser-build.md      -> /purser-build
.purser/prompts/workflows/purser-build-all.md  -> /purser-build-all
```

## Naming principles

The naming contract follows these principles:

1. **Explicit over implicit**
   - runtime prompts should look like runtime prompts
   - workflow prompts should look like workflow prompts

2. **Pi-native first**
   - names and layout are chosen for Pi discovery and Purser runtime clarity
   - they are not optimized around Claude/Codex/Copilot-native export surfaces

3. **Stable operator vocabulary**
   - workflow prompt names should match the user-facing verbs described in docs and onboarding material

4. **Low ambiguity in config**
   - role prompt paths in `.purser.toml` should be self-explanatory

## Public command vocabulary

The current intended public workflow vocabulary is:

- `purser-add-spec`
- `purser-plan`
- `purser-build`
- `purser-build-all`

These names are the stable operator-facing workflow names for Pi prompt discovery.

The current runtime CLI vocabulary remains separate and may continue to expose commands such as:

- `planner-intake-spec`
- `planner-plan`
- `exec-build`
- `exec-build-all`

A later refactor may choose to align or simplify CLI naming, but this document only locks the prompt taxonomy and prompt-file naming contract.

## Why this layout was chosen

This layout is preferred because it:

- cleanly separates internal orchestration prompts from operator prompts
- avoids exposing runtime-only prompts as the main Pi slash-command surface
- preserves explicit, readable file names
- gives later scaffold work a stable target

## Non-goals of this document

This document does not yet:

- define the final content of each prompt
- define migration mechanics from the old prompt layout
- define CLI command renaming
- define structured output schemas for runtime roles

Those concerns are handled by later beads.
