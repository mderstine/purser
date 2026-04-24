from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import re

from .gates import GateResult
from .roles import RoleResult

_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


class RunArtifacts:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.runs_dir = root / ".purser" / "runs"

    def write_role_artifact(
        self,
        *,
        kind: str,
        bead_id: str | None = None,
        spec_path: Path | None = None,
        role_result: RoleResult,
        structured_outcome: object | None = None,
        gate_results: list[GateResult] | None = None,
        gate_failure: GateResult | None = None,
        state: dict | None = None,
        errors: list[str] | None = None,
        extra: dict | None = None,
    ) -> Path:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        subject = bead_id or (spec_path.name if spec_path else kind)
        path = self.runs_dir / self._filename(kind, subject)
        payload = {
            "schema_version": 1,
            "timestamp_utc": self._timestamp(),
            "kind": kind,
            "bead_id": bead_id,
            "spec_path": str(spec_path) if spec_path else None,
            "role_result": self._serialize_role_result(role_result),
            "structured_outcome": self._serialize(structured_outcome),
            "gate_results": [
                self._serialize_gate_result(item) for item in (gate_results or [])
            ],
            "gate_failure": self._serialize_gate_result(gate_failure)
            if gate_failure
            else None,
            "state": state or {},
            "errors": errors or [],
            "extra": extra or {},
        }
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return path

    def _filename(self, kind: str, subject: str) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        return f"{stamp}-{self._safe(kind)}-{self._safe(subject)}.json"

    def _safe(self, value: str) -> str:
        cleaned = _SAFE_SEGMENT_RE.sub("-", value.strip())
        cleaned = cleaned.strip("-._")
        return cleaned or "artifact"

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _serialize_role_result(self, result: RoleResult) -> dict:
        return {
            "role": result.role,
            "model": result.model,
            "prompt_path": str(result.prompt_path),
            "command": result.command,
            "exit_code": result.exit_code,
            "transcript": result.transcript,
            "final_text": result.final_text,
            "stderr": result.stderr,
            "stdout": result.stdout,
            "provider_error": result.provider_error,
        }

    def _serialize_gate_result(self, result: GateResult) -> dict:
        return {
            "name": result.name,
            "command": result.command,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "passed": result.passed,
        }

    def _serialize(self, value: object) -> object:
        if value is None:
            return None
        if is_dataclass(value) and not isinstance(value, type):
            return asdict(value)
        return value
