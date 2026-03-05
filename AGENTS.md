# Operational Guide

This file is loaded at the start of every Ralph Loop iteration.
It contains project-specific patterns, constraints, and learnings.

## Build & Validate

```bash
# Run tests
python -m pytest tests/ -v

# Type checking
python -m mypy src/ --strict

# Lint
python -m ruff check src/ tests/

# Build
python -m build
```

## Beads CLI Reference

```bash
bd ready --json              # Unblocked work — what to do next
bd show <id> --json          # Issue details + dependencies
bd update <id> --claim       # Claim work atomically
bd close <id> --reason "..." # Complete work
bd create "Title" -p <0-4> -t <type> --deps discovered-from:<id> --json
bd dep tree <id>             # Visualize dependency graph
bd sync                      # Sync to git
bd prime                     # Session context summary
```

## Coding Standards

- Python 3.12+
- Type annotations on public APIs
- Tests for all new functionality
- Keep functions small and focused

## Known Patterns & Gotchas

<!-- Add learnings here as you discover them -->
<!-- Example: "bd sync must run before git commit to ensure JSONL is current" -->
