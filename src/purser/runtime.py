from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import shutil
import subprocess


@dataclass(slots=True)
class BinaryStatus:
    name: str
    path: str | None
    version: str | None
    ok: bool
    note: str | None = None


@dataclass(slots=True)
class BeadsContext:
    beads_dir: Path
    repo_root: Path
    backend: str
    dolt_mode: str | None
    database: str | None
    role: str | None


_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)")


def find_binary(name: str) -> str | None:
    return shutil.which(name)


def detect_version(name: str, command: list[str]) -> str | None:
    try:
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
    except OSError:
        return None
    text = "\n".join(
        part for part in [completed.stdout.strip(), completed.stderr.strip()] if part
    )
    match = _VERSION_RE.search(text)
    return match.group(1) if match else (text.splitlines()[0] if text else None)


def binary_status(name: str) -> BinaryStatus:
    path = find_binary(name)
    if path is None:
        return BinaryStatus(
            name=name, path=None, version=None, ok=False, note="missing from PATH"
        )
    if name == "bd":
        version = detect_version(name, [name, "version"])
    elif name == "dolt":
        version = detect_version(name, [name, "version"])
    else:
        version = detect_version(name, [name, "--version"])
    return BinaryStatus(name=name, path=path, version=version, ok=True)


def collect_binary_statuses() -> list[BinaryStatus]:
    return [binary_status(name) for name in ["bd", "dolt", "pi"]]


def format_binary_status(status: BinaryStatus) -> str:
    state = "ok" if status.ok else "missing"
    details = []
    if status.path:
        details.append(status.path)
    if status.version:
        details.append(f"version={status.version}")
    if status.note:
        details.append(status.note)
    return f"{status.name}: {state}" + (f" ({', '.join(details)})" if details else "")


def get_bd_context(root: Path) -> BeadsContext:
    try:
        completed = subprocess.run(
            ["bd", "context", "--json"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(f"unable to run 'bd context --json': {exc}") from exc
    output = completed.stdout.strip() or completed.stderr.strip()
    if completed.returncode != 0:
        raise RuntimeError(output or "bd context failed")
    try:
        raw = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("bd context returned invalid JSON") from exc
    repo_root = Path(raw["repo_root"]).resolve()
    beads_dir = Path(raw["beads_dir"]).resolve()
    return BeadsContext(
        beads_dir=beads_dir,
        repo_root=repo_root,
        backend=str(raw.get("backend", "")),
        dolt_mode=raw.get("dolt_mode"),
        database=raw.get("database"),
        role=raw.get("role"),
    )


def ensure_local_beads_context(root: Path) -> BeadsContext:
    context = get_bd_context(root)
    expected_root = root.resolve()
    if context.repo_root != expected_root:
        raise RuntimeError(
            f"bd context repo root mismatch: expected {expected_root}, got {context.repo_root}"
        )
    if context.backend != "dolt":
        raise RuntimeError(f"unsupported Beads backend for purser: {context.backend}")
    if context.dolt_mode != "embedded":
        raise RuntimeError(
            "purser requires a repo-local embedded Beads/Dolt database; "
            f"found dolt_mode={context.dolt_mode or 'unknown'}"
        )
    if context.beads_dir.parent != expected_root or context.beads_dir.name != ".beads":
        raise RuntimeError(
            f"purser requires repo-local .beads storage; found {context.beads_dir}"
        )
    return context


def format_beads_context_status(context: BeadsContext) -> str:
    return (
        "beads_storage: ok "
        f"(repo_root={context.repo_root}, beads_dir={context.beads_dir}, "
        f"backend={context.backend}, dolt_mode={context.dolt_mode}, database={context.database})"
    )


def prompt_health(root: Path, config) -> list[str]:
    messages: list[str] = []
    for role in ["planner", "executor", "reviewer"]:
        path = config.prompt_path(role)
        if path is None:
            messages.append(f"{role}_prompt: not configured")
        elif not path.exists():
            messages.append(f"{role}_prompt: missing file {path}")
        else:
            messages.append(f"{role}_prompt: ok ({path})")
    return messages
