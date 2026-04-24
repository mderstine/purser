from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import tomllib


@dataclass(frozen=True, slots=True)
class InitProfile:
    language: str
    lint: str
    types: str
    tests: str


def detect_init_profile(root: Path) -> InitProfile:
    if (root / "pyproject.toml").exists():
        return _python_profile(root)
    if (root / "package.json").exists():
        return _node_profile(root)
    if (root / "Cargo.toml").exists():
        return InitProfile(
            language="rust",
            lint="cargo fmt --check && cargo clippy --all-targets --all-features -- -D warnings",
            types="cargo check",
            tests="cargo test",
        )
    if (root / "go.mod").exists():
        return InitProfile(
            language="go",
            lint="go test ./...",
            types="go test ./...",
            tests="go test ./...",
        )
    return InitProfile(
        language="unknown",
        lint="",
        types="",
        tests="",
    )


def _python_profile(root: Path) -> InitProfile:
    if _is_strong_uv_repo(root):
        type_cmd = "uv run ty check" if _uses_ty(root) else "uv run pyright"
        return InitProfile(
            language="python",
            lint="uv run ruff check . && uv run ruff format --check .",
            types=type_cmd,
            tests="uv run pytest -x --tb=short",
        )
    return InitProfile(
        language="python",
        lint="ruff check . && ruff format --check .",
        types="python3 -m pyright",
        tests="python3 -m pytest -x --tb=short",
    )


def _node_profile(root: Path) -> InitProfile:
    package_json = root / "package.json"
    try:
        raw = json.loads(package_json.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    scripts = raw.get("scripts") if isinstance(raw, dict) else {}
    if not isinstance(scripts, dict):
        scripts = {}
    lint = "npm run lint" if "lint" in scripts else ""
    types = "npm run typecheck" if "typecheck" in scripts else ""
    tests = "npm test" if "test" in scripts else ""
    return InitProfile(language="node", lint=lint, types=types, tests=tests)


def _is_strong_uv_repo(root: Path) -> bool:
    if (root / "uv.lock").exists():
        return True
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return False
    try:
        raw = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:
        return False
    project = raw.get("project")
    if isinstance(project, dict):
        scripts = project.get("scripts")
        if isinstance(scripts, dict) and scripts:
            return True
    dependency_groups = raw.get("dependency-groups")
    if isinstance(dependency_groups, dict):
        return True
    tool = raw.get("tool")
    if isinstance(tool, dict) and "uv" in tool:
        return True
    return False


def _uses_ty(root: Path) -> bool:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return False
    text = pyproject.read_text(encoding="utf-8")
    return "ty" in text
