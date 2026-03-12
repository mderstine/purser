---
mode: agent
description: Run the GitHub issue triage routine to convert spec-candidate issues into spec files, then enrich each new spec to production quality.
tools:
  - execute
  - read
  - edit
---

Run the GitHub issue triage routine to convert `spec-candidate`-tagged issues into spec files.

## Step 1 — Run triage

Run `uv run purser-loop triage` and note which spec files were newly created (not skipped).

If `--dry-run` was passed, stop after reporting the preview — do not enrich.

## Step 2 — Enrich each new spec

For each spec file that was **newly created** in Step 1, read the file and rewrite it in place with fully-populated sections. Use the GitHub issue title and body as source material.

The canonical spec structure is:

```markdown
# <Title>

> Source: GitHub Issue #N

## Job To Be Done
<One sentence describing the user outcome — what the user can do after this is built>

## Requirements
- <Specific, testable requirement>
- <Include inputs, outputs, error cases>
- <State acceptance criteria>

## Constraints
- <Technical constraints: language, framework, API format>
- <Performance requirements if applicable>

## Notes
- <Context that aids implementation>
- Triaged from GitHub Issue #N
```

Rules for enrichment:
- `## Job To Be Done` must be a single sentence — no "and", no bullet points
- `## Requirements` must have at least one specific, testable bullet point derived from the issue
- `## Constraints` — populate if the issue mentions technical constraints; omit filler if none apply
- Preserve the `> Source: GitHub Issue #N` provenance line exactly
- Preserve the `- Triaged from GitHub Issue #N` entry in Notes
- Do NOT enrich specs that already existed before this triage run

## Step 3 — Report

Present a structured summary:
- How many issues had the `spec-candidate` label
- Which issues were converted (title → filename)
- Which issues were skipped and why
- Confirmation that each new spec was enriched

Then suggest running the `plan` prompt to generate tasks from the new specs.
