# Beads Orchestrator: A Project-Agnostic Planner → Executor → Reviewer Loop

**Purpose.** Build a standalone, reusable orchestration package — call it `bd-orchestrator` — that drives any Python project forward using three cooperating Pi-hosted agent roles (Planner, Executor, Reviewer) coordinated through Steve Yegge's Beads issue tracker. The package is installed once, runs against any repo that has `bd init`'d, and has zero knowledge of what it's building. Dex will be its first real consumer; LangLang and any future projects can adopt it by dropping in a config file.

The core insight is the same as before: agents are unreliable, but a graph of small verifiable beads with hard machine-checkable gates is not. What changes when we make it project-agnostic is that **the orchestrator itself must not embed any project-specific assumptions** — not the gate commands, not the language, not the role prompts' domain knowledge, not the completion predicate. All of that becomes configuration.

---

## 1. Package shape

The deliverable is a pip-installable package exposing a single CLI entry point, `bd-orchestrate`, that operates on the current working directory. A project adopts it by doing three things: `bd init` (one-time Beads setup), drop a `.bd-orchestrator.toml` config file at the repo root, and write three role prompt files (or symlink the shipped defaults). That's the whole integration surface.

```
bd-orchestrator/
├── src/bd_orchestrator/
│   ├── __init__.py
│   ├── cli.py              # `bd-orchestrate` entry point
│   ├── config.py           # loads .bd-orchestrator.toml, validates schema
│   ├── loop.py             # the outer Ralph loop + state machine
│   ├── roles.py            # Pi subprocess invocation per role
│   ├── beads.py            # thin typed wrapper over `bd` JSON output
│   ├── gates.py            # runs configured back-pressure commands
│   ├── validation.py       # appends to VALIDATION.md
│   └── prompts/            # shipped default role prompts (overridable)
│       ├── planner.md
│       ├── executor.md
│       └── reviewer.md
├── tests/
└── pyproject.toml
```

The package depends on `bd` being on `$PATH` and a Pi binary being available — it shells out to both rather than linking them as libraries. This is the right call for two reasons: `bd` is a Go binary with a stable JSON contract (exactly the integration surface you want), and Pi's print/JSON mode is explicitly designed for process integration. Keeping the orchestrator as a subprocess conductor rather than an embedded SDK keeps it honest about the boundary and trivially swappable if you later want to try Amp or Codex as the role host.

## 2. What's project-specific, and where it lives

The project adopting the orchestrator owns a `.bd-orchestrator.toml` at its repo root. This is the only place project knowledge lives; everything the orchestrator does is parameterized by it.

```toml
[project]
name = "your-project-name"
language = "python"          # informational; used in default prompt substitution

[gates]
# Commands run in project root. Non-zero exit = gate failure.
# The orchestrator runs these in order; all must pass before a bead
# can transition to in-review or be closed.
lint    = "ruff check . && ruff format --check ."
types   = "ty check"         # or "mypy --strict src/"
tests   = "pytest -x --tb=short"

[loop]
max_iterations_per_bead = 5  # Executor→Reviewer cycles before escalating
branch_prefix = "bead/"      # Executor creates branches as bead/bd-0042
validation_log = "VALIDATION.md"

[roles]
# Paths are relative to repo root. If omitted, the shipped defaults are used.
planner_prompt  = ".bd-orchestrator/prompts/planner.md"
executor_prompt = ".bd-orchestrator/prompts/executor.md"
reviewer_prompt = ".bd-orchestrator/prompts/reviewer.md"

[roles.models]
# Per-role provider routing. Uses Pi's multi-provider config.
planner  = "anthropic/claude-opus-4-7"
executor = "groq/llama-3.3-70b"       # cheap + fast for the expensive role
reviewer = "anthropic/claude-opus-4-7" # judgment matters; spend here

[completion]
# Loop exits when this predicate is true. Default shown.
# "bd ready" empty AND no beads in [open, in-review, blocked].
require_empty_ready = true
forbid_open_statuses = ["open", "in-review"]
# "blocked" beads do NOT prevent loop exit — they're escalated to human.
```

Nothing in the orchestrator's source hard-codes `ruff`, `pytest`, or even Python. A JavaScript project could adopt this by setting `lint = "biome check ."`, `types = "tsc --noEmit"`, `tests = "vitest run"` and it would just work. The orchestrator's job is to sequence roles and enforce state transitions; the project's job is to say what "green" means.

## 3. Role prompts: shipped defaults plus project overrides

The three role prompts ship with the package and work out of the box, but any project can override them. The shipped defaults are **deliberately generic** — they reference "the spec" and "the codebase" and "the gates" without assuming anything about the domain. Project-specific context (coding conventions, architectural constraints, domain vocabulary) goes in the project's `AGENTS.md`, which Pi reads automatically on startup. This preserves the clean separation: the orchestrator ships the workflow, the project ships the context.

