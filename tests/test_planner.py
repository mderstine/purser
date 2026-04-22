from pathlib import Path
from typing import Any, cast

import pytest

from purser.beads import Bead
from purser.config import PurserConfig
from purser.planner import PlannerService
from purser.roles import RoleResult


class FakePi:
    def __init__(self, final_text: str = "planner output") -> None:
        self.final_text = final_text
        self.calls: list[dict] = []

    def run_role(self, **kwargs):
        self.calls.append(kwargs)
        return RoleResult(
            role=kwargs["role"],
            model=kwargs["model"],
            prompt_path=kwargs["prompt_path"],
            command=[],
            exit_code=0,
            transcript=[{"type": "message_end"}],
            final_text=self.final_text,
            stderr="",
            stdout='{"type":"message_end"}\n',
        )


class FakeBeads:
    def __init__(self, snapshots: list[list[Bead]]) -> None:
        self.snapshots = snapshots
        self.calls = 0

    def list_all(self) -> list[Bead]:
        index = min(self.calls, len(self.snapshots) - 1)
        self.calls += 1
        return self.snapshots[index]


def make_bead(bead_id: str, *, spec_id: str = "/tmp/spec.md") -> Bead:
    return Bead(
        id=bead_id,
        title=bead_id,
        status="open",
        raw={
            "id": bead_id,
            "title": bead_id,
            "status": "open",
            "spec_id": spec_id,
            "acceptance_criteria": "- something verifiable",
        },
    )


def make_service(
    tmp_path: Path,
    *,
    human_approve_plan: bool = True,
    final_text: str = "planner output",
) -> tuple[PlannerService, FakePi]:
    config = PurserConfig(root=tmp_path)
    prompts_dir = tmp_path / ".purser/prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "planner.md").write_text("planner", encoding="utf-8")
    config.roles.planner_prompt = ".purser/prompts/planner.md"
    config.loop.human_approve_plan = human_approve_plan
    service = PlannerService(config)
    fake_pi = FakePi(final_text=final_text)
    cast(Any, service).pi = fake_pi
    return service, fake_pi


def test_intake_spec_synthesizes_markdown_file(tmp_path: Path) -> None:
    service, fake_pi = make_service(tmp_path, final_text="# Improved Spec\nBody")
    spec = tmp_path / "spec.md"
    spec.write_text("original", encoding="utf-8")

    result = service.intake_spec(spec, synthesize=True)

    assert result.output_path is not None
    assert result.output_path.read_text(encoding="utf-8") == "# Improved Spec\nBody\n"
    assert "Synthesize: true" in fake_pi.calls[0]["message"]


def test_intake_spec_without_synthesis_writes_no_file(tmp_path: Path) -> None:
    service, fake_pi = make_service(tmp_path)
    spec = tmp_path / "spec.md"
    spec.write_text("original", encoding="utf-8")

    result = service.intake_spec(spec, synthesize=False)

    assert result.output_path is None
    assert "Synthesize: false" in fake_pi.calls[0]["message"]


def test_plan_spec_requires_existing_spec(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path)

    with pytest.raises(FileNotFoundError):
        service.plan_spec(Path("missing.md"))


def test_plan_spec_message_includes_human_approval_when_enabled(tmp_path: Path) -> None:
    service, fake_pi = make_service(tmp_path, human_approve_plan=True)
    spec = tmp_path / "spec.md"
    spec.write_text("original", encoding="utf-8")
    cast(Any, service).beads = FakeBeads([[], [make_bead("bd-1", spec_id=str(spec))]])

    service.plan_spec(spec)

    assert (
        "Human approval is required before implementation"
        in fake_pi.calls[0]["message"]
    )
    assert "must actually create the beads" in fake_pi.calls[0]["message"]
    assert fake_pi.calls[0]["tools"] == "read,bash,grep,find,ls"
    assert "Every created bead must include --spec-id" in fake_pi.calls[0]["message"]
    assert "Preserve exact literals from the spec" in fake_pi.calls[0]["message"]


def test_plan_spec_message_includes_autonomous_note_when_disabled(
    tmp_path: Path,
) -> None:
    service, fake_pi = make_service(tmp_path, human_approve_plan=False)
    spec = tmp_path / "spec.md"
    spec.write_text("original", encoding="utf-8")
    cast(Any, service).beads = FakeBeads([[], [make_bead("bd-1", spec_id=str(spec))]])

    service.plan_spec(spec)

    assert (
        "Human approval is disabled; proceed with autonomous planning."
        in fake_pi.calls[0]["message"]
    )


def test_plan_spec_raises_if_no_beads_created(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path, final_text="Only prose, no mutations")
    cast(Any, service).beads = FakeBeads([[], []])
    spec = tmp_path / "spec.md"
    spec.write_text("original", encoding="utf-8")

    with pytest.raises(RuntimeError) as exc:
        service.plan_spec(spec)

    assert "did not create any beads" in str(exc.value)
    assert "Only prose, no mutations" in str(exc.value)


def test_planner_prompt_file_must_exist(tmp_path: Path) -> None:
    config = PurserConfig(root=tmp_path)
    config.roles.planner_prompt = ".purser/prompts/planner.md"
    service = PlannerService(config)

    with pytest.raises(FileNotFoundError):
        service.intake_spec(Path("spec.md"), synthesize=False)
