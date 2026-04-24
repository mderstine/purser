import pytest

from purser.outcomes import (
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


def test_parse_executor_outcome_from_fenced_json() -> None:
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
    assert outcome.ready_for_review is True


def test_parse_reviewer_outcome_from_fenced_json() -> None:
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

    assert outcome.decision == "approve"
    assert outcome.bead_id == "bd-9"
    assert outcome.state_transition_performed is True
    assert outcome.issues == []
    assert outcome.summary == "looks good"


def test_parse_outcome_requires_fenced_json() -> None:
    with pytest.raises(OutcomeProtocolError) as exc:
        parse_planner_outcome("no structured payload here")

    assert "missing fenced JSON" in str(exc.value)


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
