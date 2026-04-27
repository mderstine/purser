import json
from pathlib import Path
from typing import Any, cast

import pytest

from purser.beads import REVIEW_READY_METADATA_KEY, Bead
from purser.config import PurserConfig
from purser.gates import GateResult
from purser.loop import PurserLoop
from purser.roles import RoleResult


def executor_payload(bead_id: str, *, ready_for_review: bool = True) -> str:
    ready = "true" if ready_for_review else "false"
    return (
        "Executor summary.\n\n"
        "```json\n"
        "{\n"
        '  "status": "completed",\n'
        f'  "bead_id": "{bead_id}",\n'
        '  "files_touched": [],\n'
        '  "new_beads": [],\n'
        f'  "ready_for_review": {ready},\n'
        '  "summary": "executor done"\n'
        "}\n"
        "```\n"
    )


class FakeBeads:
    def __init__(self, bead: Bead) -> None:
        self._bead = bead
        self.incremented = False
        self.status_updates: list[str] = []
        self.closed = False

    def show(self, bead_id: str) -> Bead:
        assert bead_id == self._bead.id
        return self._bead

    def increment_attempts(self, bead_id: str) -> Bead:
        assert bead_id == self._bead.id
        self.incremented = True
        self._bead.raw.setdefault("metadata", {})["purser_executor_attempts"] = 1
        return self._bead

    def update_status(
        self, bead_id: str, status: str, notes: str | None = None
    ) -> Bead:
        assert bead_id == self._bead.id
        self.status_updates.append(status)
        self._bead.status = status
        return self._bead

    def reopen(self, bead_id: str, reason: str | None = None) -> Bead:
        assert bead_id == self._bead.id
        self._bead.status = "open"
        return self._bead

    def close(self, bead_id: str, reason: str | None = None) -> Bead:
        assert bead_id == self._bead.id
        self.closed = True
        self._bead.status = "closed"
        return self._bead

    def mark_review_ready(self, bead_id: str, ready: bool = True) -> Bead:
        assert bead_id == self._bead.id
        self._bead.raw.setdefault("metadata", {})[REVIEW_READY_METADATA_KEY] = (
            "true" if ready else "false"
        )
        return self._bead


class FakePi:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run_role(self, **kwargs):
        self.calls.append(kwargs)
        bead_id = "bd-1"
        message = kwargs.get("message", "")
        if "Execute bead bd-2." in message:
            bead_id = "bd-2"
        return RoleResult(
            role=kwargs["role"],
            model=kwargs["model"],
            prompt_path=kwargs["prompt_path"],
            command=[],
            exit_code=0,
            transcript=[{"type": "message_end"}],
            final_text=executor_payload(bead_id),
            stderr="",
            stdout="{}\n",
        )


class FakeGates:
    def __init__(self) -> None:
        self.calls = 0

    def run_all(self, bead_id: str):
        self.calls += 1
        return [
            GateResult(
                name="tests", command="pytest", exit_code=0, stdout="", stderr=""
            )
        ]


def test_execute_increments_attempts_and_marks_review_ready(tmp_path: Path) -> None:
    bead = Bead(id="bd-1", title="Test", status="open", raw={"metadata": {}})
    loop = PurserLoop(PurserConfig(root=tmp_path))
    fake_beads = FakeBeads(bead)
    fake_pi = FakePi()
    cast(Any, loop).beads = fake_beads
    cast(Any, loop).pi = fake_pi
    cast(Any, loop).gates = FakeGates()
    (tmp_path / ".purser").mkdir(parents=True, exist_ok=True)
    executor_prompt = tmp_path / ".purser/prompts/executor.md"
    reviewer_prompt = tmp_path / ".purser/prompts/reviewer.md"
    executor_prompt.parent.mkdir(parents=True, exist_ok=True)
    executor_prompt.write_text("executor", encoding="utf-8")
    reviewer_prompt.write_text("reviewer", encoding="utf-8")
    loop.config.roles.executor_prompt = ".purser/prompts/executor.md"
    loop.config.roles.reviewer_prompt = ".purser/prompts/reviewer.md"

    loop._execute(bead)

    assert fake_beads.incremented is True
    assert "in_review" not in fake_beads.status_updates
    assert bead.metadata[REVIEW_READY_METADATA_KEY] == "true"
    artifact_files = sorted((tmp_path / ".purser" / "runs").glob("*.json"))
    assert artifact_files
    artifact = json.loads(artifact_files[-1].read_text(encoding="utf-8"))
    assert artifact["kind"] == "executor"
    assert artifact["bead_id"] == "bd-1"
    assert artifact["structured_outcome"]["bead_id"] == "bd-1"
    assert artifact["gate_results"][0]["name"] == "tests"


