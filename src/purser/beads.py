from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import subprocess


@dataclass(slots=True)
class Bead:
    id: str
    title: str
    status: str
    raw: dict

    @property
    def normalized_status(self) -> str:
        return normalize_status(self.status)

    @property
    def metadata(self) -> dict:
        metadata = self.raw.get("metadata")
        return metadata if isinstance(metadata, dict) else {}


class BeadsError(RuntimeError):
    pass


class BeadsClient:
    def __init__(self, root: Path, auto_commit: str = "on") -> None:
        self.root = root
        self.auto_commit = auto_commit

    def _run(self, *args: str, check: bool = True) -> dict | list | str:
        command = ["bd", "--json", "--dolt-auto-commit", self.auto_commit, *args]
        completed = subprocess.run(
            command,
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
        )
        if check and completed.returncode != 0:
            raise BeadsError(completed.stderr.strip() or completed.stdout.strip() or f"bd failed: {' '.join(command)}")
        stdout = completed.stdout.strip()
        if not stdout:
            return ""
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return stdout

    def ready(self, limit: int = 10) -> list[Bead]:
        raw = self._run("ready", "--limit", str(limit))
        return [self._coerce_bead(item) for item in _items_from_json(raw)]

    def list_by_statuses(self, statuses: list[str]) -> list[Bead]:
        normalized = sorted({normalize_status(status) for status in statuses})
        raw = self._run("list", "--status", ",".join(normalized))
        return [self._coerce_bead(item) for item in _items_from_json(raw)]

    def show(self, bead_id: str) -> Bead:
        raw = self._run("show", bead_id)
        if isinstance(raw, list):
            if not raw:
                raise BeadsError(f"Bead not found: {bead_id}")
            return self._coerce_bead(raw[0])
        if isinstance(raw, dict):
            item = raw.get("issue") or raw
            return self._coerce_bead(item)
        raise BeadsError(f"Unexpected bd show output for {bead_id}")

    def claim(self, bead_id: str) -> Bead:
        self._run("update", bead_id, "--claim")
        return self.show(bead_id)

    def update_status(self, bead_id: str, status: str, notes: str | None = None) -> Bead:
        args = ["update", bead_id, "--status", normalize_status(status)]
        if notes:
            args += ["--append-notes", notes]
        self._run(*args)
        return self.show(bead_id)

    def close(self, bead_id: str, reason: str | None = None) -> Bead:
        args = ["close", bead_id]
        if reason:
            args += ["--reason", reason]
        self._run(*args)
        return self.show(bead_id)

    def reopen(self, bead_id: str, reason: str | None = None) -> Bead:
        args = ["reopen", bead_id]
        if reason:
            args += ["--reason", reason]
        self._run(*args)
        return self.show(bead_id)

    def note(self, bead_id: str, text: str) -> None:
        self._run("note", bead_id, text)

    def comment(self, bead_id: str, text: str) -> None:
        self._run("comments", "add", bead_id, text)

    def create(self, title: str, *, description: str | None = None, acceptance: str | None = None, spec_id: str | None = None, deps: list[str] | None = None) -> Bead:
        args = ["create", title]
        if description:
            args += ["--description", description]
        if acceptance:
            args += ["--acceptance", acceptance]
        if spec_id:
            args += ["--spec-id", spec_id]
        if deps:
            args += ["--deps", ",".join(deps)]
        raw = self._run(*args)
        if isinstance(raw, dict):
            item = raw.get("issue") or raw
            return self._coerce_bead(item)
        raise BeadsError("Unexpected bd create output")

    def add_block_dependency(self, blocker_id: str, blocked_id: str) -> None:
        self._run("dep", blocker_id, "--blocks", blocked_id)

    def set_metadata(self, bead_id: str, key: str, value: str) -> Bead:
        self._run("update", bead_id, "--set-metadata", f"{key}={value}")
        return self.show(bead_id)

    def increment_attempts(self, bead_id: str) -> Bead:
        bead = self.show(bead_id)
        current = int(bead.metadata.get("purser_executor_attempts", 0))
        return self.set_metadata(bead_id, "purser_executor_attempts", str(current + 1))

    @staticmethod
    def _coerce_bead(item: dict) -> Bead:
        bead_id = item.get("id") or item.get("issue_id") or item.get("key")
        title = item.get("title") or item.get("name") or bead_id
        status = normalize_status(item.get("status") or item.get("state") or "unknown")
        return Bead(id=bead_id, title=title, status=status, raw=item)


def normalize_status(status: str) -> str:
    value = status.strip().lower().replace("_", "-")
    aliases = {
        "in-progress": "in_progress",
        "inreview": "in_review",
        "in-review": "in_review",
        "in-reviewing": "in_review",
    }
    return aliases.get(value, value)


def _items_from_json(raw: dict | list | str) -> list[dict]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        for key in ["issues", "items", "data", "results"]:
            value = raw.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if any(key in raw for key in ["id", "issue_id", "key"]):
            return [raw]
        issue = raw.get("issue")
        if isinstance(issue, dict):
            return [issue]
    return []
