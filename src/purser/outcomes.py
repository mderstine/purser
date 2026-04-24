from __future__ import annotations

from dataclasses import dataclass
import json
import re


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
class ExecutorOutcome:
    status: str
    bead_id: str
    files_touched: list[str]
    new_beads: list[str]
    ready_for_review: bool
    summary: str


@dataclass(frozen=True, slots=True)
class ReviewerOutcome:
    decision: str
    bead_id: str
    state_transition_performed: bool
    issues: list[str]
    summary: str


_FENCED_JSON_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def parse_planner_outcome(text: str) -> PlannerOutcome:
    raw = _parse_json_payload(text)
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


def parse_executor_outcome(text: str) -> ExecutorOutcome:
    raw = _parse_json_payload(text)
    status = _require_str(raw, "status")
    bead_id = _require_str(raw, "bead_id")
    files_touched = _require_str_list(raw, "files_touched")
    new_beads = _require_str_list(raw, "new_beads")
    ready_for_review = _require_bool(raw, "ready_for_review")
    summary = _require_str(raw, "summary")
    return ExecutorOutcome(
        status=status,
        bead_id=bead_id,
        files_touched=files_touched,
        new_beads=new_beads,
        ready_for_review=ready_for_review,
        summary=summary,
    )


def parse_reviewer_outcome(text: str) -> ReviewerOutcome:
    raw = _parse_json_payload(text)
    decision = _require_str(raw, "decision")
    bead_id = _require_str(raw, "bead_id")
    state_transition_performed = _require_bool(raw, "state_transition_performed")
    issues = _require_str_list(raw, "issues")
    summary = _require_str(raw, "summary")
    return ReviewerOutcome(
        decision=decision,
        bead_id=bead_id,
        state_transition_performed=state_transition_performed,
        issues=issues,
        summary=summary,
    )


def _parse_json_payload(text: str) -> dict:
    payload = _extract_fenced_json(text)
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise OutcomeProtocolError("structured outcome payload is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise OutcomeProtocolError("structured outcome payload must be a JSON object")
    return raw


def _extract_fenced_json(text: str) -> str:
    matches = _FENCED_JSON_RE.findall(text)
    if not matches:
        raise OutcomeProtocolError("missing fenced JSON structured outcome payload")
    return matches[-1].strip()


def _require_str(raw: dict, key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OutcomeProtocolError(f"structured outcome field '{key}' must be a non-empty string")
    return value.strip()


def _require_bool(raw: dict, key: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise OutcomeProtocolError(f"structured outcome field '{key}' must be a boolean")
    return value


def _require_str_list(raw: dict, key: str) -> list[str]:
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


def _require_pair_list(raw: dict, key: str) -> list[tuple[str, str]]:
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
