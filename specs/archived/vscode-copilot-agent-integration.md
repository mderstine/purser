# VS Code Copilot Agent Integration

## Job To Be Done
Enable GitHub Copilot agents in VS Code to autonomously execute the ralph-beads framework loop (plan, claim, implement, test, commit, close).

## Requirements
- Copilot agent instructions that encode the ralph-beads build loop (`bd ready` -> implement -> `bd close`)
- Copilot agent instructions that encode the ralph-beads planning loop (specs -> beads task graph)
- Agent can read specs from `specs/`, interact with `bd` CLI, and commit results
- Agent follows AGENTS.md operational guide and respects quality gates
- Works with VS Code 1.108.2 agent mode (`.github/copilot-instructions.md` or equivalent)
- One-task-per-iteration discipline is preserved
- Backpressure checks (tests/lint/build) run before commits
- Agent discovers and links new work with `discovered-from` dependencies

## Constraints
- Must use VS Code 1.108.2's Copilot agent APIs and instruction formats
- Must not require extensions beyond what ships with VS Code + GitHub Copilot
- `bd` CLI must be available on PATH in the agent's shell environment
- Git operations must work within the agent's sandbox/permissions model

## Notes
- User has an existing reference repo: https://github.com/mderstine/beads-vscode-agents (VS Code Copilot Agent integration for beads with agents like beads-pm, beads-dev)
- The Ralph Loop (`loop.sh`) may not apply directly since Copilot agent mode has its own iteration model — the spec should address how the loop concept maps to agent mode
- VS Code 1.108.2 supports agent mode with `.github/copilot-instructions.md` for repo-level instructions and `chat.agent.instructions` setting
- A dedicated branch (`feat/vscode-copilot-agent`) should be created for this work