def test_execute_raises_if_executor_payload_is_missing(tmp_path: Path) -> None:
    bead = Bead(id="bd-3", title="Test", status="open", raw={"metadata": {}})
    loop = PurserLoop(PurserConfig(root=tmp_path))
    fake_beads = FakeBeads(bead)
    fake_pi = FakePi()
    cast(Any, loop).beads = fake_beads
    cast(Any, loop).pi = fake_pi
    cast(Any, loop).gates = FakeGates()
    executor_prompt = tmp_path / ".purser/prompts/executor.md"
    reviewer_prompt = tmp_path / ".purser/prompts/reviewer.md"
    executor_prompt.parent.mkdir(parents=True, exist_ok=True)
    executor_prompt.write_text("executor", encoding="utf-8")
    reviewer_prompt.write_text("reviewer", encoding="utf-8")
    loop.config.roles.executor_prompt = ".purser/prompts/executor.md"
    loop.config.roles.reviewer_prompt = ".purser/prompts/reviewer.md"

    cast(Any, fake_pi).run_role = lambda **kwargs: RoleResult(
        role=kwargs["role"],
        model=kwargs["model"],
        prompt_path=kwargs["prompt_path"],
        command=[],
        exit_code=0,
        transcript=[{"type": "message_end"}],
        final_text="only prose",
        stderr="",
        stdout="{}\n",
    )

    with pytest.raises(RuntimeError) as exc:
        loop._execute(bead)

    assert "structured outcome payload" in str(exc.value)
    artifact_files = sorted((tmp_path / ".purser" / "runs").glob("*.json"))
    assert artifact_files
    artifact = json.loads(artifact_files[-1].read_text(encoding="utf-8"))
    assert artifact["kind"] == "executor"
    assert artifact["errors"]
    assert artifact["structured_outcome"] is None
    assert artifact["extra"]["repair_attempts"]
    assert artifact["extra"]["repair_attempts"][0]["parsed"] is False


def test_execute_repairs_missing_executor_outcome(tmp_path: Path) -> None:
    bead = Bead(id="bd-4", title="Test", status="open", raw={"metadata": {}})
    loop = PurserLoop(PurserConfig(root=tmp_path))
    fake_beads = FakeBeads(bead)
    fake_pi = FakePi()
    cast(Any, loop).beads = fake_beads
    cast(Any, loop).pi = fake_pi
    cast(Any, loop).gates = FakeGates()
    executor_prompt = tmp_path / ".purser/prompts/executor.md"
    reviewer_prompt = tmp_path / ".purser/prompts/reviewer.md"
    executor_prompt.parent.mkdir(parents=True, exist_ok=True)
    executor_prompt.write_text("executor", encoding="utf-8")
    reviewer_prompt.write_text("reviewer", encoding="utf-8")
    loop.config.roles.executor_prompt = ".purser/prompts/executor.md"
    loop.config.roles.reviewer_prompt = ".purser/prompts/reviewer.md"

    def run_role(**kwargs):
        role = kwargs["role"]
        final_text = "implemented bd-4 successfully"
        if role == "executor-outcome-repair":
            final_text = json.dumps(
                {
                    "status": "completed",
                    "bead_id": "bd-4",
                    "files_touched": [],
                    "new_beads": [],
                    "gates_run": [],
                    "ready_for_review": True,
                    "summary": "executor done",
                    "blocking_reason": None,
                }
            )
        return RoleResult(
            role=role,
            model=kwargs["model"],
            prompt_path=kwargs["prompt_path"],
            command=[],
            exit_code=0,
            transcript=[{"type": "message_end"}],
            final_text=final_text,
            stderr="",
            stdout="{}\n",
        )

    cast(Any, fake_pi).run_role = run_role

    loop._execute(bead)

    artifact_files = sorted((tmp_path / ".purser" / "runs").glob("*.json"))
    artifact = json.loads(artifact_files[-1].read_text(encoding="utf-8"))
    assert artifact["structured_outcome"]["bead_id"] == "bd-4"
    assert artifact["extra"]["repair_attempts"][0]["parsed"] is True
    assert artifact["extra"]["repair_attempts"][0]["role"] == "executor-outcome-repair"


