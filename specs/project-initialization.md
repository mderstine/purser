# Project Initialization

## Job To Be Done
Provide a cross-platform initialization routine that bootstraps a new Ralph-Beads project from the GitHub template, detects or creates a remote GitHub repository, and configures GitHub Projects integration through guided prompts or a config file.

## Requirements

### Init Entry Point
- A top-level `init` command (e.g., `./init.sh` on Unix, `init.ps1` on Windows, or a polyglot approach) that walks the user through first-time setup
- Detects the host OS and shell environment to select the appropriate script variant
- Idempotent — safe to re-run; skips already-completed steps and updates config for changed values

### Agent-Agnostic Design
- The init routine must work identically whether invoked from Claude Code CLI, VS Code with GitHub Copilot, or manually from a terminal
- No hard dependency on any specific AI agent or CLI tool — the framework is agent-agnostic
- Agent-specific configuration (e.g., `CLAUDE.md`, `.github/copilot-instructions.md`) is detected and preserved but not required

### Local Setup
- Verifies prerequisites are installed: `git`, `python3`, `gh` CLI, `bd` CLI
- Reports missing prerequisites with install instructions per platform (macOS/Homebrew, Ubuntu/apt, Windows/winget or scoop)
- Initializes the beads database (`bd init`) if `.beads/` doesn't exist
- Creates the project config file (`.ralph-beads.yml`) with defaults if it doesn't exist

### GitHub Remote Detection and Creation
- Checks `git remote -v` for a GitHub remote (origin or other named remotes)
- If no remote exists, **prompts the user** to create a new GitHub repository via `gh repo create`
- The user may decline repo creation — local-only operation is fully supported
- The prompt behavior can be controlled via config (`github.auto_create: prompt | skip | auto`)
- If a remote exists, validates it is accessible via `gh` CLI (authenticated and has push access)
- Stores the resolved GitHub owner/repo in the project config file

### GitHub Project Detection
- If a GitHub remote is configured, checks for associated GitHub Projects (v2)
- If exactly one project exists, offers to use it automatically
- If multiple projects exist, presents a selection menu
- If no project exists, offers to create one with default columns (Backlog, Ready, In Progress, Done)
- Stores the selected project number/ID in the project config file

### Configuration File
- Use `.ralph-beads.yml` in the repo root as the single source of configuration
- Structure:
  ```yaml
  github:
    remote: origin           # git remote name
    owner: <detected>        # GitHub owner/org
    repo: <detected>         # GitHub repo name
    auto_create: prompt      # prompt | skip | auto
    project_number: <detected or selected>
  labels:
    bootstrap: true          # whether gh-labels.sh has been run
  ```
- All scripts (`gh-sync.sh`, `gh-project.sh`, `gh-triage.sh`, etc.) read from this config instead of re-detecting each run
- The config file is `.gitignore`-safe by default (user opts in to committing it)
- Environment variables override config file values (e.g., `RALPH_BEADS_GITHUB_AUTO_CREATE=skip`)

### Template Readiness
- When the repo is created from the GitHub template, the init routine detects it's a fresh clone (no `.beads/`, no config file) and runs full setup
- Clears or resets any template-specific state (e.g., template's own beads issues, sample specs)
- Prints a summary of what was configured and suggests next steps (`./loop.sh plan`)

## Constraints
- Must work on macOS, Linux, and Windows (WSL or native PowerShell)
- Uses `gh` CLI for all GitHub operations — no raw API calls or token management
- Must not require any dependencies beyond what the framework already needs (git, python3, gh, bd)
- Init must work offline for local-only setup (GitHub steps are skippable)
- Config file format must be readable by both bash scripts and Python without external libraries (YAML via Python's standard approach, or consider TOML if Python 3.11+ is the minimum)

## Notes
- This repo will become a GitHub template repository — init is the first thing a user runs after "Use this template"
- The existing scripts already do ad-hoc detection (e.g., `gh repo view`); init centralizes and caches these results
- Consider a `.ralph-beads.example.yml` checked into the template with commented defaults
- The init routine should be the single entry point that replaces scattered prerequisite checks across scripts
- Must work equally well from VS Code terminal (Copilot agent workflows) and Claude Code CLI sessions
