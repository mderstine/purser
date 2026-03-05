# Ralph-Beads

A unified framework for autonomous AI development combining Geoffrey Huntley's
[Ralph Loop](https://ghuntley.com/loop/) methodology with
[Beads](https://github.com/steveyegge/beads) dependency-aware issue tracking.

## What This Is

Ralph-Beads is a protocol for letting an AI agent build your software autonomously
while you direct it from the outside. You write **what** you want (specs). The
framework handles **how** to break it down, order it, and execute it — one task
at a time, in an infinite loop, with fresh context every iteration.

Your role shifts from writing code to writing requirements, watching the loop,
and tuning when it drifts.

## How It Works

Two concepts combine:

**The Ralph Loop** runs Claude Code in a bash `while` loop. Each iteration gets
fresh context (no hallucination buildup), implements one task, commits, and exits.
The loop restarts for the next task.

**Beads** (`bd`) replaces the original Ralph Loop's flat `IMPLEMENTATION_PLAN.md`
with a proper dependency graph. Tasks know what blocks them. The agent only works
on unblocked tasks. Discovered work gets linked back to its origin.

```
You write specs ──► Plan mode creates task graph ──► Build mode implements tasks
                         (bd issues)                    (one per loop iteration)
```

| Ralph Loop (original) | Ralph-Beads (this framework) |
|----------------------|------------------------------|
| `IMPLEMENTATION_PLAN.md` flat list | `bd` dependency graph (DAG) |
| LLM picks next task by reading markdown | `bd ready` returns unblocked work |
| No blocker awareness | `blocks` dependencies prevent premature work |
| Manual task discovery | `discovered-from` links capture emergent work |
| Single agent only | `--claim` enables multi-agent coordination |
| Plan drift requires regeneration | Graph stays accurate via atomic updates |

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI — `claude`
- [Beads](https://github.com/steveyegge/beads) CLI — `npm install -g @beads/bd`
- [Dolt](https://github.com/dolthub/dolt) — version-controlled SQL database
- Python 3.12+ (or adapt `AGENTS.md` for your stack)

## Getting Started

### 1. Install

```bash
git clone <this-repo>
cd ralph-beads

npm install -g @beads/bd
bd init --prefix myproject
```

### 2. Write Your Specs

Specs go in `specs/`, one file per **topic of concern**. A topic of concern is a
distinct aspect of your project that you can describe in one sentence without using
"and". If you need "and", split it into two specs.

```bash
cat > specs/auth.md << 'EOF'
# Authentication

## Job To Be Done
Users need to sign in with email/password and receive a JWT token.

## Requirements
- POST /auth/login accepts email + password, returns JWT
- Tokens expire after 24 hours
- Invalid credentials return 401
- Passwords are hashed with bcrypt before storage
EOF
```

```bash
cat > specs/user-profile.md << 'EOF'
# User Profile

## Job To Be Done
Authenticated users need to view and update their profile information.

## Requirements
- GET /users/me returns the current user's profile
- PATCH /users/me updates allowed fields (name, avatar)
- Profile changes require valid JWT in Authorization header
EOF
```

**Tips for writing good specs:**
- Be specific about inputs, outputs, and error cases
- Include technical constraints (database, framework, API format)
- State acceptance criteria — how will you know it's done?
- Don't prescribe implementation — say what, not how

### 3. Configure Your Stack

Edit `AGENTS.md` to match your project's build/test/lint commands. This file is
loaded every iteration, so the agent always knows how to validate its work:

```bash
# AGENTS.md — Build & Validate section

# Node.js example
npm test && npm run lint && npm run build

# Rust example
cargo test && cargo clippy && cargo build

# Go example
go test ./... && golangci-lint run
```

Also update the validation commands in `PROMPT_build.md` Phase 3 to match.

### 4. Run the Planning Loop

```bash
./loop.sh plan
```

This reads your specs and creates a dependency-aware task graph in beads. After it
runs, inspect the results:

```bash
bd list --status open     # See all created issues
bd ready                  # See what's unblocked and ready to build
bd dep tree <epic-id>     # Visualize dependency structure
```

**If the plan doesn't look right**, edit your specs and run `./loop.sh plan` again.
Planning iterations are cheap — the agent doesn't write code in this mode.

### 5. Run the Build Loop

```bash
./loop.sh
```

The agent will:
1. Query `bd ready` for the highest-priority unblocked task
2. Claim it (atomic — prevents conflicts)
3. Implement the work
4. Run your test/lint/build validation
5. Commit only if validation passes
6. Close the issue with context
7. Exit — loop restarts with fresh context for the next task

**It stops automatically when:** no ready work remains (all done or all blocked).

## How You Direct It

You are the director, not the coder. Here's how you steer:

### Before the Loop

| What you control | How |
|-----------------|-----|
| **What gets built** | Write specs in `specs/` |
| **Build order** | Beads dependencies (set during planning) |
| **Quality gates** | Test/lint/build commands in `AGENTS.md` |
| **Coding standards** | Patterns and constraints in `AGENTS.md` |
| **Agent behavior** | Instructions in `PROMPT_plan.md` / `PROMPT_build.md` |

### During the Loop

| Action | How |
|--------|-----|
| **Watch progress** | `bd list --status open` / `bd ready` |
| **Pause the loop** | `Ctrl+C` between iterations |
| **Skip a stuck task** | `bd close <id> --reason "skipped"` and restart |
| **Add urgent work** | `bd create "Hotfix: ..." -p 0 -t bug` |
| **Re-prioritize** | `bd update <id> --priority 0` |
| **Block something** | `bd dep add <task-id> <blocker-id> --type blocks` |
| **Check what's next** | `bd ready --json` |
| **View full state** | `bd prime` |
| **View iteration logs** | `cat /tmp/ralph-beads-iter-<N>.log` |

### After the Loop

| Action | How |
|--------|-----|
| **Review what was built** | `git log --oneline` |
| **Check remaining work** | `bd list --status open` |
| **Find what's blocked** | `bd list --status open` then `bd dep tree <id>` |
| **Add more specs** | Write new `specs/*.md`, run `./loop.sh plan` again |
| **Re-plan from scratch** | Close all issues, write new specs, re-plan |

### Tuning the Agent's Behavior

The framework gives you four "knobs" to turn:

**1. Specs** (`specs/*.md`) — Control *what* gets built. More detailed specs produce
more focused tasks. Vague specs produce vague implementations.

**2. AGENTS.md** — Control *how* the agent works. Add coding standards, known
gotchas, framework-specific patterns. This file accumulates learnings over time.
When the agent makes a mistake, add a note here so it doesn't repeat it.

**3. Prompt files** (`PROMPT_plan.md`, `PROMPT_build.md`) — Control the agent's
*process*. You rarely need to change these, but you can add guardrails (in the
numbered 999+ sections) or adjust phase instructions.

**4. Backpressure** (tests, lint, types) — Control *quality*. The agent cannot commit
code that fails validation. Stronger test suites produce more reliable output.
Write tests manually if needed to raise the quality bar.

### When Things Go Wrong

| Symptom | Fix |
|---------|-----|
| Agent implements the wrong thing | Improve the spec, re-plan |
| Agent keeps failing validation | Check `AGENTS.md` for missing patterns |
| Agent goes in circles | `Ctrl+C`, check the iteration log, add a guardrail to `AGENTS.md` |
| Task graph has wrong ordering | `bd dep add/remove` to fix dependencies |
| Agent works on low-priority stuff | `bd update <id> --priority 0` on the important task |
| Agent discovers too much side work | Add "minimize discovered issues" to `PROMPT_build.md` |
| Plan is stale | Re-run `./loop.sh plan` (cheap — no code changes) |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     loop.sh                              │
│  while true; do                                          │
│      cat PROMPT_build.md | claude -p                     │
│      bd sync                                             │
│  done                                                    │
└─────────────┬───────────────────────────────┬───────────┘
              │                               │
              ▼                               ▼
┌─────────────────────┐         ┌─────────────────────────┐
│   Claude Code        │         │   Beads (bd)             │
│   (fresh context)    │◄───────►│   (persistent state)     │
│                      │         │                          │
│   1. bd ready        │         │   ┌───┐  ┌───┐  ┌───┐  │
│   2. bd claim        │         │   │ A │──│ B │──│ C │  │
│   3. implement       │         │   └───┘  └───┘  └───┘  │
│   4. test/lint       │         │   dependency graph      │
│   5. commit          │         │   (DAG)                 │
│   6. bd close        │         │                          │
│   7. exit            │         │   .beads/issues.jsonl   │
└─────────────────────┘         └─────────────────────────┘
```

**Why this works:**
- **Fresh context** each iteration prevents hallucination accumulation
- **Deterministic task selection** via `bd ready` — not LLM guesswork
- **Backpressure** (tests/lint) forces correctness before commits
- **Git-backed state** survives context resets and machine restarts
- **Dependency graph** ensures work happens in the right order

### Steering Model

```
         ┌─────────────────────────────────────────┐
         │          UPSTREAM (you control)          │
         │                                          │
         │  specs/     →  what to build             │
         │  AGENTS.md  →  how to build              │
         │  PROMPT_*.md → agent process             │
         │  code patterns → implementation style    │
         └────────────────────┬────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   Claude Code     │
                    │   (one iteration) │
                    └────────┬─────────┘
                              │
                              ▼
         ┌─────────────────────────────────────────┐
         │         DOWNSTREAM (backpressure)        │
         │                                          │
         │  tests     →  correctness                │
         │  linter    →  style compliance            │
         │  types     →  type safety                │
         │  bd ready  →  dependency ordering         │
         └─────────────────────────────────────────┘
```

You push intent **downstream** through specs and standards.
Quality gates push **back upstream** by rejecting bad implementations.
The agent lives in the middle, squeezed into producing correct code.

## File Structure

```
ralph-beads/
├── loop.sh              # Ralph Loop orchestrator
├── PROMPT_plan.md       # Planning mode prompt
├── PROMPT_build.md      # Build mode prompt
├── AGENTS.md            # Operational guide (loaded every iteration)
├── CLAUDE.md            # Claude Code project instructions
├── specs/               # YOUR requirements (one per topic of concern)
│   └── *.md
├── src/                 # Application source code (agent writes here)
├── tests/               # Test suite
└── .beads/              # Beads database (managed by bd — don't edit)
    ├── config.yaml
    ├── issues.jsonl     # Git-tracked issue export
    └── dolt/            # Dolt database
```

## Multi-Agent Setup

Run multiple agents in parallel. Beads prevents conflicts via atomic claiming:

```bash
# Terminal 1
BD_ACTOR=agent-1 ./loop.sh

# Terminal 2
BD_ACTOR=agent-2 ./loop.sh
```

Each agent will claim different tasks. If agent-1 claims task A, agent-2 skips it
and picks the next ready task.

## Adapting for Non-Python Projects

1. Update `AGENTS.md` Build & Validate section with your commands
2. Update `PROMPT_build.md` Phase 3 with the same commands
3. Replace `src/` and `tests/` with your project's structure
4. Update `pyproject.toml` or replace with your package manager config

## Concepts & Terminology

| Term | Meaning |
|------|---------|
| **Ralph Loop** | Bash `while` loop feeding prompts to Claude Code |
| **Beads** | Git-backed dependency-aware issue tracker (`bd` CLI) |
| **Spec** | Requirements document in `specs/` — one per topic of concern |
| **Topic of concern** | A distinct project aspect describable in one sentence |
| **Backpressure** | Tests/lint/types that reject bad code before commit |
| **Upstream steering** | Specs, AGENTS.md, prompts — what you write to direct the agent |
| **Downstream steering** | Validation gates that force quality |
| **Discovered work** | Issues the agent finds mid-implementation and files for later |
| **Ready work** | Issues with no unresolved blockers (`bd ready`) |
| **Claiming** | Atomic lock on an issue to prevent multi-agent conflicts |

## Credits

- **Ralph Loop**: [Geoffrey Huntley](https://ghuntley.com/loop/)
- **Ralph Playbook**: [Clayton Farr](https://github.com/ClaytonFarr/ralph-playbook)
- **Beads**: [Steve Yegge](https://github.com/steveyegge/beads)
- **Beads + VS Code Agents**: [mderstine](https://github.com/mderstine/beads-vscode-agents)

## License

MIT
