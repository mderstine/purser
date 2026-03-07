# Framework Resilience and Observability

## Job To Be Done
Make the Ralph-Beads loop robust against hangs, failures, and silent drift by adding timeouts, pre-flight checks, structured logging, and shared script utilities.

## Requirements

### Pre-flight Checks (loop.sh)
- Before entering the loop, verify clean git state (no uncommitted changes that could conflict with agent commits)
- Warn if the current branch is `main` (build work should typically happen on feature branches)
- Verify `bd prime` succeeds (beads database is accessible and not corrupted)
- Check that `claude` CLI is available and authenticated (fail fast instead of mid-iteration)

### Iteration Timeouts
- Add a configurable timeout per iteration (default: 15 minutes for build, 10 minutes for plan)
- Use `timeout` command or bash `SIGALRM` to kill hung Claude invocations
- Log timeout events clearly so the user knows the iteration was killed, not just failed
- On timeout, do NOT close the beads issue -- leave it claimed so the next iteration can retry or the user can intervene

### Structured Iteration Logging
- Write iteration logs to a project-local directory (`logs/`) instead of `/tmp/`
- Each log file named with timestamp and iteration number: `logs/build-2026-03-06T14:30:00-iter-3.log`
- After each iteration, append a one-line summary to `logs/summary.jsonl` with: iteration number, start time, duration, exit code, beads issue ID (if build mode), outcome (success/timeout/error)
- Add a `./loop.sh status` command that reads `logs/summary.jsonl` and prints iteration stats (total, success rate, avg duration, last N outcomes)

### Signal Handling
- Trap SIGINT/SIGTERM in loop.sh for graceful shutdown
- On signal: wait for current Claude process to exit (with a grace period), print summary, then exit
- Do not leave orphaned Claude processes running after Ctrl+C

### Shared Script Utilities
- Extract duplicated functions (`run()`, `slugify()`, `get_commit_for_issue()`, `get_repo_url()`) from gh-sync.sh, gh-triage.sh, gh-changelog.sh, and gh-pr-body.sh into a shared `scripts/lib.py` module
- Each script imports from `lib.py` instead of defining its own copy
- Shared module includes: subprocess runner, beads issue loader, GitHub issue number extractor, repo URL resolver, slugify, commit SHA lookup

### Argument Parsing Hardening
- Fix `loop.sh` arg parsing: `*[0-9]*` matches any string containing a digit (e.g., "v2-feature" would be parsed as max iterations)
- Use stricter pattern: only match strings that are purely numeric

## Constraints
- Changes to loop.sh must be backward-compatible with existing usage patterns
- Log directory must be gitignored (add to .gitignore)
- Shared lib.py must not introduce new external dependencies beyond Python stdlib
- Timeout mechanism must work on both Linux and macOS

## Notes
- The `PIPESTATUS` handling on line 96 of loop.sh (`${PIPESTATUS[1]:-0}`) may not capture exit codes correctly when piped through `tee` -- investigate and fix if needed
- Current `/tmp/ralph-beads-iter-*.log` files are ephemeral and lost on reboot -- project-local logs solve this
- The `run()` function appears in 4 separate scripts with slightly different error handling -- consolidation will reduce maintenance burden
