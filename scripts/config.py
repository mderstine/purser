"""Purser project configuration loader.

Reads .purser.yml from the repo root and provides typed access to
configuration values. Environment variables (PURSER_*) override
file values.

Uses only Python stdlib — no PyYAML dependency. The YAML subset we
support is deliberately minimal: two levels of nesting with scalar values.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

# Environment variable prefix
_ENV_PREFIX = "PURSER_"

# Default configuration values
DEFAULTS = {
    "github": {
        "host": "github.com",
        "remote": "origin",
        "owner": "",
        "repo": "",
        "auto_create": "prompt",
        "project_number": "",
    },
    "labels": {
        "bootstrap": "false",
    },
}

# Maps config keys to environment variable names
_ENV_MAP = {
    ("github", "host"): "PURSER_GITHUB_HOST",
    ("github", "remote"): "PURSER_GITHUB_REMOTE",
    ("github", "owner"): "PURSER_GITHUB_OWNER",
    ("github", "repo"): "PURSER_GITHUB_REPO",
    ("github", "auto_create"): "PURSER_GITHUB_AUTO_CREATE",
    ("github", "project_number"): "PURSER_GITHUB_PROJECT_NUMBER",
    ("labels", "bootstrap"): "PURSER_LABELS_BOOTSTRAP",
}


def _find_repo_root() -> Path:
    """Find the git repository root."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except FileNotFoundError:
        pass
    return Path.cwd()


def _parse_yaml(text: str) -> dict[str, dict[str, str]]:
    """Parse a minimal YAML subset: two-level nested scalar key-value pairs.

    Supports:
        section:
          key: value
          key: "quoted value"
          key: 'quoted value'
          key: true/false
          key: 42

    Does NOT support: lists, multi-line values, anchors, tags, etc.
    """
    result: dict[str, dict[str, str]] = {}
    current_section = None

    for line in text.splitlines():
        # Skip comments and blank lines
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Top-level section (no leading whitespace, ends with colon)
        if not line[0].isspace() and stripped.endswith(":"):
            current_section = stripped[:-1].strip()
            result[current_section] = {}
            continue

        # Nested key-value pair (indented)
        if current_section is not None and line[0].isspace():
            match = re.match(r"\s+(\w+)\s*:\s*(.*)", line)
            if match:
                key = match.group(1)
                value = match.group(2).strip()
                # Strip quotes
                if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                # Strip inline comments
                if " #" in value:
                    value = value[: value.index(" #")].strip()
                result[current_section][key] = value

    return result


def _serialize_yaml(config: dict[str, dict[str, str]]) -> str:
    """Serialize a two-level config dict to YAML."""
    lines = []
    for section, values in config.items():
        lines.append(f"{section}:")
        for key, value in values.items():
            # Quote values that contain special characters
            if value and any(c in value for c in ": #{}[],&*!|>'\"%@`"):
                value = f'"{value}"'
            lines.append(f"  {key}: {value}")
    return "\n".join(lines) + "\n"


def _apply_env_overrides(config: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Override config values with environment variables."""
    for (section, key), env_var in _ENV_MAP.items():
        env_value = os.environ.get(env_var)
        if env_value is not None:
            if section not in config:
                config[section] = {}
            config[section][key] = env_value
    return config


def config_path(repo_root: Path | None = None) -> Path:
    """Return the path to .purser.yml."""
    root = repo_root or _find_repo_root()
    return root / ".purser.yml"


def load_config(repo_root: Path | None = None) -> dict[str, dict[str, str]]:
    """Load configuration from .purser.yml with env var overrides.

    Returns a two-level dict. Missing sections/keys are filled from DEFAULTS.
    Environment variables (PURSER_*) override file and default values.
    Returns defaults if no config file exists.
    """
    import copy

    config = copy.deepcopy(DEFAULTS)

    path = config_path(repo_root)
    if path.exists():
        text = path.read_text(encoding="utf-8")
        file_config = _parse_yaml(text)
        for section, values in file_config.items():
            if section not in config:
                config[section] = {}
            config[section].update(values)

    config = _apply_env_overrides(config)
    return config


def save_config(config: dict[str, dict[str, str]], repo_root: Path | None = None) -> Path:
    """Write configuration to .purser.yml.

    Returns the path written to.
    """
    path = config_path(repo_root)
    path.write_text(_serialize_yaml(config), encoding="utf-8")
    return path


def get(section: str, key: str, repo_root: Path | None = None) -> str:
    """Get a single config value (convenience function)."""
    config = load_config(repo_root)
    return config.get(section, {}).get(key, "")


# --- CLI interface for bash scripts ---


def main():
    """CLI: read config values for use in shell scripts.

    Usage:
        python3 scripts/config.py get github.owner
        python3 scripts/config.py get github.repo
        python3 scripts/config.py dump          # print full config as YAML
    """
    if len(sys.argv) < 2:
        print("Usage: config.py <get SECTION.KEY | dump>", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    if command == "dump":
        config = load_config()
        print(_serialize_yaml(config), end="")
    elif command == "get" and len(sys.argv) >= 3:
        parts = sys.argv[2].split(".", 1)
        if len(parts) != 2:
            print(f"Error: key must be SECTION.KEY, got '{sys.argv[2]}'", file=sys.stderr)
            sys.exit(1)
        value = get(parts[0], parts[1])
        print(value)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
