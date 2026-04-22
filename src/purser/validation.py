from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .gates import GateResult


@dataclass(slots=True)
class ValidationRecord:
    bead_id: str
    title: str
    spec_reference: str
    summary: str
    verification_items: list[str]
    notes: list[str]
    executor_attempts: int = 1
    commits: list[str] | None = None


def append_validation_log(path: Path, record: ValidationRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = (
        datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    commits = ", ".join(record.commits or []) or "n/a"
    verification = (
        "\n".join(f"- {item}" for item in record.verification_items) or "- n/a"
    )
    notes = "\n".join(f"- {item}" for item in record.notes) or "- none"
    block = (
        f"## {record.bead_id} — {record.title}\n\n"
        f"**Validated:** {timestamp}\n"
        f"**Status:** closed\n"
        f"**Spec reference:** {record.spec_reference}\n"
        f"**Commits:** {commits}\n"
        f"**Executor attempts:** {record.executor_attempts}\n\n"
        f"### Summary\n{record.summary}\n\n"
        f"### Verification\n{verification}\n\n"
        f"### Notes\n{notes}\n\n"
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(block)


def verification_items_from_gates(results: list[GateResult]) -> list[str]:
    return [
        f"{result.name}: {'clean' if result.passed else 'failed'}" for result in results
    ]
