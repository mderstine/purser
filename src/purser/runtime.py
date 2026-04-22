from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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


_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)")


def find_binary(name: str) -> str | None:
    return shutil.which(name)


def detect_version(name: str, command: list[str]) -> str | None:
    try:
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
    except OSError:
        return None
    text = "\n".join(part for part in [completed.stdout.strip(), completed.stderr.strip()] if part)
    match = _VERSION_RE.search(text)
    return match.group(1) if match else (text.splitlines()[0] if text else None)


def binary_status(name: str) -> BinaryStatus:
    path = find_binary(name)
    if path is None:
        return BinaryStatus(name=name, path=None, version=None, ok=False, note="missing from PATH")
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
