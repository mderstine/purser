"""Shared utilities for purser GitHub integration scripts.

All functions use only Python stdlib. This module is imported by
gh_sync.py, gh_triage.py, gh_changelog.py, and gh_pr_body.py
via sys.path.insert in each script.
"""

import json
import re
import subprocess
import sys

try:
    import config as _config
except ImportError:
    _config = None


def run(cmd, capture=True):
    """Run a command (list of args) and return stdout."""
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if result.returncode != 0 and capture:
        print(f"  ERROR: {cmd}", file=sys.stderr)
        print(f"  {result.stderr.strip()}", file=sys.stderr)
    return result.stdout.strip() if capture else ""


def slugify(title, max_length=60):
    """Convert a title to a filename/label-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug[:max_length]


def get_commit_for_issue(beads_id):
    """Find the commit SHA that closed a beads issue."""
    result = run(["git", "log", "--format=%H", f"--grep=Closes: {beads_id}", "-1"])
    return result[:12] if result else None


def get_repo_url():
    """Get the GitHub repo URL for linking.

    Converts git@github.com:user/repo.git or https://github.com/user/repo.git
    to https://github.com/user/repo.
    """
    remote = run(["git", "remote", "get-url", "origin"])
    if not remote:
        return None
    remote = remote.rstrip("/").removesuffix(".git")
    if remote.startswith("git@"):
        remote = remote.replace(":", "/").replace("git@", "https://")
    return remote


def get_repo_owner():
    """Get the GitHub repo owner login.

    Checks .purser.yml (github.owner) and PURSER_GITHUB_OWNER first.
    Falls back to detecting via 'gh repo view' when not configured.
    """
    if _config is not None:
        owner = _config.get("github", "owner")
        if owner:
            return owner
    return run(["gh", "repo", "view", "--json", "owner", "-q", ".owner.login"])


def get_repo_name():
    """Get the GitHub repo name.

    Checks .purser.yml (github.repo) and PURSER_GITHUB_REPO first.
    Falls back to detecting via 'gh repo view' when not configured.
    """
    if _config is not None:
        repo = _config.get("github", "repo")
        if repo:
            return repo
    return run(["gh", "repo", "view", "--json", "name", "-q", ".name"])


def get_project_number():
    """Get the GitHub Projects v2 board number from config.

    Returns the integer project number from .purser.yml (github.project_number)
    or PURSER_GITHUB_PROJECT_NUMBER. Returns None when not configured.
    """
    if _config is None:
        return None
    value = _config.get("github", "project_number")
    if value:
        try:
            return int(value)
        except ValueError:
            pass
    return None


def load_beads_issues(status=None):
    """Load beads issues, optionally filtered by status."""
    cmd = ["bd", "list", "--json"]
    if status:
        cmd.extend(["--status", status])
    result = run(cmd)
    return json.loads(result) if result else []
