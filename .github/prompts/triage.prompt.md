---
mode: agent
description: Run the GitHub issue triage routine to convert spec-candidate issues into spec files.
tools:
  - execute
---

Run the GitHub issue triage routine to convert `spec-candidate`-tagged issues into spec files.

Run `uv run purser-loop triage` and present a structured summary:

- How many issues had the `spec-candidate` label
- Which issues were converted to spec files (title → filename)
- Which issues were skipped and why
- What spec files were created or updated in `specs/`

To preview without writing files, run `uv run purser-loop triage --dry-run` first.

After triage completes, suggest running the `plan` prompt to generate tasks from any newly created specs.
