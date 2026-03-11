---
mode: agent
description: Give a project status report from the beads tracker.
tools:
  - execute
---

Give a project status report from the beads tracker.

Run these commands and present a structured summary:

1. `bd prime` — session context
2. `bd list --status open --json` — all open issues
3. `bd ready --json` — unblocked ready work
4. `bd dep cycles` — check for dependency cycles

Report:
- Total open issues (by priority breakdown: P0/P1/P2/P3/P4)
- Ready (unblocked) count and their titles
- Blocked count and what's blocking them
- Recently closed issues
- Recommended next actions
