from pathlib import Path

from purser.beads import Bead
from purser.config import PurserConfig
from purser.gates import GateResult
from purser.loop import PurserLoop
from purser.roles import RoleResult


class FakeBeads:
    def __init__(self, bead: Bead) -> None:
        self._bead = bead
        self.incremented = False
        self.status_updates: list[str] = []

    def show(self, bead_id: str) -> Bead:
        assert bead_id == self._bead.id
        return self._bead

    def increment_attempts(self, bead_id: str) -> Bead:
        assert bead_id == self._bead.id
        self.incremented = True
        self._bead.raw.setdefault("metadata", {})["purser_executor_attempts"] = 1
        return self._bead

    def update_status(self, bead_id: str, status: str, notes: str | None = None) -> Bead:
        assert bead_id == self._bead.id
        self.status_updates.append(status)
        self._bead.status = status
        return self._bead

    def reopen(self, bead_id: str, reason: str | None = None) -> Bead:
        assert bead_id == self._bead.id
        self._bead.status = "open"
        return self._bead


class FakePi:
    def run_role(self, **kwargs):
        return RoleResult(
            role=kwargs["role"],
            model=kwargs["model"],
            prompt_path=kwargs["prompt_path"],
            command=[],
            exit_code=0,
            transcript=[{"type": "message_end"}],
            final_text="ok",
            stderr="",
            stdout="{}\n",
        )


class FakeGates:
    def __init__(self) -> None:
        self.calls = 0

    def run_all(self, bead_id: str):
        self.calls += 1
        return [GateResult(name="tests", command="pytest", exit_code=0, stdout="", stderr="")]


def test_execute_increments_attempts_and_moves_to_review(tmp_path: Path) -> None:
    bead = Bead(id="bd-1", title="Test", status="open", raw={"metadata": {}})
    loop = PurserLoop(PurserConfig(root=tmp_path))
    loop.beads = FakeBeads(bead)
    loop.pi = FakePi()
    loop.gates = FakeGates()
    (tmp_path / ".purser").mkdir(parents=True, exist_ok=True)
    executor_prompt = tmp_path / ".purser/prompts/executor.md"
    reviewer_prompt = tmp_path / ".purser/prompts/reviewer.md"
    executor_prompt.parent.mkdir(parents=True, exist_ok=True)
    executor_prompt.write_text("executor", encoding="utf-8")
    reviewer_prompt.write_text("reviewer", encoding="utf-8")
    loop.config.roles.executor_prompt = ".purser/prompts/executor.md"
    loop.config.roles.reviewer_prompt = ".purser/prompts/reviewer.md"

    loop._execute(bead)

    assert loop.beads.incremented is True
    assert "in_review" in loop.beads.status_updates
