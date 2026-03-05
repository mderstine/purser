Run one iteration of the Ralph-Beads build loop. Implement exactly ONE task, then stop.

Follow the instructions in PROMPT_build.md exactly:
1. Run `bd ready --json` to find unblocked work
2. Pick the highest-priority ready issue
3. Claim it: `bd update <id> --claim --json`
4. Read the issue details: `bd show <id> --json`
5. Implement the work described in the issue
6. Run validation (tests/lint/build) per AGENTS.md
7. If validation fails, fix and retry until green
8. If you discover new work, file it: `bd create "Discovered: ..." --deps discovered-from:<id>`
9. Commit the implementation
10. Close the issue: `bd close <id> --reason "..." --json`

Do NOT pick up additional tasks. One task only.

$ARGUMENTS
