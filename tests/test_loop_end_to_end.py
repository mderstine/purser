from pathlib import Path
from typing import Any, cast

import pytest

from purser.beads import (
    REVIEW_READY_METADATA_KEY,
    Bead,
    is_review_ready,
    normalize_status,
)
from purser.config import PurserConfig
from purser.gates import GateFailure, GateResult
from purser.loop import PurserLoop
from purser.roles import RoleResult


def executor_payload(bead_id: str) -> str:
    return (
        "Executor summary.\n\n"
        "```json\n"
        "{\n"
        '  "status": "completed",\n'
        f'  "bead_id": "{bead_id}",\n'
        '  "files_touched": [],\n'
        '  "new_beads": [],\n'
        '  "ready_for_review": true,\n'
        '  "summary": "executor done"\n'
        "}\n"
        "```\n"
    )


def reviewer_payload(bead_id: str, *, decision: str, summary: str) -> str:
    issues = "[]" if decision == "approve" else '["changes requested"]'
    return (
        "Reviewer summary.\n\n"
        "```json\n"
        "{\n"
        f'  "decision": "{decision}",\n'
        f'  "bead_id": "{bead_id}",\n'
        '  "state_transition_performed": true,\n'
        f'  "issues": {issues},\n'
        f'  "summary": "{summary}"\n'
        "}\n"
        "```\n"
    )


class ScenarioBeads:
    def __init__(self, bead: Bead) -> None:
        self.bead = bead
        self.comments: list[tuple[str, str]] = []
        self.notes: list[tuple[str, str, str | None]] = []
        self.claimed = False
        self.closed = False

    def show(self, bead_id: str) -> Bead:
        assert bead_id == self.bead.id
        return self.bead

    def ready(self, limit: int = 1) -> list[Bead]:
        return [self.bead] if self.bead.normalized_status == "open" else []

    def list_by_statuses(self, statuses: list[str]) -> list[Bead]:
        wanted = {normalize_status(status) for status in statuses}
        return [self.bead] if self.bead.normalized_status in wanted else []

    def list_review_ready(self) -> list[Bead]:
        return [self.bead] if is_review_ready(self.bead) else []

    def claim(self, bead_id: str) -> Bead:
        assert bead_id == self.bead.id
        self.claimed = True
        self.bead.status = "in_progress"
        return self.bead

    def increment_attempts(self, bead_id: str) -> Bead:
        assert bead_id == self.bead.id
        metadata = self.bead.raw.setdefault("metadata", {})
        metadata["purser_executor_attempts"] = (
            int(metadata.get("purser_executor_attempts", 0)) + 1
        )
        return self.bead

    def update_status(
        self, bead_id: str, status: str, notes: str | None = None
    ) -> Bead:
        assert bead_id == self.bead.id
        self.notes.append((bead_id, status, notes))
        self.bead.status = status
        return self.bead

    def reopen(self, bead_id: str, reason: str | None = None) -> Bead:
        assert bead_id == self.bead.id
        self.bead.status = "open"
        return self.bead

    def close(self, bead_id: str, reason: str | None = None) -> Bead:
        assert bead_id == self.bead.id
        self.closed = True
        self.bead.status = "closed"
        return self.bead

    def mark_review_ready(self, bead_id: str, ready: bool = True) -> Bead:
        assert bead_id == self.bead.id
        self.bead.raw.setdefault("metadata", {})[REVIEW_READY_METADATA_KEY] = (
            "true" if ready else "false"
        )
        return self.bead

    def comment(self, bead_id: str, text: str) -> None:
        self.comments.append((bead_id, text))


class ScenarioPi:
    def __init__(self, beads: ScenarioBeads, reviewer_closes: bool = True) -> None:
        self.beads = beads
        self.calls: list[str] = []
        self.reviewer_closes = reviewer_closes

    def run_role(self, **kwargs):
        role = kwargs["role"]
        self.calls.append(role)
        if role == "executor":
            text = executor_payload(self.beads.bead.id)
        else:
            if self.reviewer_closes:
                self.beads.close(self.beads.bead.id, reason="review passed")
                text = reviewer_payload(
                    self.beads.bead.id,
                    decision="approve",
                    summary="Reviewer validated and closed bead",
                )
            else:
                self.beads.bead.status = "open"
                text = reviewer_payload(
                    self.beads.bead.id,
                    decision="reject",
                    summary="Reviewer requested changes",
                )
        return RoleResult(
            role=role,
            model=kwargs["model"],
            prompt_path=kwargs["prompt_path"],
            command=[],
            exit_code=0,
            transcript=[{"type": "message_end"}],
            final_text=text,
            stderr="",
            stdout='{"type":"message_end"}\n',
        )


class ScenarioGates:
    def __init__(self, fail_on_call: int | None = None) -> None:
        self.calls = 0
        self.fail_on_call = fail_on_call

    def run_all(self, bead_id: str):
        self.calls += 1
        result = GateResult(
            name="tests", command="pytest", exit_code=0, stdout="ok", stderr=""
        )
        if self.fail_on_call == self.calls:
            failed = GateResult(
                name="tests", command="pytest", exit_code=1, stdout="", stderr="boom"
            )
            raise GateFailure(failed)
        return [result]


