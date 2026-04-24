from pathlib import Path
import json

import pytest

from purser import cli


def test_dispatch_init_help_smoke() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.dispatch(["init", "--help"])
    assert exc.value.code == 0


def test_cmd_init_writes_config_and_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    code = cli.dispatch(["init"])

    assert code == 0
    assert (tmp_path / ".purser.toml").exists()
    config_text = (tmp_path / ".purser.toml").read_text(encoding="utf-8")
    assert 'language = "unknown"' in config_text
    assert 'lint = ""' in config_text
    assert (tmp_path / ".purser/prompts/roles/planner-role.md").exists()
    assert (tmp_path / ".purser/prompts/roles/executor-role.md").exists()
    assert (tmp_path / ".purser/prompts/roles/reviewer-role.md").exists()
    assert (tmp_path / ".purser/prompts/workflows/purser-add-spec.md").exists()
    assert (tmp_path / ".purser/prompts/workflows/purser-plan.md").exists()
    assert (tmp_path / ".purser/prompts/workflows/purser-build.md").exists()
    assert (tmp_path / ".purser/prompts/workflows/purser-build-all.md").exists()
    assert (tmp_path / ".purser/README.md").exists()
    assert (tmp_path / "specs/.gitkeep").exists()
    settings = json.loads((tmp_path / ".pi/settings.json").read_text(encoding="utf-8"))
    assert settings["prompts"] == ["../.purser/prompts/workflows"]
    config_text = (tmp_path / ".purser.toml").read_text(encoding="utf-8")
    assert '\ndefault_model = "qwen3.5"' not in config_text
    assert '# default_model = "qwen3.5"' in config_text
    assert '# [roles.models]' in config_text
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "## Purser workflow" in agents
    assert "Purser is not the product or primary deliverable" in agents
    gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".beads/" in gitignore
    assert ".purser/" in gitignore
    assert ".purser.toml" in gitignore
    assert "VALIDATION.md" in gitignore
    out = capsys.readouterr().out
    assert "wrote" in out
    assert "next: edit .purser.toml" in out


def test_cmd_init_uses_strict_uv_python_gates_when_repo_signals_are_strong(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='demo'\n\n[dependency-groups]\ndev=['ty','ruff']\n",
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")

    code = cli.dispatch(["init"])

    assert code == 0
    config_text = (tmp_path / ".purser.toml").read_text(encoding="utf-8")
    assert 'language = "python"' in config_text
    assert 'lint = "uv run ruff check . && uv run ruff format --check .' in config_text
    assert 'types = "uv run ty check"' in config_text
    assert 'tests = "uv run pytest -x --tb=short"' in config_text


def test_cmd_init_from_nested_directory_writes_to_repo_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    nested = repo_root / "src/pkg"
    nested.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    monkeypatch.chdir(nested)

    code = cli.dispatch(["init"])

    assert code == 0
    assert (repo_root / ".purser.toml").exists()
    assert (repo_root / ".purser/prompts/roles/planner-role.md").exists()
    assert not (nested / ".purser.toml").exists()


def test_cmd_init_is_idempotent_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    first = cli.dispatch(["init"])
    second = cli.dispatch(["init"])

    assert first == 0
    assert second == 0
    assert (tmp_path / ".purser.toml").exists()
    out = capsys.readouterr().out
    assert "kept" in out


def test_cmd_init_force_overwrites_existing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    cli.dispatch(["init"])
    config_path = tmp_path / ".purser.toml"
    config_path.write_text("[project]\nname='custom'\n", encoding="utf-8")

    code = cli.dispatch(["init", "--force"])

    assert code == 0
    assert "{project_name}" not in config_path.read_text(encoding="utf-8")
    assert 'name = "' in config_path.read_text(encoding="utf-8")


def test_cmd_init_merges_pi_settings_prompts_without_overwriting_other_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    settings_path = tmp_path / ".pi/settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps({"theme": "dark", "prompts": ["../existing"]}, indent=2) + "\n",
        encoding="utf-8",
    )

    code = cli.dispatch(["init"])

    assert code == 0
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["theme"] == "dark"
    assert settings["prompts"] == ["../existing", "../.purser/prompts/workflows"]


