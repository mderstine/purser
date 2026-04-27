from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, cast


class OutcomeProtocolError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PlannerOutcome:
    status: str
    created_beads: list[str]
    dependencies: list[tuple[str, str]]
    needs_human_input: bool
    summary: str


@dataclass(frozen=True, slots=True)
class GateOutcome:
    command: str
    status: str
    exit_code: int
    summary: str


@dataclass(frozen=True, slots=True)
class ExecutorOutcome:
    status: str
    bead_id: str
    files_touched: list[str]
    new_beads: list[str]
    gates_run: list[GateOutcome]
    ready_for_review: bool
    summary: str
    blocking_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewIssue:
    severity: str
    summary: str
    file: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewerOutcome:
    status: str
    bead_id: str
    issues_found: list[ReviewIssue]
    gates_run: list[GateOutcome]
    summary: str
    legacy_state_transition_performed: bool | None = None

    @property
    def decision(self) -> str:
        """Compatibility alias for older loop code and tests."""
        return "approve" if self.status == "approved" else self.status

    @property
    def state_transition_performed(self) -> bool:
        """Compatibility alias for the legacy reviewer contract."""
        return bool(self.legacy_state_transition_performed)

    @property
    def issues(self) -> list[str]:
        """Compatibility alias for older string-only reviewer issues."""
        return [issue.summary for issue in self.issues_found]


FENCED_JSON_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
EXECUTOR_STATUSES = {"completed", "blocked", "failed"}
REVIEWER_STATUSES = {"approved", "rejected", "blocked", "failed"}
GATE_STATUSES = {"passed", "failed", "skipped"}
ISSUE_SEVERITIES = {"critical", "major", "minor"}

EXECUTOR_OUTCOME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "status",
        "bead_id",
        "files_touched",
        "new_beads",
        "gates_run",
        "ready_for_review",
        "summary",
        "blocking_reason",
    ],
    "properties": {
        "status": {"enum": sorted(EXECUTOR_STATUSES)},
        "bead_id": {"type": "string"},
        "files_touched": {"type": "array", "items": {"type": "string"}},
        "new_beads": {"type": "array", "items": {"type": "string"}},
        "gates_run": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["command", "status", "exit_code", "summary"],
                "properties": {
                    "command": {"type": "string"},
                    "status": {"enum": sorted(GATE_STATUSES)},
                    "exit_code": {"type": "integer"},
                    "summary": {"type": "string"},
                },
            },
        },
        "ready_for_review": {"type": "boolean"},
        "summary": {"type": "string"},
        "blocking_reason": {"type": ["string", "null"]},
    },
}

REVIEWER_OUTCOME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["status", "bead_id", "issues_found", "gates_run", "summary"],
    "properties": {
        "status": {"enum": sorted(REVIEWER_STATUSES)},
        "bead_id": {"type": "string"},
        "issues_found": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["severity", "summary", "file"],
                "properties": {
                    "severity": {"enum": sorted(ISSUE_SEVERITIES)},
                    "summary": {"type": "string"},
                    "file": {"type": ["string", "null"]},
                },
            },
        },
        "gates_run": {
            "type": "array",
            "items": EXECUTOR_OUTCOME_SCHEMA["properties"]["gates_run"]["items"],
        },
        "summary": {"type": "string"},
    },
}


def parse_planner_outcome(value: str | dict[str, Any]) -> PlannerOutcome:
    raw = _parse_json_payload(value)
    status = _require_str(raw, "status")
    created_beads = _require_str_list(raw, "created_beads")
    dependency_pairs = _require_pair_list(raw, "dependencies")
    needs_human_input = _require_bool(raw, "needs_human_input")
    summary = _require_str(raw, "summary")
    return PlannerOutcome(
        status=status,
        created_beads=created_beads,
        dependencies=dependency_pairs,
        needs_human_input=needs_human_input,
        summary=summary,
    )


