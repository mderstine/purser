#!/usr/bin/env python3
"""Purser Project Initialization.

Bootstraps a new Purser project from the GitHub template.
Idempotent — safe to re-run; skips completed steps.
Cross-platform Python replacement for init.sh.

Usage:
    python3 scripts/init.py              # Interactive setup
    python3 scripts/init.py --check      # Check prerequisites only, no prompts
    python3 scripts/init.py --skip-github # Skip all GitHub integration steps

Steps:
    1. Check prerequisites (git, python3, uv, gh, bd)
    2. Create Python virtual environment (uv venv + uv sync)
    3. Initialize beads database if needed
    4. Detect/create GitHub remote
    5. Detect/setup GitHub Project
    6. Bootstrap GitHub labels
    7. Save configuration to .purser.yml
    8. Print summary and next steps
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import config  # noqa: E402
import gh_labels  # noqa: E402
import gh_project_setup  # noqa: E402
import gh_remote  # noqa: E402
import prereqs  # noqa: E402

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command with sensible defaults."""
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("timeout", 60)
    try:
        return subprocess.run(cmd, **kwargs)
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, returncode=127, stdout="", stderr="not found")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, returncode=124, stdout="", stderr="timeout")


def _print_header() -> None:
    print()
    print("=========================================")
    print("  Purser Project Initialization")
    print("=========================================")
    print()


def _print_step(step: int, desc: str) -> None:
    print(f"--- Step {step}: {desc} ---")


# ─── Steps ───────────────────────────────────────────────────────────────────


def step_prerequisites(*, check_only: bool) -> bool:
    """Step 1: Check prerequisites. Returns True if OK to continue."""
    _print_step(1, "Checking prerequisites")

    result = prereqs.check_prerequisites()
    prereqs.print_report(result)
    print()

    if not result["all_ok"]:
        print("Some prerequisites are missing. Install them and re-run init.")
        tool_map = {t["name"]: t["found"] for t in result["tools"]}
        if not (tool_map.get("git", False) and tool_map.get("python3", False)):
            print("ERROR: git and python3 are required. Cannot continue.")
            sys.exit(1)
        print("WARNING: Continuing with available tools (some features may be limited).")
        print()

    if check_only:
        print("Check complete.")
        sys.exit(0)

    return True


def step_venv() -> None:
    """Step 2: Create Python virtual environment."""
    _print_step(2, "Python virtual environment (uv)")

    if shutil.which("uv") is None:
        print("  WARNING: uv not found — skipping virtual environment setup.")
        print("  Install uv and re-run init to set up the environment.")
        print()
        return

    venv_dir = REPO_ROOT / ".venv"
    if venv_dir.is_dir():
        print("  .venv/ directory exists — syncing dependencies...")
        result = _run(["uv", "sync", "--project", str(REPO_ROOT)])
        if result.returncode != 0:
            print("  WARNING: uv sync failed. Dependencies may be out of date.")
    else:
        print("  Creating virtual environment...")
        result = _run(["uv", "venv", str(venv_dir)])
        if result.returncode != 0:
            print("  WARNING: uv venv failed.")
        print("  Installing dependencies...")
        result = _run(["uv", "sync", "--project", str(REPO_ROOT)])
        if result.returncode != 0:
            print("  WARNING: uv sync failed.")

    print("  Virtual environment ready.")
    print()


def step_beads_db() -> None:
    """Step 3: Initialize beads database."""
    _print_step(3, "Beads database")

    beads_dir = REPO_ROOT / ".beads"
    if beads_dir.is_dir():
        print("  .beads/ directory exists — skipping initialization.")
        # Count existing issues
        result = _run(["bd", "list", "--json"])
        if result.returncode == 0 and result.stdout.strip():
            try:
                count = len(json.loads(result.stdout))
            except json.JSONDecodeError:
                count = 0
        else:
            count = 0
        print(f"  Current issues: {count}")
    else:
        print("  Initializing beads database...")
        if shutil.which("bd") is not None:
            result = _run(["bd", "init"])
            if result.returncode != 0:
                print("  WARNING: bd init failed. You may need to initialize manually.")
            else:
                print("  Beads database initialized.")
        else:
            print("  WARNING: bd CLI not found — skipping beads initialization.")
            print("  Install bd and re-run init to initialize.")
    print()


def step_github_remote(*, skip_github: bool) -> tuple[str, str]:
    """Step 4: Detect/create GitHub remote. Returns (owner, repo)."""
    _print_step(4, "GitHub remote")

    if skip_github:
        print("  Skipped (--skip-github).")
        print()
        return "", ""

    # First, detect non-interactively
    result = gh_remote.detect_or_create(check_only=True)

    if result["status"] == "found":
        remote = result["remote"]
        owner, repo = remote["owner"], remote["repo"]
        print(f"  GitHub remote: {owner}/{repo}")
        print()
        return owner, repo

    if result["status"] == "skipped":
        # No remote found — run interactively to allow creation
        result = gh_remote.detect_or_create(check_only=False)
        if result["status"] in ("found", "created") and result["remote"]:
            remote = result["remote"]
            owner, repo = remote["owner"], remote["repo"]
            print(f"  GitHub remote: {owner}/{repo}")
            print()
            return owner, repo
        print("  GitHub remote: not configured (local-only mode)")
        print()
        return "", ""

    print(f"  GitHub remote: {result['status']}")
    print()
    return "", ""