The prompts themselves are short and declarative. The Executor prompt, in full, is roughly:

> You are the Executor. You have been given exactly one bead ID. Your job:
> 1. Run `bd show <id> --json` and read the full bead plus linked spec references.
> 2. Create and check out a branch named `<branch_prefix><id>`.
> 3. Implement only what the bead's acceptance criteria require. If you discover work that is needed but out of scope, create a new bead with `bd create ... --discovered-from <id>`. Do not expand scope.
> 4. Run the configured gates until green. If a gate fails, fix and re-run.
> 5. Commit your work, then run `bd update <id> --status in-review`.
> 6. You may NOT run `bd close`. Only the Reviewer can close beads.

The Reviewer prompt is similarly tight, with an explicit tool allowlist. The Planner prompt is the longest because spec enhancement is the hardest role; it includes the "stop and ask" discipline and the atomicity heuristic for bead sizing.

## 4. The loop, as a state machine

The orchestrator's `loop.py` is a small state machine, not a framework. Given your LangLang work there's a real temptation to reach for LangGraph here, and I'd push back on that specifically: Ralph's thesis is that sophisticated orchestration is the wrong abstraction for this pattern. A ~200-line Python state machine gives you everything LangGraph would and nothing you don't need.

```python
def run(config: Config) -> ExitCode:
    while True:
        bd_sync()  # safe no-op if no remote configured

        if completion_predicate(config):
            return ExitCode.DONE

        # Prefer reviewing in-review beads before starting new ones;
        # this keeps WIP bounded and validation fresh.
        if bead := next_in_review():
            run_reviewer(bead, config)
            continue

        ready = bd_ready()
        if not ready:
            # Nothing ready, nothing in review, but predicate not met
            # => we have blocked beads. Escalate.
            return ExitCode.BLOCKED

        bead = ready[0]
        if bead.executor_attempts >= config.max_iterations_per_bead:
            bd_update(bead.id, status="blocked", note="iteration cap hit")
            continue

        run_executor(bead, config)
        # Executor transitions to in-review; next loop iteration picks it up.
```

Each `run_executor` / `run_reviewer` call spawns a fresh Pi subprocess with the appropriate role prompt, model, and bead ID. Fresh context per iteration is the Ralph insight — it prevents the "lost in the middle" drift that kills long sessions and forces each role to re-read state from Beads rather than trusting its own memory. The orchestrator parses Pi's JSON output, verifies the expected bead state transition happened, and loops.

The iteration cap per bead is the pressure-release valve. If a bead cycles Executor→Reviewer 5 times without closing, it gets marked `blocked` with a note summarizing what the Reviewer kept rejecting, and the loop moves on. This prevents one pathological bead from burning the entire run, and it surfaces the bead for human triage rather than silently spinning.

## 5. Back-pressure gates as a first-class contract

The gates are what make the Ralph pattern actually work. Without machine-verifiable green/red signal, the Reviewer degenerates into vibes. The orchestrator treats gate commands as opaque shell strings, but it enforces a strict contract around them:

- Gates run in a subprocess with a timeout (configurable, default 10 minutes).
- Exit code 0 is the only "pass" signal. stdout/stderr are captured and attached to the bead as a comment, whether pass or fail.
- The Executor cannot transition a bead to `in-review` until all gates pass on its branch.
- The Reviewer re-runs all gates on the merged-to-main state before closing. This catches merge-introduced regressions that passed on the branch but fail on main.
- A gate failure during review automatically reopens the bead with the captured output as the reopen note.

This gate-rerun-on-merge step is worth emphasizing: it catches the single most common Ralph-loop failure mode, where a bead passes in isolation but the integration breaks. Doing it in the Reviewer rather than in a separate CI step keeps the feedback loop tight.

## 6. The validation log

`VALIDATION.md` is the human-readable audit trail. Append-only, one section per closed bead, written by the Reviewer via a helper the orchestrator provides. The format is fixed so it's greppable and diffable:

```markdown
## BD-0042 — Add DuckDB connection pool

**Validated:** 2026-04-22T14:03Z
**Status:** closed
**Spec reference:** specs/memory-layer.md §3.2
**Commits:** a1b2c3d, e4f5g6h
**Executor attempts:** 2 (1 reopen: missing test for cleanup-on-exception)

### Summary
Implemented a connection pool wrapper around `duckdb.connect()` with configurable
max connections and a context-manager acquire pattern. 7 unit tests covering
pool exhaustion, reuse, and cleanup-on-exception.

### Verification
- lint: clean
- types: clean
- tests: 7/7 new, 142/142 total
- Acceptance criteria 1–4 satisfied; criterion 5 (metrics hook) deferred to BD-0051 (discovered).

### Notes
Pool is process-local; cross-process coordination out of scope per spec.
```

