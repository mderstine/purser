---
mode: agent
description: Run the Purser planning loop. Read all specs and create a dependency-aware task graph using beads (bd).
tools:
  - run_terminal_cmd
  - read_file
  - list_dir
  - file_search
---

Run the Purser planning loop. Read all specs in `specs/` and create a dependency-aware task graph using beads (`bd`).

Follow the instructions in PROMPT_plan.md exactly:
1. Study all specs in `specs/`
2. Run `bd prime` and `bd list --status open --json` to understand current state
3. Study `AGENTS.md` for project constraints
4. Perform gap analysis against existing code in `src/`
5. Create beads issues with proper priorities, types, and dependency links
6. Validate with `bd dep cycles` and `bd ready --json`

Report a summary of what was planned: total issues by type/priority, dependency structure, and what's ready to build first.