def parse_executor_outcome(value: str | dict[str, Any]) -> ExecutorOutcome:
    raw = _parse_json_payload(value)
    status = _require_enum(raw, "status", EXECUTOR_STATUSES)
    bead_id = _require_str(raw, "bead_id")
    files_touched = _require_str_list(raw, "files_touched")
    new_beads = _require_str_list(raw, "new_beads")
    gates_run = _require_gate_list(raw, "gates_run", default=[])
    ready_for_review = _require_bool(raw, "ready_for_review")
    summary = _require_str(raw, "summary")
    blocking_reason = _require_optional_str(raw, "blocking_reason", default_none=True)
    return ExecutorOutcome(
        status=status,
        bead_id=bead_id,
        files_touched=files_touched,
        new_beads=new_beads,
        gates_run=gates_run,
        ready_for_review=ready_for_review,
        summary=summary,
        blocking_reason=blocking_reason,
    )


def parse_reviewer_outcome(value: str | dict[str, Any]) -> ReviewerOutcome:
    raw = _parse_json_payload(value)
    legacy_transition: bool | None = None
    if "status" in raw:
        status = _require_enum(raw, "status", REVIEWER_STATUSES)
        issues_found = _require_review_issue_list(raw, "issues_found")
        gates_run = _require_gate_list(raw, "gates_run")
    else:
        # Migration compatibility for artifacts/prompts from the previous reviewer
        # contract. New code should emit REVIEWER_OUTCOME_SCHEMA.
        decision = _require_str(raw, "decision")
        decision_map = {"approve": "approved", "reject": "rejected", "rejected": "rejected"}
        if decision not in decision_map:
            expected = "approve, reject, rejected"
            raise OutcomeProtocolError(
                f"structured outcome field 'decision' has invalid value {decision!r}; expected one of: {expected}"
            )
        status = decision_map[decision]
        legacy_transition = _require_bool(raw, "state_transition_performed")
        issues_found = [
            ReviewIssue(severity="major", summary=item, file=None)
            for item in _require_str_list(raw, "issues")
        ]
        gates_run = []
    bead_id = _require_str(raw, "bead_id")
    summary = _require_str(raw, "summary")
    return ReviewerOutcome(
        status=status,
        bead_id=bead_id,
        issues_found=issues_found,
        gates_run=gates_run,
        summary=summary,
        legacy_state_transition_performed=legacy_transition,
    )


