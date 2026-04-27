import json
from pathlib import Path
from typing import Any, cast

import pytest

from purser.beads import Bead
from purser.config import PurserConfig
from purser.planner import PlannerService
from purser.roles import RoleExecutionError, RoleResult


def planner_payload(created_beads: list[str], summary: str = "planner output") -> str:
    deps = "[]"
    beads = ", ".join(f'"{bead}"' for bead in created_beads)
    return (
        f"Summary: {summary}\n\n"
        "```json\n"
        "{\n"
        '  "status": "planned",\n'
        f'  "created_beads": [{beads}],\n'
        f'  "dependencies": {deps},\n'
        '  "needs_human_input": false,\n'
        f'  "summary": "{summary}"\n'
        "}\n"
        "```\n"
    )


class FakePi:
    def __init__(
        self, final_text: str = "planner output", error: Exception | None = None
    ) -> None:
        self.final_text = final_text
        self.error = error
        self.calls: list[dict] = []

    def run_role(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
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
        self.metadata_updates: list[tuple[str, str, str]] = []

    def list_all(self) -> list[Bead]:
        index = min(self.calls, len(self.snapshots) - 1)
        self.calls += 1
        return self.snapshots[index]

    def set_metadata(self, bead_id: str, key: str, value: str) -> Bead:
        self.metadata_updates.append((bead_id, key, value))
        for snapshot in self.snapshots:
            for bead in snapshot:
                if bead.id == bead_id:
                    bead.raw.setdefault("metadata", {})[key] = value
                    return bead
        raise AssertionError(f"missing bead {bead_id}")


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
    error: Exception | None = None,
) -> tuple[PlannerService, FakePi]:
    config = PurserConfig(root=tmp_path)
    prompts_dir = tmp_path / ".purser/prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "planner.md").write_text("planner", encoding="utf-8")
    config.roles.planner_prompt = ".purser/prompts/planner.md"
    config.loop.human_approve_plan = human_approve_plan
    service = PlannerService(config)
    fake_pi = FakePi(final_text=final_text, error=error)
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


def test_plan_spec_requires_explicit_approval_when_enabled(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path, human_approve_plan=True)
    spec = tmp_path / "spec.md"
    spec.write_text("original", encoding="utf-8")
    cast(Any, service).beads = FakeBeads([[], [make_bead("bd-1", spec_id=str(spec))]])

    with pytest.raises(RuntimeError) as exc:
        service.plan_spec(spec)

    assert "planning approval is required before bead generation" in str(exc.value)
    assert "approve-plan" in str(exc.value)


def test_plan_spec_message_includes_human_approval_when_enabled_after_approval(
    tmp_path: Path,
) -> None:
    service, fake_pi = make_service(
        tmp_path, human_approve_plan=True, final_text=planner_payload(["bd-1"])
    )
    spec = tmp_path / "spec.md"
    spec.write_text("original", encoding="utf-8")
    cast(Any, service).beads = FakeBeads([[], [make_bead("bd-1", spec_id=str(spec))]])
    service.approve_plan(spec)

    service.plan_spec(spec)

    artifact_files = sorted((tmp_path / ".purser" / "runs").glob("*.json"))
    assert artifact_files
    artifact = json.loads(artifact_files[-1].read_text(encoding="utf-8"))
    assert artifact["kind"] == "planner"
    assert artifact["spec_path"] == str(spec)
    assert artifact["structured_outcome"]["created_beads"] == ["bd-1"]
    assert artifact["extra"]["created_bead_ids"] == ["bd-1"]

    assert (
        "Director (human driver) review/approval is required before generating the bead graph"
        in fake_pi.calls[0]["message"]
    )
    assert "must actually create the beads" in fake_pi.calls[0]["message"]
    assert fake_pi.calls[0]["tools"] == "read,bash,grep,find,ls"
    assert "Every created bead must include --spec-id" in fake_pi.calls[0]["message"]
    assert "Preserve exact literals from the spec" in fake_pi.calls[0]["message"]


def test_plan_spec_message_includes_autonomous_note_when_disabled(
    tmp_path: Path,
) -> None:
    service, fake_pi = make_service(
        tmp_path, human_approve_plan=False, final_text=planner_payload(["bd-1"])
    )
    spec = tmp_path / "spec.md"
    spec.write_text("original", encoding="utf-8")
    cast(Any, service).beads = FakeBeads([[], [make_bead("bd-1", spec_id=str(spec))]])

    service.plan_spec(spec)

    assert (
        "Human approval is disabled; proceed with autonomous planning."
        in fake_pi.calls[0]["message"]
    )


def test_plan_spec_raises_if_no_beads_created(tmp_path: Path) -> None:
    service, _ = make_service(
        tmp_path,
        human_approve_plan=False,
        final_text=planner_payload([], summary="Only prose, no mutations"),
    )
    cast(Any, service).beads = FakeBeads([[], []])
    spec = tmp_path / "spec.md"
    spec.write_text("original", encoding="utf-8")

    with pytest.raises(RuntimeError) as exc:
        service.plan_spec(spec)

    assert "did not create any beads" in str(exc.value)
    assert "Only prose, no mutations" in str(exc.value)


