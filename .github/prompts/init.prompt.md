---
mode: agent
description: Initialize a new Purser project. Run the init script and guide the user through setup.
tools:
  - run_terminal_cmd
  - read_file
  - list_dir
---

Initialize a new Purser project in the current directory. Run the init script and guide the user through setup.

Steps:
1. Run `./init.sh --check` to verify prerequisites (git, python3, gh, bd)
2. If prerequisites pass, run `./init.sh` to perform full initialization:
   - Initialize beads database (`bd init` if needed)
   - Detect or create GitHub remote
   - Detect or setup GitHub Project board
   - Bootstrap GitHub labels
   - Save configuration to `.purser.yml`
3. Report what was configured and print next steps

Options the user can pass as arguments:
- `--skip-github` — skip GitHub remote, project board, and label setup (local-only mode)
- `--check` — check prerequisites only, no changes made

After init completes, the recommended next steps are:
1. Write specs in `specs/` describing what you want to build
2. Invoke `@beads-pm` to convert specs into a dependency-aware task graph
3. Invoke `@beads-dev` to implement the first ready task
