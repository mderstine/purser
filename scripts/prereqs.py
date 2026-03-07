"""Prerequisite checker for Ralph-Beads framework.

Checks for required tools and reports missing ones with platform-specific
install instructions. Uses only Python stdlib.

Usage:
    python3 scripts/prereqs.py              # check all prerequisites
    python3 scripts/prereqs.py --json       # output as JSON
    python3 scripts/prereqs.py --quiet      # exit code only (0=ok, 1=missing)
"""

import json
import platform
import shutil
import subprocess
import sys


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
    ("gh", "--version", "GitHub CLI"),
    ("bd", "--version", "Beads issue tracker CLI"),
]

# Install instructions per platform
INSTALL_INSTRUCTIONS: dict[str, dict[str, str]] = {
    "macos": {
        "git": "brew install git",
        "python3": "brew install python@3.12",
        "gh": "brew install gh",
        "bd": "npm install -g @beads/bd",
    },
    "linux-apt": {
        "git": "sudo apt install git",
        "python3": "sudo apt install python3",
        "gh": "See https://github.com/cli/cli/blob/trunk/docs/install_linux.md",
        "bd": "npm install -g @beads/bd",
    },
    "linux-other": {
        "git": "Install via your package manager",
        "python3": "Install via your package manager",
        "gh": "See https://github.com/cli/cli/blob/trunk/docs/install_linux.md",
        "bd": "npm install -g @beads/bd",
    },
    "windows": {
        "git": "winget install Git.Git  (or scoop install git)",
        "python3": "winget install Python.Python.3.12  (or scoop install python)",
        "gh": "winget install GitHub.cli  (or scoop install gh)",
        "bd": "npm install -g @beads/bd",
    },
}


def _get_version(command: str, version_flag: str) -> str | None:
    """Try to get a tool's version string. Returns None if not found."""
    try:
        result = subprocess.run(
            [command, version_flag],
            capture_output=True, text=True, timeout=10,
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
        version = _get_version(command, version_flag)
        found = version is not None
        if not found:
            all_ok = False

        install_map = INSTALL_INSTRUCTIONS.get(plat, INSTALL_INSTRUCTIONS["linux-other"])
        tools.append({
            "name": command,
            "description": description,
            "found": found,
            "version": version,
            "install": install_map.get(command, ""),
        })

    return {
        "platform": plat,
        "all_ok": all_ok,
        "tools": tools,
    }


def print_report(result: dict) -> None:
    """Print a human-readable prerequisite report."""
    print(f"Platform: {result['platform']}")
    print()

    for tool in result["tools"]:
        if tool["found"]:
            print(f"  [ok]      {tool['name']}: {tool['version']}")
        else:
            print(f"  [MISSING] {tool['name']}: {tool['description']}")
            print(f"            Install: {tool['install']}")

    print()
    if result["all_ok"]:
        print("All prerequisites satisfied.")
    else:
        missing = [t["name"] for t in result["tools"] if not t["found"]]
        print(f"Missing {len(missing)} prerequisite(s): {', '.join(missing)}")


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
