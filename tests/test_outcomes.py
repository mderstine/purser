import pytest

from purser.outcomes import (
    EXECUTOR_OUTCOME_SCHEMA,
    REVIEWER_OUTCOME_SCHEMA,
    OutcomeProtocolError,
    parse_executor_outcome,
    parse_planner_outcome,
    parse_reviewer_outcome,
)


def test_parse_planner_outcome_from_fenced_json() -> None:
    text = """Planner summary.

```json
{
  "status": "planned",
  "created_beads": ["bd-1", "bd-2"],
  "dependencies": [["bd-1", "bd-2"]],
  "needs_human_input": false,
  "summary": "created two beads"
}
```
"""

    outcome = parse_planner_outcome(text)

    assert outcome.status == "planned"
    assert outcome.created_beads == ["bd-1", "bd-2"]
    assert outcome.dependencies == [("bd-1", "bd-2")]
    assert outcome.needs_human_input is False
    assert outcome.summary == "created two beads"


def test_parse_executor_outcome_from_fenced_json_compatibility() -> None:
    text = """Done.

```json
{
  "status": "completed",
  "bead_id": "bd-9",
  "files_touched": ["src/x.py"],
  "new_beads": [],
  "ready_for_review": true,
  "summary": "implemented bead"
}
```
"""

    outcome = parse_executor_outcome(text)

    assert outcome.status == "completed"
    assert outcome.bead_id == "bd-9"
    assert outcome.files_touched == ["src/x.py"]
    assert outcome.new_beads == []
    assert outcome.gates_run == []
    assert outcome.ready_for_review is True
    assert outcome.blocking_reason is None


def test_parse_executor_outcome_from_native_dict() -> None:
    outcome = parse_executor_outcome(
        {
            "status": "blocked",
            "bead_id": "bd-9",
            "files_touched": [],
            "new_beads": ["bd-10"],
            "gates_run": [
                {
                    "command": "uv run pytest",
                    "status": "skipped",
                    "exit_code": 0,
                    "summary": "not applicable until clarification",
                }
            ],
            "ready_for_review": False,
            "summary": "needs product decision",
            "blocking_reason": "missing acceptance criterion",
        }
    )

    assert outcome.status == "blocked"
    assert outcome.gates_run[0].command == "uv run pytest"
    assert outcome.gates_run[0].status == "skipped"
    assert outcome.blocking_reason == "missing acceptance criterion"


def test_parse_reviewer_outcome_from_legacy_fenced_json() -> None:
    text = """Review complete.

```json
{
  "decision": "approve",
  "bead_id": "bd-9",
  "state_transition_performed": true,
  "issues": [],
  "summary": "looks good"
}
```
"""

    outcome = parse_reviewer_outcome(text)

    assert outcome.status == "approved"
    assert outcome.decision == "approve"
    assert outcome.bead_id == "bd-9"
    assert outcome.state_transition_performed is True
    assert outcome.issues == []
    assert outcome.summary == "looks good"


def test_parse_reviewer_outcome_from_native_dict() -> None:
    outcome = parse_reviewer_outcome(
        {
            "status": "rejected",
            "bead_id": "bd-9",
            "issues_found": [
                {"severity": "major", "summary": "missing test", "file": "tests/x.py"}
            ],
            "gates_run": [
                {
                    "command": "uv run pytest tests/x.py",
                    "status": "failed",
                    "exit_code": 1,
                    "summary": "test failed",
                }
            ],
            "summary": "needs test fix",
        }
    )

    assert outcome.status == "rejected"
    assert outcome.decision == "rejected"
    assert outcome.state_transition_performed is False
    assert outcome.issues == ["missing test"]
    assert outcome.issues_found[0].severity == "major"
    assert outcome.gates_run[0].exit_code == 1


def test_outcome_schema_constants_name_required_fields() -> None:
    assert "gates_run" in EXECUTOR_OUTCOME_SCHEMA["required"]
    assert "blocking_reason" in EXECUTOR_OUTCOME_SCHEMA["required"]
    assert "issues_found" in REVIEWER_OUTCOME_SCHEMA["required"]
    assert REVIEWER_OUTCOME_SCHEMA["properties"]["status"]["enum"] == [
        "approved",
        "blocked",
        "failed",
        "rejected",
    ]


def test_parse_outcome_requires_json_payload() -> None:
    with pytest.raises(OutcomeProtocolError) as exc:
        parse_planner_outcome("no structured payload here")

    assert "missing JSON structured outcome payload" in str(exc.value)


def test_parse_outcome_requires_valid_json() -> None:
    with pytest.raises(OutcomeProtocolError) as exc:
        parse_executor_outcome("```json\n{not valid}\n```")

    assert "not valid JSON" in str(exc.value)


def test_parse_outcome_requires_expected_field_types() -> None:
    bad = """```json
{
  "decision": "approve",
  "bead_id": "bd-1",
  "state_transition_performed": "yes",
  "issues": [],
  "summary": "ok"
}
```"""

    with pytest.raises(OutcomeProtocolError) as exc:
        parse_reviewer_outcome(bad)

    assert "state_transition_performed" in str(exc.value)


def test_parse_outcome_rejects_invalid_enum_values() -> None:
    with pytest.raises(OutcomeProtocolError) as exc:
        parse_executor_outcome(
            {
                "status": "done",
                "bead_id": "bd-1",
                "files_touched": [],
                "new_beads": [],
                "gates_run": [],
                "ready_for_review": True,
                "summary": "ok",
                "blocking_reason": None,
            }
        )

    assert "status" in str(exc.value)
    assert "done" in str(exc.value)
    assert "completed" in str(exc.value)


def test_parse_outcome_reports_nested_missing_fields() -> None:
    with pytest.raises(OutcomeProtocolError) as exc:
        parse_reviewer_outcome(
            {
                "status": "approved",
                "bead_id": "bd-1",
                "issues_found": [{"severity": "minor", "file": None}],
                "gates_run": [],
                "summary": "ok",
            }
        )

    assert "issues_found[0].summary" in str(exc.value)
