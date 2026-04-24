import json
from pathlib import Path
from typing import Any, cast

from purser import cli
from purser.beads import Bead, normalize_status
from purser.config import PurserConfig
from purser.gates import GateResult
from purser.loop import PurserLoop
from purser.roles import RoleResult
from purser.runtime import BeadsContext, BinaryStatus


class SmokeBeads:
    def __init__(self, bead: Bead) -> None:
        self.bead = bead
        self.comments: list[tuple[str, str]] = []

    def show(self, bead_id: str) -> Bead:
        assert bead_id == self.bead.id
        return self.bead

    def ready(self, limit: int = 1) -> list[Bead]:
        return [self.bead] if self.bead.normalized_status == "open" else []

    def list_by_statuses(self, statuses: list[str]) -> list[Bead]:
        wanted = {normalize_status(status) for status in statuses}
        return [self.bead] if self.bead.normalized_status in wanted else []

    def claim(self, bead_id: str) -> Bead:
        assert bead_id == self.bead.id
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
        self.bead.status = status
        return self.bead

    def reopen(self, bead_id: str, reason: str | None = None) -> Bead:
        assert bead_id == self.bead.id
        self.bead.status = "open"
        return self.bead

    def close(self, bead_id: str, reason: str | None = None) -> Bead:
        assert bead_id == self.bead.id
        self.bead.status = "closed"
        return self.bead

    def comment(self, bead_id: str, text: str) -> None:
        self.comments.append((bead_id, text))


class SmokePi:
    def __init__(self, beads: SmokeBeads) -> None:
        self.beads = beads

    def run_role(self, **kwargs):
        role = kwargs["role"]
        if role == "executor":
            self.beads.bead.status = "in_review"
            final_text = (
                "Executor summary.\n\n"
                "```json\n"
                "{\n"
                '  "status": "completed",\n'
                f'  "bead_id": "{self.beads.bead.id}",\n'
                '  "files_touched": ["src/demo.py"],\n'
                '  "new_beads": [],\n'
                '  "ready_for_review": true,\n'
                '  "summary": "executor done"\n'
                "}\n"
                "```\n"
            )
        else:
            self.beads.close(self.beads.bead.id, reason="review passed")
            final_text = (
                "Reviewer summary.\n\n"
                "```json\n"
                "{\n"
                '  "decision": "approve",\n'
                f'  "bead_id": "{self.beads.bead.id}",\n'
                '  "state_transition_performed": true,\n'
                '  "issues": [],\n'
                '  "summary": "reviewer approved"\n'
                "}\n"
                "```\n"
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
            stdout='{"type":"message_end"}\n',
        )


class SmokeGates:
    def run_all(self, bead_id: str):
        return [
            GateResult(
                name="tests",
                command="pytest",
                exit_code=0,
                stdout="ok",
                stderr="",
            )
        ]


def test_smoke_portable_setup_from_nested_dir_then_doctor(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    repo_root = tmp_path / "repo"
    nested = repo_root / "src/pkg"
    nested.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    monkeypatch.chdir(nested)

    init_code = cli.dispatch(["init"])
    assert init_code == 0
    assert (repo_root / ".purser.toml").exists()
    assert (repo_root / ".purser/prompts/roles/planner-role.md").exists()
    assert (repo_root / ".purser/prompts/workflows/purser-build-all.md").exists()
    capsys.readouterr()

    monkeypatch.setattr(
        cli,
        "collect_binary_statuses",
        lambda: [
            BinaryStatus(name="bd", path="/bin/bd", version="1.0.0", ok=True),
            BinaryStatus(name="dolt", path="/bin/dolt", version="1.0.0", ok=True),
            BinaryStatus(name="pi", path="/bin/pi", version="1.0.0", ok=True),
        ],
    )
    monkeypatch.setattr(
        cli,
        "ensure_local_beads_context",
        lambda root: BeadsContext(
            beads_dir=root / ".beads",
            repo_root=root,
            backend="dolt",
            dolt_mode="embedded",
            database="local",
            role=None,
        ),
    )

    doctor_code = cli.dispatch(["doctor"])

    assert doctor_code == 0
    out = capsys.readouterr().out
    assert f"config: ok ({repo_root / '.purser.toml'})" in out
    assert "pi_prompts: ok" in out
    assert "workflow_prompts: ok" in out
    assert "models: ok (no repo-pinned models; Purser will use Pi ambient/default model selection)" in out
    assert "beads_storage: ok" in out


def test_smoke_hardened_runtime_persists_artifacts_and_validation(tmp_path: Path) -> None:
    config = PurserConfig(root=tmp_path)
    prompts_dir = tmp_path / ".purser/prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "executor.md").write_text("executor", encoding="utf-8")
    (prompts_dir / "reviewer.md").write_text("reviewer", encoding="utf-8")
    config.roles.executor_prompt = ".purser/prompts/executor.md"
    config.roles.reviewer_prompt = ".purser/prompts/reviewer.md"

    bead = Bead(
        id="bd-smoke",
        title="Smoke runtime",
        status="open",
        raw={"metadata": {}, "spec_id": "specs/smoke.md"},
    )
    loop = PurserLoop(config)
    beads = SmokeBeads(bead)
    cast(Any, loop).beads = beads
    cast(Any, loop).pi = SmokePi(beads)
    cast(Any, loop).gates = SmokeGates()

    processed = loop.run_once()

    assert processed == "bd-smoke"
    assert beads.bead.normalized_status == "closed"
    validation = (tmp_path / "VALIDATION.md").read_text(encoding="utf-8")
    assert "## bd-smoke — Smoke runtime" in validation
    assert "reviewer approved" in validation

    artifact_files = sorted((tmp_path / ".purser/runs").glob("*.json"))
    assert len(artifact_files) == 2
    artifacts = [json.loads(path.read_text(encoding="utf-8")) for path in artifact_files]
    kinds = {artifact["kind"] for artifact in artifacts}
    assert kinds == {"executor", "reviewer"}
    executor_artifact = next(item for item in artifacts if item["kind"] == "executor")
    reviewer_artifact = next(item for item in artifacts if item["kind"] == "reviewer")
    assert executor_artifact["structured_outcome"]["bead_id"] == "bd-smoke"
    assert executor_artifact["gate_results"][0]["passed"] is True
    assert reviewer_artifact["structured_outcome"]["decision"] == "approve"
    assert reviewer_artifact["extra"]["validation_log_path"] == str(
        tmp_path / "VALIDATION.md"
    )