def test_cmd_init_migrates_legacy_prompt_layout_and_pi_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    legacy_prompts = tmp_path / ".purser/prompts"
    legacy_prompts.mkdir(parents=True)
    (legacy_prompts / "planner.md").write_text("legacy planner\n", encoding="utf-8")
    (legacy_prompts / "executor.md").write_text("legacy executor\n", encoding="utf-8")
    (legacy_prompts / "reviewer.md").write_text("legacy reviewer\n", encoding="utf-8")
    (tmp_path / ".purser.toml").write_text(
        "[project]\nname='demo'\n\n[roles]\n"
        "planner_prompt='.purser/prompts/planner.md'\n"
        "executor_prompt='.purser/prompts/executor.md'\n"
        "reviewer_prompt='.purser/prompts/reviewer.md'\n",
        encoding="utf-8",
    )
    settings_path = tmp_path / ".pi/settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps({"prompts": ["../.purser/prompts"], "theme": "dark"}, indent=2)
        + "\n",
        encoding="utf-8",
    )

    code = cli.dispatch(["init"])

    assert code == 0
    assert (tmp_path / ".purser/prompts/roles/planner-role.md").read_text(encoding="utf-8") == "legacy planner\n"
    assert (tmp_path / ".purser/prompts/roles/executor-role.md").read_text(encoding="utf-8") == "legacy executor\n"
    assert (tmp_path / ".purser/prompts/roles/reviewer-role.md").read_text(encoding="utf-8") == "legacy reviewer\n"
    config_text = (tmp_path / ".purser.toml").read_text(encoding="utf-8")
    assert ".purser/prompts/planner.md" not in config_text
    assert ".purser/prompts/roles/planner-role.md" in config_text
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["theme"] == "dark"
    assert settings["prompts"] == ["../.purser/prompts/workflows"]
    out = capsys.readouterr().out
    assert "migrated legacy planner prompt" in out
    assert "updated legacy prompt paths" in out


def test_cmd_init_fails_clearly_when_legacy_and_canonical_prompts_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    legacy_prompts = tmp_path / ".purser/prompts"
    canonical_prompts = legacy_prompts / "roles"
    canonical_prompts.mkdir(parents=True)
    legacy_prompts.mkdir(parents=True, exist_ok=True)
    (legacy_prompts / "planner.md").write_text("legacy planner\n", encoding="utf-8")
    (canonical_prompts / "planner-role.md").write_text("new planner\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="legacy prompt migration is unsafe for planner"):
        cli.dispatch(["init"])


def test_cmd_init_upserts_agents_section_without_overwriting_unrelated_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        "# Agent Instructions\n\nKeep this guidance.\n\n"
        "<!-- purser:agents begin -->\nold body\n<!-- purser:agents end -->\n",
        encoding="utf-8",
    )

    code = cli.dispatch(["init"])

    assert code == 0
    text = agents_path.read_text(encoding="utf-8")
    assert "Keep this guidance." in text
    assert "old body" not in text
    assert text.count("<!-- purser:agents begin -->") == 1
    assert text.count("<!-- purser:agents end -->") == 1
    assert "## Purser workflow" in text


def test_cmd_init_appends_gitignore_entries_without_overwriting_existing_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    gitignore_path = tmp_path / ".gitignore"
    gitignore_path.write_text(".venv/\n.purser/\n", encoding="utf-8")

    code = cli.dispatch(["init"])

    assert code == 0
    lines = gitignore_path.read_text(encoding="utf-8").splitlines()
    assert lines == [".venv/", ".purser/", "", ".beads/", ".purser.toml", "VALIDATION.md"]


