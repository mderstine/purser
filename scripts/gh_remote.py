"""GitHub remote detection and creation flow for Purser.

Detects GitHub remotes from git config, validates access via gh CLI,
and optionally creates a new repository. Respects the github.auto_create
config setting (prompt|skip|auto).

Uses only Python stdlib.

Usage:
    python3 scripts/gh_remote.py              # interactive detection/creation
    python3 scripts/gh_remote.py --json       # output result as JSON
    python3 scripts/gh_remote.py --check      # check only, no prompts
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Allow importing sibling modules
sys.path.insert(0, str(Path(__file__).parent))
import config


def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a command and return the CompletedProcess."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            cmd, returncode=127, stdout="", stderr="command not found"
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, returncode=124, stdout="", stderr="timeout")


def _has_gh() -> bool:
    """Check if gh CLI is available."""
    return shutil.which("gh") is not None


def _parse_github_url(url: str) -> tuple[str, str] | None:
    """Extract owner/repo from a GitHub remote URL.

    Handles:
        git@github.com:owner/repo.git
        https://github.com/owner/repo.git
        https://github.com/owner/repo
        ssh://git@github.com/owner/repo.git
    """
    url = url.strip().rstrip("/").removesuffix(".git")

    # SSH: git@github.com:owner/repo
    match = re.match(r"git@github\.com:([^/]+)/([^/]+)$", url)
    if match:
        return match.group(1), match.group(2)

    # HTTPS or SSH URL: *github.com/owner/repo
    match = re.match(r"(?:https?|ssh)://(?:[^@]+@)?github\.com/([^/]+)/([^/]+)$", url)
    if match:
        return match.group(1), match.group(2)

    return None


def detect_github_remotes() -> list[dict[str, str]]:
    """Detect all GitHub remotes from git config.

    Tries two approaches for each remote:
    1. Parse the raw URL from ``git remote -v``
    2. Resolve via ``git remote get-url <name>`` (handles ``url.<base>.insteadOf``)

    Returns a list of dicts with keys: name, url, owner, repo.
    """
    result = _run(["git", "remote", "-v"])
    if result.returncode != 0:
        return []

    remotes: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and "(fetch)" in line:
            remotes[parts[0]] = parts[1]

    github_remotes = []
    for name, url in remotes.items():
        parsed = _parse_github_url(url)

        # Fallback: resolve effective URL (handles insteadOf rewrites).
        if not parsed:
            resolved = _run(["git", "remote", "get-url", name])
            if resolved.returncode == 0:
                effective_url = resolved.stdout.strip()
                parsed = _parse_github_url(effective_url)
                if parsed:
                    url = effective_url

        if parsed:
            github_remotes.append(
                {
                    "name": name,
                    "url": url,
                    "owner": parsed[0],
                    "repo": parsed[1],
                }
            )

    return github_remotes


def _detect_via_gh_cli() -> dict[str, str] | None:
    """Last-resort detection: ask ``gh`` to identify the repo from the working directory.

    ``gh repo view --json`` auto-detects the GitHub repo even when the remote
    URL doesn't look like a standard GitHub URL (e.g. custom SSH aliases).

    Returns a remote dict or None.
    """
    if not _has_gh():
        return None
    result = _run(["gh", "repo", "view", "--json", "owner,name,url"])
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
        owner = (
            data["owner"]["login"]
            if isinstance(data.get("owner"), dict)
            else str(data.get("owner", ""))
        )
        repo_name = data.get("name", "")
        if not owner or not repo_name:
            return None
        return {
            "name": "origin",
            "url": data.get("url", ""),
            "owner": owner,
            "repo": repo_name,
        }
    except (json.JSONDecodeError, KeyError):
        return None


def select_remote(
    remotes: list[dict[str, str]], preferred: str = "origin"
) -> dict[str, str] | None:
    """Select the best remote, preferring the configured/origin remote."""
    if not remotes:
        return None
    for r in remotes:
        if r["name"] == preferred:
            return r
    return remotes[0]


def validate_remote(owner: str, repo: str) -> bool:
    """Validate that the remote is accessible via gh CLI."""
    if not _has_gh():
        return False
    result = _run(["gh", "repo", "view", f"{owner}/{repo}", "--json", "name"])
    return result.returncode == 0


def _prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt user for yes/no answer."""
    suffix = " [Y/n]: " if default else " [y/N]: "
    try:
        answer = input(question + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def _prompt_repo_name() -> tuple[str, str] | None:
    """Prompt user for repository details for creation."""
    try:
        # Get current directory name as default
        default_name = Path.cwd().name
        name = input(f"  Repository name [{default_name}]: ").strip()
        if not name:
            name = default_name

        visibility = input("  Visibility (public/private) [private]: ").strip().lower()
        if not visibility:
            visibility = "private"
        if visibility not in ("public", "private"):
            print(f"  Invalid visibility: {visibility}", file=sys.stderr)
            return None

        return name, visibility
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def create_repo(name: str, visibility: str = "private") -> dict[str, str] | None:
    """Create a new GitHub repository via gh CLI.

    Returns dict with name, url, owner, repo on success, None on failure.
    """
    if not _has_gh():
        print("  gh CLI not available — cannot create repository.", file=sys.stderr)
        return None

    flag = f"--{visibility}"
    result = _run(
        [
            "gh",
            "repo",
            "create",
            name,
            flag,
            "--source=.",
            "--remote=origin",
            "--json",
            "owner,name,url",
        ],
        timeout=60,
    )
    if result.returncode != 0:
        print(f"  Failed to create repository: {result.stderr.strip()}", file=sys.stderr)
        return None

    try:
        data = json.loads(result.stdout)
        return {
            "name": "origin",
            "url": data.get("url", ""),
            "owner": data["owner"]["login"]
            if isinstance(data.get("owner"), dict)
            else str(data.get("owner", "")),
            "repo": data.get("name", name),
        }
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  Failed to parse gh output: {e}", file=sys.stderr)
        return None


def detect_or_create(repo_root: Path | None = None, check_only: bool = False) -> dict:
    """Main flow: detect GitHub remote, optionally create one.

    Returns:
        {
            "status": "found" | "created" | "skipped" | "declined" | "error",
            "remote": {"name": ..., "url": ..., "owner": ..., "repo": ...} | null,
            "validated": true/false,
            "message": "human-readable summary"
        }
    """
    cfg = config.load_config(repo_root)
    preferred_remote = cfg["github"].get("remote", "origin")
    auto_create = cfg["github"].get("auto_create", "prompt")

    # Step 1: Detect existing GitHub remotes
    remotes = detect_github_remotes()

    # Step 1b: Fallback — ask gh CLI to identify the repo from the working directory.
    if not remotes:
        gh_detected = _detect_via_gh_cli()
        if gh_detected:
            remotes = [gh_detected]

    if remotes:
        remote = select_remote(remotes, preferred_remote)
        validated = validate_remote(remote["owner"], remote["repo"])
        return {
            "status": "found",
            "remote": remote,
            "validated": validated,
            "message": f"Found GitHub remote '{remote['name']}': {remote['owner']}/{remote['repo']}"
            + (
                " (validated)"
                if validated
                else " (not validated — gh CLI unavailable or no access)"
            ),
        }

    # Step 2: No GitHub remote found
    if check_only or auto_create == "skip":
        return {
            "status": "skipped",
            "remote": None,
            "validated": False,
            "message": "No GitHub remote found. GitHub integration skipped.",
        }

    if not _has_gh():
        return {
            "status": "skipped",
            "remote": None,
            "validated": False,
            "message": (
                "No GitHub remote found and gh CLI is not installed. GitHub integration skipped."
            ),
        }

    # Step 3: Prompt or auto-create
    if auto_create == "auto":
        should_create = True
    else:
        # auto_create == "prompt"
        print()
        print("No GitHub remote detected.")
        should_create = _prompt_yes_no("  Create a new GitHub repository?")

    if not should_create:
        return {
            "status": "declined",
            "remote": None,
            "validated": False,
            "message": "User declined repository creation. Local-only mode.",
        }

    # Step 4: Get repo details and create
    if auto_create == "auto":
        name = Path.cwd().name
        visibility = "private"
    else:
        details = _prompt_repo_name()
        if not details:
            return {
                "status": "declined",
                "remote": None,
                "validated": False,
                "message": "Repository creation cancelled.",
            }
        name, visibility = details

    remote = create_repo(name, visibility)
    if not remote:
        return {
            "status": "error",
            "remote": None,
            "validated": False,
            "message": "Failed to create GitHub repository.",
        }

    validated = validate_remote(remote["owner"], remote["repo"])
    return {
        "status": "created",
        "remote": remote,
        "validated": validated,
        "message": f"Created {visibility} repository: {remote['owner']}/{remote['repo']}",
    }


def main():
    """CLI entry point."""
    use_json = "--json" in sys.argv
    check_only = "--check" in sys.argv

    result = detect_or_create(check_only=check_only)

    if use_json:
        print(json.dumps(result, indent=2))
    else:
        print(result["message"])
        if result["remote"]:
            r = result["remote"]
            print(f"  Remote: {r['name']} -> {r['owner']}/{r['repo']}")
            print(f"  Validated: {result['validated']}")

    sys.exit(0 if result["status"] in ("found", "created", "skipped") else 1)


if __name__ == "__main__":
    main()
