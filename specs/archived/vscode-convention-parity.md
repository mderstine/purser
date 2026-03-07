# VS Code Convention Parity

## Job To Be Done
Convert all Claude Code-specific configuration files to VS Code Copilot equivalents so the ralph-beads framework is fully operable from VS Code with GitHub Copilot agents.

## Requirements
- `.claude/commands/*.md` slash commands have equivalent VS Code Copilot prompt files (`.github/prompts/*.prompt.md`) for: plan, build, status, add-spec, create-issue
- `.github/copilot-instructions.md` contains all guidance currently in `CLAUDE.md` that is relevant to VS Code agents (beads workflow, quality gates, project structure)
- `AGENTS.md` is either VS Code-compatible as-is or has a VS Code-specific equivalent that agents load at session start
- VS Code agent sessions can invoke the plan loop (specs → task graph) and build loop (claim → implement → test → commit → close) without Claude Code
- Prompt files use VS Code prompt file conventions (`mode`, `tools`, `description` front matter where applicable)
- A human-readable mapping document explains which Claude Code file maps to which VS Code file

## Constraints
- VS Code 1.108.2+ Copilot agent mode only — no extensions beyond GitHub Copilot
- `.claude/` directory and its contents must remain intact (framework must still work in Claude Code)
- VS Code prompt files live in `.github/prompts/` per VS Code conventions
- Memory/persistence between sessions is out of scope (no VS Code equivalent for `.claude/projects/*/memory/`)

## Notes
- Claude Code slash commands use `.claude/commands/<name>.md` with `$ARGUMENTS` substitution
- VS Code Copilot prompt files use `.github/prompts/<name>.prompt.md` with YAML front matter (`mode: agent`, `description: ...`)
- The existing `.github/copilot-instructions.md` already covers the build workflow but may be missing content from `CLAUDE.md` (roles, loop structure, key commands)
- Reference repo: https://github.com/mderstine/beads-vscode-agents has patterns for `.github/agents/` and `.github/skills/` that may inform prompt file structure
- Existing `.github/agents/beads-pm.agent.md` and `.github/agents/beads-dev.agent.md` may partially fulfill the agent role requirement