def _configure_loop(
    tmp_path: Path,
    bead: Bead,
    reviewer_closes: bool = True,
    fail_on_gate_call: int | None = None,
) -> tuple[PurserLoop, ScenarioBeads, ScenarioPi, ScenarioGates]:
    config = PurserConfig(root=tmp_path)
    prompts_dir = tmp_path / ".purser/prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for name in ["executor", "reviewer"]:
        (prompts_dir / f"{name}.md").write_text(name, encoding="utf-8")
    config.roles.executor_prompt = ".purser/prompts/executor.md"
    config.roles.reviewer_prompt = ".purser/prompts/reviewer.md"
    loop = PurserLoop(config)
    beads = ScenarioBeads(bead)
    pi = ScenarioPi(beads, reviewer_closes=reviewer_closes)
    gates = ScenarioGates(fail_on_call=fail_on_gate_call)
    cast(Any, loop).beads = beads
    cast(Any, loop).pi = pi
    cast(Any, loop).gates = gates
    return loop, beads, pi, gates


def test_run_once_end_to_end_closes_and_logs_validation(tmp_path: Path) -> None:
    bead = Bead(
        id="bd-1",
        title="Add feature",
        status="open",
        raw={"metadata": {}, "spec_id": "specs/demo.md §1"},
    )
    loop, beads, pi, gates = _configure_loop(tmp_path, bead)

    processed = loop.run_once()

    assert processed == "bd-1"
    assert beads.claimed is True
    assert beads.closed is True
    assert pi.calls == ["executor", "reviewer"]
    assert gates.calls == 2
    validation = (tmp_path / "VALIDATION.md").read_text(encoding="utf-8")
    assert "## bd-1 — Add feature" in validation
    assert "Reviewer validated and closed bead" in validation
    assert "**Executor attempts:** 1" in validation


def test_run_once_reviews_metadata_ready_bead_without_custom_status(
    tmp_path: Path,
) -> None:
    bead = Bead(
        id="bd-meta",
        title="Metadata ready",
        status="in_progress",
        raw={
            "metadata": {
                "purser_executor_attempts": 1,
                REVIEW_READY_METADATA_KEY: "true",
            }
        },
    )
    loop, beads, pi, gates = _configure_loop(tmp_path, bead)

    processed = loop.run_once()

    assert processed == "bd-meta"
    assert beads.claimed is False
    assert beads.closed is True
    assert pi.calls == ["reviewer"]
    assert gates.calls == 1


def test_run_once_review_rejection_reopens_bead(tmp_path: Path) -> None:
    bead = Bead(id="bd-2", title="Need changes", status="open", raw={"metadata": {}})
    loop, beads, pi, gates = _configure_loop(tmp_path, bead, reviewer_closes=False)

    processed = loop.run_once()

    assert processed == "bd-2"
    assert beads.bead.normalized_status == "open"
    assert beads.bead.metadata[REVIEW_READY_METADATA_KEY] == "false"
    assert any(
        status == "open" and notes == "Reviewer requested changes"
        for _, status, notes in beads.notes
    )
    assert not (tmp_path / "VALIDATION.md").exists()
    assert pi.calls == ["executor", "reviewer"]
    assert gates.calls == 2


def test_run_all_blocks_bead_at_iteration_cap(tmp_path: Path) -> None:
    bead = Bead(
        id="bd-3",
        title="Stuck bead",
        status="open",
        raw={"metadata": {"purser_executor_attempts": 5}},
    )
    loop, beads, pi, gates = _configure_loop(tmp_path, bead)
    loop.config.loop.max_iterations_per_bead = 5

    result = loop.run_all()

    assert result.status == "done"
    assert result.processed_beads == ["bd-3"]
    assert beads.bead.normalized_status == "blocked"
    assert pi.calls == []
    assert gates.calls == 0


def test_review_gate_failure_reopens_bead_without_validation_log(
    tmp_path: Path,
) -> None:
    bead = Bead(
        id="bd-4",
        title="Gate fail on review",
        status="in_review",
        raw={"metadata": {"purser_executor_attempts": 2}},
    )
    loop, beads, pi, gates = _configure_loop(
        tmp_path, bead, reviewer_closes=True, fail_on_gate_call=1
    )

    processed = loop.run_once("bd-4")

    assert processed == "bd-4"
    assert beads.bead.normalized_status == "open"
    assert beads.bead.metadata[REVIEW_READY_METADATA_KEY] == "false"
    assert not (tmp_path / "VALIDATION.md").exists()
    assert pi.calls == ["reviewer"]


def test_review_raises_if_reviewer_payload_is_missing(tmp_path: Path) -> None:
    bead = Bead(
        id="bd-5",
        title="Missing payload",
        status="in_review",
        raw={"metadata": {"purser_executor_attempts": 1}},
    )
    loop, beads, _, gates = _configure_loop(tmp_path, bead, reviewer_closes=False)

    class ProseOnlyReviewer(ScenarioPi):
        def run_role(self, **kwargs):
            role = kwargs["role"]
            self.calls.append(role)
            return RoleResult(
                role=role,
                model=kwargs["model"],
                prompt_path=kwargs["prompt_path"],
                command=[],
                exit_code=0,
                transcript=[{"type": "message_end"}],
                final_text="Verdict: correct, complete, and cohesive. Approve.",
                stderr="",
                stdout='{"type":"message_end"}\n',
            )

    cast(Any, loop).pi = ProseOnlyReviewer(beads, reviewer_closes=False)

    with pytest.raises(RuntimeError) as exc:
        loop.run_once("bd-5")

    assert "structured outcome payload" in str(exc.value)
    assert gates.calls == 0