def _parse_json_payload(value: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    payload = _extract_json_payload(value)
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise OutcomeProtocolError(
            "structured outcome payload is not valid JSON"
        ) from exc
    if not isinstance(raw, dict):
        raise OutcomeProtocolError("structured outcome payload must be a JSON object")
    return raw


def _extract_json_payload(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{"):
        return stripped
    matches = FENCED_JSON_RE.findall(text)
    if not matches:
        raise OutcomeProtocolError(
            "missing JSON structured outcome payload (expected native JSON object or fenced JSON compatibility block)"
        )
    return matches[-1].strip()


def _require_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OutcomeProtocolError(
            f"structured outcome field '{key}' must be a non-empty string"
        )
    return value.strip()


def _require_optional_str(
    raw: dict[str, Any], key: str, *, default_none: bool = False
) -> str | None:
    if key not in raw and default_none:
        return None
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise OutcomeProtocolError(
            f"structured outcome field '{key}' must be a string or null"
        )
    return value.strip() or None


def _require_bool(raw: dict[str, Any], key: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise OutcomeProtocolError(
            f"structured outcome field '{key}' must be a boolean"
        )
    return value


def _require_int(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise OutcomeProtocolError(
            f"structured outcome field '{key}' must be an integer"
        )
    return value


def _require_enum(raw: dict[str, Any], key: str, allowed: set[str]) -> str:
    value = _require_str(raw, key)
    if value not in allowed:
        expected = ", ".join(sorted(allowed))
        raise OutcomeProtocolError(
            f"structured outcome field '{key}' has invalid value {value!r}; expected one of: {expected}"
        )
    return value


def _require_str_list(raw: dict[str, Any], key: str) -> list[str]:
    value = raw.get(key)
    if not isinstance(value, list):
        raise OutcomeProtocolError(f"structured outcome field '{key}' must be a list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise OutcomeProtocolError(
                f"structured outcome field '{key}' must contain only strings"
            )
        result.append(item)
    return result


def _require_pair_list(raw: dict[str, Any], key: str) -> list[tuple[str, str]]:
    value = raw.get(key)
    if not isinstance(value, list):
        raise OutcomeProtocolError(f"structured outcome field '{key}' must be a list")
    result: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            raise OutcomeProtocolError(
                f"structured outcome field '{key}' must contain only two-item lists"
            )
        left, right = item
        if not isinstance(left, str) or not isinstance(right, str):
            raise OutcomeProtocolError(
                f"structured outcome field '{key}' pairs must contain only strings"
            )
        result.append((left, right))
    return result


def _require_gate_list(
    raw: dict[str, Any], key: str, *, default: list[GateOutcome] | None = None
) -> list[GateOutcome]:
    if key not in raw and default is not None:
        return list(default)
    value = raw.get(key)
    if not isinstance(value, list):
        raise OutcomeProtocolError(f"structured outcome field '{key}' must be a list")
    result: list[GateOutcome] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise OutcomeProtocolError(
                f"structured outcome field '{key}[{index}]' must be an object"
            )
        item_dict = cast(dict[str, Any], item)
        result.append(
            GateOutcome(
                command=_require_nested_str(item_dict, key, index, "command"),
                status=_require_nested_enum(item_dict, key, index, "status", GATE_STATUSES),
                exit_code=_require_nested_int(item_dict, key, index, "exit_code"),
                summary=_require_nested_str(item_dict, key, index, "summary"),
            )
        )
    return result


def _require_review_issue_list(raw: dict[str, Any], key: str) -> list[ReviewIssue]:
    value = raw.get(key)
    if not isinstance(value, list):
        raise OutcomeProtocolError(f"structured outcome field '{key}' must be a list")
    result: list[ReviewIssue] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise OutcomeProtocolError(
                f"structured outcome field '{key}[{index}]' must be an object"
            )
        item_dict = cast(dict[str, Any], item)
        result.append(
            ReviewIssue(
                severity=_require_nested_enum(
                    item_dict, key, index, "severity", ISSUE_SEVERITIES
                ),
                summary=_require_nested_str(item_dict, key, index, "summary"),
                file=_require_nested_optional_str(item_dict, key, index, "file"),
            )
        )
    return result


def _require_nested_str(
    raw: dict[str, Any], parent: str, index: int, key: str
) -> str:
    try:
        return _require_str(raw, key)
    except OutcomeProtocolError as exc:
        raise OutcomeProtocolError(
            str(exc).replace(f"'{key}'", f"'{parent}[{index}].{key}'")
        ) from exc


def _require_nested_optional_str(
    raw: dict[str, Any], parent: str, index: int, key: str
) -> str | None:
    try:
        return _require_optional_str(raw, key)
    except OutcomeProtocolError as exc:
        raise OutcomeProtocolError(
            str(exc).replace(f"'{key}'", f"'{parent}[{index}].{key}'")
        ) from exc


def _require_nested_int(raw: dict[str, Any], parent: str, index: int, key: str) -> int:
    try:
        return _require_int(raw, key)
    except OutcomeProtocolError as exc:
        raise OutcomeProtocolError(
            str(exc).replace(f"'{key}'", f"'{parent}[{index}].{key}'")
        ) from exc


def _require_nested_enum(
    raw: dict[str, Any], parent: str, index: int, key: str, allowed: set[str]
) -> str:
    try:
        return _require_enum(raw, key, allowed)
    except OutcomeProtocolError as exc:
        raise OutcomeProtocolError(
            str(exc).replace(f"'{key}'", f"'{parent}[{index}].{key}'")
        ) from exc