def test_cmd_approve_plan_writes_repo_local_approval_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    cli.dispatch(["init"])
    capsys.readouterr()
    spec = tmp_path / "specs/demo.md"
    spec.write_text("# Demo\n", encoding="utf-8")

    code = cli.dispatch(["approve-plan", "specs/demo.md"])

    assert code == 0
    out = capsys.readouterr().out.strip()
    approval_path = Path(out)
    assert approval_path.exists()
    assert approval_path.parent.name == "plan-approvals"


def test_cmd_doctor_reports_missing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "collect_binary_statuses", lambda: [])

    code = cli.dispatch(["doctor"])

    assert code == 1
    out = capsys.readouterr().out
    assert "config: error" in out


def test_cmd_doctor_reports_non_local_beads_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".purser.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    monkeypatch.setattr(cli, "collect_binary_statuses", lambda: [])
    monkeypatch.setattr(cli, "prompt_health", lambda root, config: [])
    monkeypatch.setattr(
        cli,
        "ensure_local_beads_context",
        lambda root: (_ for _ in ()).throw(RuntimeError("found dolt_mode=server")),
    )

    code = cli.dispatch(["doctor"])

    assert code == 1
    out = capsys.readouterr().out
    assert "beads_storage: error" in out
    assert "dolt_mode=server" in out


def test_cmd_doctor_warns_when_pi_prompt_integration_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".purser/prompts/roles").mkdir(parents=True)
    for name in ["planner-role.md", "executor-role.md", "reviewer-role.md"]:
        (tmp_path / ".purser/prompts/roles" / name).write_text(name, encoding="utf-8")
    (tmp_path / ".purser/prompts/workflows").mkdir(parents=True)
    (tmp_path / ".purser.toml").write_text(
        "[project]\nname='demo'\n\n[roles]\n"
        "planner_prompt='.purser/prompts/roles/planner-role.md'\n"
        "executor_prompt='.purser/prompts/roles/executor-role.md'\n"
        "reviewer_prompt='.purser/prompts/roles/reviewer-role.md'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "collect_binary_statuses", lambda: [])
    monkeypatch.setattr(
        cli,
        "ensure_local_beads_context",
        lambda root: (_ for _ in ()).throw(RuntimeError("found dolt_mode=server")),
    )

    code = cli.dispatch(["doctor"])

    assert code == 1
    out = capsys.readouterr().out
    assert "pi_prompts: warning" in out
    assert "../.purser/prompts/workflows" in out


def test_cmd_doctor_warns_when_legacy_prompt_layout_is_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".purser/prompts").mkdir(parents=True)
    (tmp_path / ".purser/prompts/planner.md").write_text("legacy planner", encoding="utf-8")
    (tmp_path / ".purser.toml").write_text(
        "[project]\nname='demo'\n\n[roles]\n"
        "planner_prompt='.purser/prompts/planner.md'\n"
        "executor_prompt='.purser/prompts/roles/executor-role.md'\n"
        "reviewer_prompt='.purser/prompts/roles/reviewer-role.md'\n",
        encoding="utf-8",
    )
    (tmp_path / ".purser/prompts/roles").mkdir(parents=True)
    (tmp_path / ".purser/prompts/roles/executor-role.md").write_text("executor", encoding="utf-8")
    (tmp_path / ".purser/prompts/roles/reviewer-role.md").write_text("reviewer", encoding="utf-8")
    (tmp_path / ".purser/prompts/workflows").mkdir(parents=True)
    monkeypatch.setattr(cli, "collect_binary_statuses", lambda: [])
    monkeypatch.setattr(
        cli,
        "ensure_local_beads_context",
        lambda root: (_ for _ in ()).throw(RuntimeError("found dolt_mode=server")),
    )

    code = cli.dispatch(["doctor"])

    assert code == 1
    out = capsys.readouterr().out
    assert "migration: warning (legacy planner prompt detected" in out
    assert "run `purser init`" in out


