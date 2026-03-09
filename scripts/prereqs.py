"""Prerequisite checker for Purser framework.

Checks for required tools and reports missing ones with platform-specific
install instructions. Uses only Python stdlib.

Usage:
    python3 scripts/prereqs.py              # check all prerequisites
    python3 scripts/prereqs.py --json       # output as JSON
    python3 scripts/prereqs.py --quiet      # exit code only (0=ok, 1=missing)
"""

import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cli_utils import setup_logging  # noqa: E402

logger = setup_logging(__name__)


def _detect_platform() -> str:
    """Detect the platform for install instructions.

    Returns one of: 'macos', 'linux-apt', 'linux-other', 'windows'.
    """
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        # Check for apt-based distro
        if shutil.which("apt") or shutil.which("apt-get"):
            return "linux-apt"
        return "linux-other"
    return "linux-other"


# Tool definitions: (command, version_flag, description)
REQUIRED_TOOLS = [
    ("git", "--version", "Git version control"),
    ("python3", "--version", "Python 3.12+ interpreter"),
    ("uv", "--version", "Python package manager"),
    ("gh", "--version", "GitHub CLI"),
    ("bd", "--version", "Beads issue tracker CLI"),
]

# Python binary fallback order per platform.
# On Windows there is no python3; the launcher `py -3` is the idiomatic way.
# In uv-managed environments the binary is often just `python`.
_PYTHON_FALLBACKS: dict[str, list[tuple[str, ...]]] = {
    "windows": [("python", "--version"), ("py", "-3", "--version")],
    "default": [("python3", "--version"), ("python", "--version")],
}

# Minimum required Python version (major, minor).
_PYTHON_MIN_VERSION: tuple[int, int] = (3, 12)

# Install instructions per platform
INSTALL_INSTRUCTIONS: dict[str, dict[str, str]] = {
    "macos": {
        "git": "brew install git",
        "python3": "brew install python@3.12",
        "uv": "brew install uv  (or curl -LsSf https://astral.sh/uv/install.sh | sh)",
        "gh": "brew install gh",
        "bd": "npm install -g @beads/bd",
    },
    "linux-apt": {
        "git": "sudo apt install git",
        "python3": "sudo apt install python3",
        "uv": "curl -LsSf https://astral.sh/uv/install.sh | sh",
        "gh": "See https://github.com/cli/cli/blob/trunk/docs/install_linux.md",
        "bd": "npm install -g @beads/bd",
    },
    "linux-other": {
        "git": "Install via your package manager",
        "python3": "Install via your package manager",
        "uv": "curl -LsSf https://astral.sh/uv/install.sh | sh",
        "gh": "See https://github.com/cli/cli/blob/trunk/docs/install_linux.md",
        "bd": "npm install -g @beads/bd",
    },
    "windows": {
        "git": "winget install Git.Git  (or scoop install git)",
        "python3": "winget install Python.Python.3.12  (or scoop install python)",
        "uv": 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"',
        "gh": "winget install GitHub.cli  (or scoop install gh)",
        "bd": "npm install -g @beads/bd",
    },
}


def _get_version(*cmd: str) -> str | None:
    """Try to get a tool's version string. Returns None if not found.

    Accepts one or more command tokens, e.g. ``_get_version("python3", "--version")``
    or ``_get_version("py", "-3", "--version")``.
    """
    try:
        result = subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # Return first non-empty line of output
            for line in (result.stdout + result.stderr).splitlines():
                line = line.strip()
                if line:
                    return line
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _get_python_version(plat: str) -> str | None:
    """Try platform-specific Python binary fallbacks.

    Returns the version string from the first binary that works, or None.
    """
    key = "windows" if plat == "windows" else "default"
    for cmd_tokens in _PYTHON_FALLBACKS[key]:
        version = _get_version(*cmd_tokens)
        if version is not None:
            return version
    return None


def _parse_python_version(version_str: str) -> tuple[int, int] | None:
    """Extract (major, minor) from a Python version string.

    Handles formats like "Python 3.12.4", "Python 3.12.0a1", etc.
    Returns None if the string cannot be parsed.
    """
    match = re.search(r"(\d+)\.(\d+)", version_str)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None


def _check_python_min_version(version_str: str | None) -> bool:
    """Return True if *version_str* satisfies the minimum Python version."""
    if version_str is None:
        return False
    parsed = _parse_python_version(version_str)
    if parsed is None:
        return False
    return parsed >= _PYTHON_MIN_VERSION


def check_prerequisites() -> dict:
    """Check all prerequisites and return structured results.

    Returns:
        {
            "platform": "macos" | "linux-apt" | ...,
            "all_ok": true/false,
            "tools": [
                {
                    "name": "git",
                    "description": "Git version control",
                    "found": true/false,
                    "version": "git version 2.43.0" | null,
                    "install": "brew install git"
                },
                ...
            ]
        }
    """
    plat = _detect_platform()
    tools = []
    all_ok = True

    for command, version_flag, description in REQUIRED_TOOLS:
        # Python needs special handling: try platform-specific fallbacks
        # and enforce a minimum version.
        if command == "python3":
            version = _get_python_version(plat)
            if version is not None and not _check_python_min_version(version):
                min_maj, min_min = _PYTHON_MIN_VERSION
                version = f"{version} (need {min_maj}.{min_min}+)"
                found = False
            else:
                found = version is not None
        else:
            version = _get_version(command, version_flag)
            found = version is not None
        if not found:
            all_ok = False

        install_map = INSTALL_INSTRUCTIONS.get(plat, INSTALL_INSTRUCTIONS["linux-other"])
        # Always report as "python3" regardless of which binary was found,
        # so downstream consumers (init.py tool_map["python3"]) keep working.
        tools.append(
            {
                "name": command,
                "description": description,
                "found": found,
                "version": version,
                "install": install_map.get(command, ""),
            }
        )

    return {
        "platform": plat,
        "all_ok": all_ok,
        "tools": tools,
    }


def print_report(result: dict) -> None:
    """Print a human-readable prerequisite report."""
    logger.info("Platform: %s", result["platform"])
    logger.info("")

    for tool in result["tools"]:
        if tool["found"]:
            logger.info("  [ok]      %s: %s", tool["name"], tool["version"])
        else:
            logger.warning("  [MISSING] %s: %s", tool["name"], tool["description"])
            logger.warning("            Install: %s", tool["install"])

    logger.info("")
    if result["all_ok"]:
        logger.info("All prerequisites satisfied.")
    else:
        missing = [t["name"] for t in result["tools"] if not t["found"]]
        logger.warning("Missing %d prerequisite(s): %s", len(missing), ", ".join(missing))


def main():
    """CLI entry point."""
    use_json = "--json" in sys.argv
    quiet = "--quiet" in sys.argv

    result = check_prerequisites()

    if quiet:
        sys.exit(0 if result["all_ok"] else 1)
    elif use_json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)

    sys.exit(0 if result["all_ok"] else 1)


if __name__ == "__main__":
    main()