def test_reviewer_repairs_malformed_outcome(tmp_path: Path) -> None:
    bead = Bead(id="bd-5", title="Test", status="in_progress", raw={"metadata": {}})
    loop = PurserLoop(PurserConfig(root=tmp_path))
    fake_beads = FakeBeads(bead)
    fake_pi = FakePi()
    cast(Any, loop).beads = fake_beads
    cast(Any, loop).pi = fake_pi
    cast(Any, loop).gates = FakeGates()
    reviewer_prompt = tmp_path / ".purser/prompts/reviewer.md"
    executor_prompt = tmp_path / ".purser/prompts/executor.md"
    reviewer_prompt.parent.mkdir(parents=True, exist_ok=True)
    reviewer_prompt.write_text("reviewer", encoding="utf-8")
    executor_prompt.write_text("executor", encoding="utf-8")
    loop.config.roles.reviewer_prompt = ".purser/prompts/reviewer.md"
    loop.config.roles.executor_prompt = ".purser/prompts/executor.md"

    def run_role(**kwargs):
        role = kwargs["role"]
        if role == "reviewer":
            fake_beads.close("bd-5")
            final_text = "```json\n{not valid}\n```"
        else:
            final_text = json.dumps(
                {
                    "decision": "approve",
                    "bead_id": "bd-5",
                    "state_transition_performed": True,
                    "issues": [],
                    "summary": "reviewer approved",
                }
            )
        return RoleResult(
            role=role,
            model=kwargs["model"],
            prompt_path=kwargs["prompt_path"],
            command=[],
            exit_code=0,
            transcript=[{"type": "message_end"}],
            final_text=final_text,
            stderr="",
            stdout="{}\n",
        )

    cast(Any, fake_pi).run_role = run_role

    loop._review(bead)

    artifact_files = sorted((tmp_path / ".purser" / "runs").glob("*.json"))
    artifact = json.loads(artifact_files[-1].read_text(encoding="utf-8"))
    assert artifact["kind"] == "reviewer"
    assert artifact["structured_outcome"]["decision"] == "approve"
    assert artifact["extra"]["repair_attempts"][0]["parsed"] is True


def test_reviewer_message_assigns_lifecycle_to_purser(tmp_path: Path) -> None:
    bead = Bead(id="bd-6", title="Test", status="in_progress", raw={"metadata": {}})
    loop = PurserLoop(PurserConfig(root=tmp_path))
    fake_beads = FakeBeads(bead)
    fake_pi = FakePi()
    cast(Any, loop).beads = fake_beads
    cast(Any, loop).pi = fake_pi
    cast(Any, loop).gates = FakeGates()
    reviewer_prompt = tmp_path / ".purser/prompts/reviewer.md"
    executor_prompt = tmp_path / ".purser/prompts/executor.md"
    reviewer_prompt.parent.mkdir(parents=True, exist_ok=True)
    reviewer_prompt.write_text("reviewer", encoding="utf-8")
    executor_prompt.write_text("executor", encoding="utf-8")
    loop.config.roles.reviewer_prompt = ".purser/prompts/reviewer.md"
    loop.config.roles.executor_prompt = ".purser/prompts/executor.md"

    def run_role(**kwargs):
        role = kwargs["role"]
        fake_pi.calls.append(kwargs)
        return RoleResult(
            role=role,
            model=kwargs["model"],
            prompt_path=kwargs["prompt_path"],
            command=[],
            exit_code=0,
            transcript=[{"type": "message_end"}],
            final_text=json.dumps(
                {
                    "status": "approved",
                    "bead_id": "bd-6",
                    "issues_found": [],
                    "gates_run": [],
                    "summary": "reviewer approved",
                }
            ),
            stderr="",
            stdout="{}\n",
        )

    cast(Any, fake_pi).run_role = run_role

    loop._review(bead)

    message = fake_pi.calls[0]["message"]
    assert "Do not close, reopen" in message
    assert "Purser will perform Beads status transitions" in message
    assert fake_beads.closed is True


def test_execute_message_requires_exact_literals_and_no_guessing(
    tmp_path: Path,
) -> None:
    bead = Bead(
        id="bd-2",
        title="Test",
        status="open",
        raw={"metadata": {}, "spec_id": "specs/demo.md"},
    )
    loop = PurserLoop(PurserConfig(root=tmp_path))
    fake_beads = FakeBeads(bead)
    fake_pi = FakePi()
    cast(Any, loop).beads = fake_beads
    cast(Any, loop).pi = fake_pi
    cast(Any, loop).gates = FakeGates()
    executor_prompt = tmp_path / ".purser/prompts/executor.md"
    reviewer_prompt = tmp_path / ".purser/prompts/reviewer.md"
    executor_prompt.parent.mkdir(parents=True, exist_ok=True)
    executor_prompt.write_text("executor", encoding="utf-8")
    reviewer_prompt.write_text("reviewer", encoding="utf-8")
    loop.config.roles.executor_prompt = ".purser/prompts/executor.md"
    loop.config.roles.reviewer_prompt = ".purser/prompts/reviewer.md"

    loop._execute(bead)

    message = fake_pi.calls[0]["message"]
    assert "The originating spec is: specs/demo.md" in message
    assert (
        "Treat exact file names, exact strings, exact paths, and exact commands as binding requirements"
        in message
    )
    assert "do not guess" in message
    assert "Purser owns lifecycle transitions" in message
