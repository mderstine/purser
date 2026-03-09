"""Create/update GitHub labels for beads metadata sync.

Idempotent: skips labels that already exist (by name).
Cross-platform Python replacement for gh-labels.sh.

Usage:
    uv run python3 scripts/gh_labels.py              # Create labels
    uv run python3 scripts/gh_labels.py --dry-run    # Preview without creating
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cli_utils import require_commands, require_gh_auth, setup_logging  # noqa: E402

logger = setup_logging(__name__)

# ─── Label definitions ──────────────────────────────────────────────────────

LABELS: list[tuple[str, str, str, str]] = [
    # (category, name, color, description)
    # Issue types
    ("Issue types", "type:bug", "d73a4a", "Beads issue type: bug"),
    ("Issue types", "type:feature", "0e8a16", "Beads issue type: feature"),
    ("Issue types", "type:task", "1d76db", "Beads issue type: task"),
    ("Issue types", "type:epic", "5319e7", "Beads issue type: epic"),
    ("Issue types", "type:chore", "c5def5", "Beads issue type: chore"),
    # Priorities
    ("Priorities", "priority:0", "b60205", "P0: Critical (security, data loss, broken builds)"),
    ("Priorities", "priority:1", "d93f0b", "P1: High (major features, important bugs)"),
    ("Priorities", "priority:2", "fbca04", "P2: Medium (default)"),
    ("Priorities", "priority:3", "c2e0c6", "P3: Low (polish, optimization)"),
    ("Priorities", "priority:4", "e4e669", "P4: Backlog (future ideas)"),
    # Status/workflow
    ("Workflow", "blocked", "b60205", "Issue is blocked by dependencies"),
    ("Workflow", "spec-candidate", "006b75", "GitHub Issue to be triaged into a spec"),
    ("Workflow", "spec-created", "0e8a16", "Spec was generated from this issue"),
]


def get_existing_labels() -> set[str]:
    """Fetch existing label names from the GitHub repo."""
    result = subprocess.run(
        ["gh", "label", "list", "--json", "name", "-q", ".[].name"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def create_label(name: str, color: str, description: str, *, dry_run: bool) -> None:
    """Create a single GitHub label."""
    if dry_run:
        logger.info("  would create: %s (%s)", name, description)
    else:
        subprocess.run(
            ["gh", "label", "create", name, "--color", color, "--description", description],
            capture_output=True,
        )
        logger.info("  created: %s", name)


def setup_labels(*, dry_run: bool = False) -> None:
    """Create all beads GitHub labels, skipping any that already exist."""
    existing = get_existing_labels()

    logger.info("=== Beads GitHub Label Setup ===")
    logger.info("")

    current_category = ""
    for category, name, color, description in LABELS:
        if category != current_category:
            if current_category:
                logger.info("")
            logger.info("%s:", category)
            current_category = category

        if name in existing:
            logger.info("  skip: %s (exists)", name)
        else:
            create_label(name, color, description, dry_run=dry_run)

    logger.info("")
    logger.info("Done.")


def main() -> None:
    """CLI entry point."""
    if "-h" in sys.argv or "--help" in sys.argv:
        print("Usage: gh_labels.py [--dry-run]")
        print("Create GitHub labels for beads metadata sync.")
        return

    require_commands(["gh"])
    require_gh_auth()

    dry_run = "--dry-run" in sys.argv
    setup_labels(dry_run=dry_run)


if __name__ == "__main__":
    main()
