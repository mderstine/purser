from __future__ import annotations

from pathlib import Path
import subprocess

from .config import DEFAULT_CONFIG_PATH


def resolve_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    git_root = _git_repo_root(current)
    if git_root is not None:
        return git_root
    for candidate in [current, *current.parents]:
        if (candidate / DEFAULT_CONFIG_PATH).exists():
            return candidate
        if (candidate / ".beads").exists():
            return candidate
        if (candidate / ".git").exists():
            return candidate
    return current


def _git_repo_root(start: Path) -> Path | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    output = completed.stdout.strip()
    return Path(output).resolve() if output else None
