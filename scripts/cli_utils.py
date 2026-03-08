"""Cross-platform CLI utilities for Purser scripts.

Replaces common bash patterns (command -v, gh auth status, PYTHONPATH setup)
with cross-platform Python equivalents. Used by all converted shell wrappers.

Uses only Python stdlib.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def require_commands(commands: list[str]) -> None:
    """Verify that all required CLI commands are available on PATH.

    Exits with code 1 and a descriptive message if any command is missing.
    """
    missing = [cmd for cmd in commands if shutil.which(cmd) is None]
    if missing:
        for cmd in missing:
            print(f"Error: {cmd} not found on PATH", file=sys.stderr)
        sys.exit(1)


def require_gh_auth() -> None:
    """Verify that the GitHub CLI is authenticated.

    Exits with code 1 if `gh auth status` fails.
    """
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            print("Error: gh CLI not authenticated. Run: gh auth login", file=sys.stderr)
            sys.exit(1)
    except FileNotFoundError:
        print("Error: gh not found on PATH", file=sys.stderr)
        sys.exit(1)


def run_python_script(script_path: str | Path, args: list[str] | None = None) -> None:
    """Run a Python script with PYTHONPATH set to include the scripts directory.

    Uses os.pathsep for cross-platform path separation (`:` on Unix, `;` on Windows).
    Replaces the current process on Unix (exec), falls back to subprocess on Windows.

    Args:
        script_path: Path to the Python script to run.
        args: Additional arguments to pass to the script.
    """
    script = Path(script_path).resolve()
    scripts_dir = str(script.parent)

    # Build PYTHONPATH with the scripts directory prepended
    existing = os.environ.get("PYTHONPATH", "")
    if existing:
        os.environ["PYTHONPATH"] = scripts_dir + os.pathsep + existing
    else:
        os.environ["PYTHONPATH"] = scripts_dir

    cmd = [sys.executable, str(script)]
    if args:
        cmd.extend(args)

    if sys.platform == "win32":
        # Windows: no os.execvp, use subprocess
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    else:
        # Unix: replace this process entirely (like bash exec)
        os.execvp(cmd[0], cmd)