def test_plan_spec_raises_if_planner_payload_is_missing_or_invalid(
    tmp_path: Path,
) -> None:
    service, _ = make_service(
        tmp_path, human_approve_plan=False, final_text="Only prose"
    )
    cast(Any, service).beads = FakeBeads(
        [[], [make_bead("bd-1", spec_id=str(tmp_path / "spec.md"))]]
    )
    spec = tmp_path / "spec.md"
    spec.write_text("original", encoding="utf-8")

    with pytest.raises(RuntimeError) as exc:
        service.plan_spec(spec)

    assert "structured outcome payload" in str(exc.value)
    artifact_files = sorted((tmp_path / ".purser" / "runs").glob("*.json"))
    assert artifact_files
    artifact = json.loads(artifact_files[-1].read_text(encoding="utf-8"))
    assert artifact["kind"] == "planner"
    assert artifact["structured_outcome"] is None
    assert artifact["errors"]


def test_plan_spec_raises_if_structured_payload_disagrees_with_created_beads(
    tmp_path: Path,
) -> None:
    service, _ = make_service(
        tmp_path, human_approve_plan=False, final_text=planner_payload(["bd-999"])
    )
    spec = tmp_path / "spec.md"
    spec.write_text("original", encoding="utf-8")
    cast(Any, service).beads = FakeBeads([[], [make_bead("bd-1", spec_id=str(spec))]])

    with pytest.raises(RuntimeError) as exc:
        service.plan_spec(spec)

    assert "did not match actual created beads" in str(exc.value)


def test_plan_spec_tags_created_beads_with_stable_planner_metadata(
    tmp_path: Path,
) -> None:
    service, _ = make_service(
        tmp_path, human_approve_plan=False, final_text=planner_payload(["bd-1"])
    )
    spec = tmp_path / "spec.md"
    spec.write_text("original", encoding="utf-8")
    bead = make_bead("bd-1", spec_id=str(spec))
    fake_beads = FakeBeads([[], [bead]])
    cast(Any, service).beads = fake_beads

    service.plan_spec(spec)

    metadata = bead.metadata
    assert metadata["purser_planner_run_id"].startswith("plan-")
    assert metadata["purser_spec_hash"]
    assert metadata["purser_spec_path"] == str(spec)
    assert ("bd-1", "purser_planner_run_id", metadata["purser_planner_run_id"]) in fake_beads.metadata_updates
    artifact = json.loads(
        sorted((tmp_path / ".purser" / "runs").glob("*.json"))[-1].read_text(
            encoding="utf-8"
        )
    )
    assert artifact["extra"]["planner_run_id"] == metadata["purser_planner_run_id"]
    assert artifact["extra"]["planning_state"] == "complete"


def test_plan_spec_timeout_records_partial_creation_for_retry(
    tmp_path: Path,
) -> None:
    timeout = RoleExecutionError("pi timed out for role planner after 1s")
    service, fake_pi = make_service(
        tmp_path, human_approve_plan=False, error=timeout
    )
    spec = tmp_path / "spec.md"
    spec.write_text("original", encoding="utf-8")
    bead = make_bead("bd-1", spec_id=str(spec))
    fake_beads = FakeBeads([[], [bead]])
    cast(Any, service).beads = fake_beads

    with pytest.raises(RuntimeError) as exc:
        service.plan_spec(spec)

    assert "partial bead creation" in str(exc.value)
    assert "bd-1" in str(exc.value)
    assert len(fake_pi.calls) == 1
    assert bead.metadata["purser_planner_run_id"].startswith("plan-")
    artifact = json.loads(
        sorted((tmp_path / ".purser" / "runs").glob("*.json"))[-1].read_text(
            encoding="utf-8"
        )
    )
    assert artifact["extra"]["planning_state"] == "partial"
    assert artifact["extra"]["created_bead_ids"] == ["bd-1"]


def test_plan_spec_retry_reuses_existing_planner_metadata_without_duplication(
    tmp_path: Path,
) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text("original", encoding="utf-8")
    service, fake_pi = make_service(
        tmp_path, human_approve_plan=False, final_text=planner_payload(["bd-new"])
    )
    identity = service._planner_run_identity(spec)
    bead = make_bead("bd-1", spec_id=str(spec))
    bead.raw["metadata"] = {
        "purser_planner_run_id": identity.run_id,
        "purser_spec_hash": identity.spec_hash,
        "purser_spec_path": str(spec),
    }
    cast(Any, service).beads = FakeBeads([[bead]])

    result = service.plan_spec(spec)

    assert fake_pi.calls == []
    assert "Planning already exists" in result.final_text
    assert service.planned_beads_for_spec(spec)[0].id == "bd-1"
    artifact = json.loads(
        sorted((tmp_path / ".purser" / "runs").glob("*.json"))[-1].read_text(
            encoding="utf-8"
        )
    )
    assert artifact["extra"]["planning_state"] == "complete_existing"
    assert artifact["extra"]["created_bead_ids"] == ["bd-1"]


def test_planner_prompt_file_must_exist(tmp_path: Path) -> None:
    config = PurserConfig(root=tmp_path)
    config.roles.planner_prompt = ".purser/prompts/planner.md"
    service = PlannerService(config)

    with pytest.raises(FileNotFoundError):
        service.intake_spec(Path("spec.md"), synthesize=False)