def step_github_project(owner: str, repo: str, *, skip_github: bool) -> str:
    """Step 5: Detect/setup GitHub Project. Returns project number as string."""
    _print_step(5, "GitHub Project")

    if skip_github or not owner or not repo:
        if skip_github:
            print("  Skipped (--skip-github).")
        else:
            print("  Skipped (no GitHub remote configured).")
        print()
        return ""

    # First, check non-interactively
    result = gh_project_setup.detect_or_setup(owner, repo, check_only=True)

    if result["status"] == "found" and result["project"]:
        project = result["project"]
        print(f"  Found GitHub Project: {project['title']} (#{project['number']})")
        print()
        return str(project["number"])

    if result["status"] == "skipped":
        # No projects found — offer to create one interactively
        print("  No GitHub Projects found.")
        try:
            answer = input("  Create a new project with default columns? [Y/n]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            answer = "n"

        if not answer or answer.lower().startswith("y"):
            project = gh_project_setup.create_project(owner, repo)
            if project:
                print(f"  Created GitHub Project #{project['number']}")
                print()
                return str(project["number"])
            print("  WARNING: Failed to create project.")
        else:
            print("  Skipped project creation.")

    else:
        print(f"  GitHub Project: {result['status']}")

    print()
    return ""


def step_labels(owner: str, repo: str, *, skip_github: bool) -> None:
    """Step 6: Bootstrap GitHub labels."""
    _print_step(6, "GitHub labels")

    if skip_github or not owner or not repo:
        if skip_github:
            print("  Skipped (--skip-github).")
        else:
            print("  Skipped (no GitHub remote configured).")
        print()
        return

    # Check if labels have already been bootstrapped
    labels_done = config.get("labels", "bootstrap", REPO_ROOT)
    if labels_done == "true":
        print("  Labels already bootstrapped — skipping.")
        print()
        return

    print("  Bootstrapping GitHub labels...")
    gh_labels.setup_labels(dry_run=False)
    print()


def step_save_config(owner: str, repo: str, project_number: str, *, skip_github: bool) -> None:
    """Step 7: Save configuration to .purser.yml."""
    _print_step(7, "Configuration")

    cfg = config.load_config(REPO_ROOT)

    if owner:
        cfg["github"]["owner"] = owner
    if repo:
        cfg["github"]["repo"] = repo
    if project_number:
        cfg["github"]["project_number"] = project_number
    if owner and repo and not skip_github:
        cfg["labels"]["bootstrap"] = "true"

    config.save_config(cfg, REPO_ROOT)
    print("  Configuration saved to .purser.yml")
    print()


def step_summary() -> None:
    """Step 8: Print summary and next steps."""
    print()
    print("=========================================")
    print("  Setup Summary")
    print("=========================================")
    print()

    # Beads
    beads_dir = REPO_ROOT / ".beads"
    if beads_dir.is_dir():
        print("  Beads database: initialized")
    else:
        print("  Beads database: not initialized")

    # Config
    config_file = config.config_path(REPO_ROOT)
    if config_file.exists():
        print(f"  Config file: {config_file}")
        owner = config.get("github", "owner", REPO_ROOT)
        repo = config.get("github", "repo", REPO_ROOT)
        project_number = config.get("github", "project_number", REPO_ROOT)
        if owner and repo:
            print(f"  GitHub repo: {owner}/{repo}")
        else:
            print("  GitHub repo: not configured")
        if project_number:
            print(f"  GitHub Project: #{project_number}")
        else:
            print("  GitHub Project: not configured")
    else:
        print("  Config file: not created")

    print()
    print("Next steps:")
    print("  1. Write specs in specs/ describing what to build")
    print("  2. Run './loop.sh plan' to generate the task graph")
    print("  3. Run './loop.sh' to start building")
    print()


# ─── Main ────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    check_only = "--check" in argv
    skip_github = "--skip-github" in argv

    if "-h" in argv or "--help" in argv:
        print("Usage: init.py [--check] [--skip-github]")
        print()
        print("Options:")
        print("  --check         Check prerequisites only, no prompts")
        print("  --skip-github   Skip GitHub remote, projects, and label setup")
        print("  -h, --help      Show this help message")
        return

    _print_header()

    # Step 1
    step_prerequisites(check_only=check_only)

    # Step 2
    step_venv()

    # Step 3
    step_beads_db()

    # Step 4
    owner, repo = step_github_remote(skip_github=skip_github)

    # Step 5
    project_number = step_github_project(owner, repo, skip_github=skip_github)

    # Step 6
    step_labels(owner, repo, skip_github=skip_github)

    # Step 7
    step_save_config(owner, repo, project_number, skip_github=skip_github)

    # Step 8
    step_summary()


if __name__ == "__main__":
    main()