The "Executor attempts" field is the part most teams skip and shouldn't — it makes loop pathology visible in the log itself. A project where half the beads took 3+ attempts is telling you the Planner's bead sizing is wrong, and you want that signal.

## 7. Build order for the package itself

The orchestrator is, pleasingly, a good candidate for its own dogfood: build it as a Python project using a simpler bootstrap version of itself, then swap to self-hosting once it works.

1. **Scaffold.** `pyproject.toml`, `src/bd_orchestrator/`, `ruff`+`ty`+`pytest` configured. CI that runs the gates on every push.
2. **`beads.py`** — thin typed wrapper over `bd`'s JSON output. This is where you eat the cost of `bd` CLI changes; everything else in the package talks to `beads.py`, not to `bd` directly.
3. **`gates.py`** — subprocess runner with timeout, output capture, and the "attach to bead as comment" behavior. Small, tested in isolation.
4. **`roles.py`** — Pi subprocess invocation. Takes a role name, a bead ID, a model string, and a prompt path; returns a structured result. This is where per-role model routing lives.
5. **`loop.py`** — the state machine above. Pure function of `(beads state, config) → next action`, so it's testable without ever shelling out.
6. **`cli.py`** — argparse, config loading, the `while` loop that threads it all together.
7. **Ship default prompts** under `prompts/` in the package, with a `bd-orchestrate init` subcommand that copies them into a project's `.bd-orchestrator/prompts/` for local customization.
8. **Dogfood.** Point it at Dex. The first 3–5 beads of Dex's real work will surface every hole in the package; file those as beads against the orchestrator itself and let it fix its own issues.

## 8. How Dex consumes it

Dex's integration is three files: `.bd-orchestrator.toml` at its repo root with the Dex-specific gate commands and model routing, a `specs/` directory where Planner-enhanced specs land, and an `AGENTS.md` with Dex's coding conventions (which Pi reads automatically regardless of role). That's it. Dex never imports from `bd_orchestrator`; it just runs `bd-orchestrate` as a CLI tool in its repo. Same story for LangLang, same story for the next project.

The reusability test is clean: if adopting `bd-orchestrator` in a new project takes more than writing one TOML file and running `bd init`, we've leaked project assumptions into the package and need to push them back out.

## 9. Design decisions worth flagging

**Subprocess boundary, not SDK.** The orchestrator shells out to `bd` and `pi` rather than linking them. This preserves the project-agnostic property — the orchestrator doesn't know or care what Pi is talking to, so swapping Pi for Amp later is a config change. It also avoids version-coupling the orchestrator to Pi's internals.

**Reviewer is strictly read-only on source.** Via the Reviewer prompt and, ideally, by running the Reviewer's Pi session with a restricted tool allowlist (Pi extensions support this). The Reviewer can read files, run gates, update bead status, and append to `VALIDATION.md`. It cannot edit source. This is what makes the review real rather than a rubber stamp.

**Executor cannot self-close.** Enforced in prompt and verified in the orchestrator: after an Executor run, the orchestrator confirms the bead is in `in-review`, not `closed`. If the Executor somehow closed it, the orchestrator reopens it and logs the violation. Belt and suspenders, but the self-closure failure mode is severe enough to warrant it.

**Provider routing per role.** The expensive role (Executor — lots of tokens, iterative) goes to a cheap/fast provider; the judgment roles (Planner, Reviewer) go to the strongest model you have access to. Given your Claude Code throttling experience, this is also how you keep the loop running when one provider is rate-limiting you.

**`--discovered-from` is the scope discipline.** Any time a role wants to do "just one more thing," they file a new bead with `--discovered-from <current>` instead of expanding scope. This keeps beads atomic and keeps the Reviewer's job tractable. Planner should reserve the right to triage discovered beads into a backlog milestone rather than letting them block the current loop's completion predicate — otherwise the graph grows faster than it closes and you never reach "done."

**Human checkpoint after Planner, at least initially.** A bad DAG is unrecoverable downstream; catching it once at the top is cheap. Make this a config flag (`[loop] human_approve_plan = true`) so projects can opt out once they trust their Planner prompt.

## 10. What I'd build next after the MVP works

Not in scope for v1, but worth naming so the v1 design doesn't foreclose them:

- A `bd-orchestrate status` subcommand that renders the current bead graph and loop state — useful for the moments when you want to check in on a long-running loop without tailing logs.
- Optional Slack/email notification on `blocked` transitions, since those are the cases that need you.
- A "replay" mode that takes a closed bead and re-runs the Reviewer against it — useful for regression-testing prompt changes.
- Integration with the DuckDB-backed episodic memory pattern you've been exploring, so roles can query "what did we learn from similar beads" rather than relying on `AGENTS.md` alone. This is where LangLang's memory work and this orchestrator naturally converge — and why keeping them decoupled now matters.