def test_cmd_doctor_warns_when_model_strings_are_blank(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".purser/prompts/roles").mkdir(parents=True)
    (tmp_path / ".purser/prompts/workflows").mkdir(parents=True)
    (tmp_path / ".pi").mkdir(parents=True)
    for name in ["planner-role.md", "executor-role.md", "reviewer-role.md"]:
        (tmp_path / ".purser/prompts/roles" / name).write_text(name, encoding="utf-8")
    (tmp_path / ".pi/settings.json").write_text(
        json.dumps({"prompts": ["../.purser/prompts/workflows"]}), encoding="utf-8"
    )
    (tmp_path / ".purser.toml").write_text(
        "[project]\nname='demo'\n\n[roles]\n"
        "planner_prompt='.purser/prompts/roles/planner-role.md'\n"
        "executor_prompt='.purser/prompts/roles/executor-role.md'\n"
        "reviewer_prompt='.purser/prompts/roles/reviewer-role.md'\n"
        "default_model='   '\n"
        "\n[roles.models]\nplanner=' '\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "collect_binary_statuses", lambda: [])
    monkeypatch.setattr(
        cli,
        "ensure_local_beads_context",
        lambda root: (_ for _ in ()).throw(RuntimeError("found dolt_mode=server")),
    )

    code = cli.dispatch(["doctor"])

    assert code == 1
    out = capsys.readouterr().out
    assert "models: warning (roles.default_model is blank" in out
    assert "models: warning (roles.models.planner is blank" in out


def test_cmd_doctor_reports_pi_default_model_fallback_when_unpinned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".purser/prompts/roles").mkdir(parents=True)
    (tmp_path / ".purser/prompts/workflows").mkdir(parents=True)
    (tmp_path / ".pi").mkdir(parents=True)
    for name in ["planner-role.md", "executor-role.md", "reviewer-role.md"]:
        (tmp_path / ".purser/prompts/roles" / name).write_text(name, encoding="utf-8")
    (tmp_path / ".pi/settings.json").write_text(
        json.dumps({"prompts": ["../.purser/prompts/workflows"]}), encoding="utf-8"
    )
    (tmp_path / ".purser.toml").write_text(
        "[project]\nname='demo'\n\n[roles]\n"
        "planner_prompt='.purser/prompts/roles/planner-role.md'\n"
        "executor_prompt='.purser/prompts/roles/executor-role.md'\n"
        "reviewer_prompt='.purser/prompts/roles/reviewer-role.md'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "collect_binary_statuses", lambda: [])
    monkeypatch.setattr(
        cli,
        "ensure_local_beads_context",
        lambda root: (_ for _ in ()).throw(RuntimeError("found dolt_mode=server")),
    )

    code = cli.dispatch(["doctor"])

    assert code == 1
    out = capsys.readouterr().out
    assert "models: ok (no repo-pinned models; Purser will use Pi ambient/default model selection)" in out


def test_cmd_doctor_from_nested_directory_uses_repo_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = tmp_path / "repo"
    nested = repo_root / "a/b"
    nested.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    (repo_root / ".purser.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    monkeypatch.chdir(nested)
    monkeypatch.setattr(cli, "collect_binary_statuses", lambda: [])
    monkeypatch.setattr(cli, "prompt_health", lambda root, config: [])
    monkeypatch.setattr(
        cli,
        "ensure_local_beads_context",
        lambda root: (_ for _ in ()).throw(RuntimeError(f"root={root}")),
    )

    code = cli.dispatch(["doctor"])

    assert code == 1
    out = capsys.readouterr().out
    assert f"config: ok ({repo_root / '.purser.toml'})" in out
    assert f"root={repo_root}" in out


def test_main_prints_user_friendly_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli, "dispatch", lambda argv=None: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "error: boom" in err
