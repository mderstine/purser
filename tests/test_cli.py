from pathlib import Path

import pytest

from purser import cli


def test_dispatch_init_help_smoke() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.dispatch(["init", "--help"])
    assert exc.value.code == 0


def test_cmd_init_writes_config_and_prompts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)

    code = cli.dispatch(["init"])

    assert code == 0
    assert (tmp_path / ".purser.toml").exists()
    assert (tmp_path / ".purser/prompts/planner.md").exists()
    assert (tmp_path / ".purser/prompts/executor.md").exists()
    assert (tmp_path / ".purser/prompts/reviewer.md").exists()
    out = capsys.readouterr().out
    assert "wrote" in out
    assert "next: edit .purser.toml" in out


def test_cmd_init_refuses_overwrite_without_force(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".purser.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        cli.dispatch(["init"])
    assert "Refusing to overwrite existing config" in str(exc.value)


def test_cmd_doctor_reports_missing_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "collect_binary_statuses", lambda: [])

    code = cli.dispatch(["doctor"])

    assert code == 1
    out = capsys.readouterr().out
    assert "config: error" in out


def test_cmd_doctor_reports_non_local_beads_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".purser.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    monkeypatch.setattr(cli, "collect_binary_statuses", lambda: [])
    monkeypatch.setattr(cli, "prompt_health", lambda root, config: [])
    monkeypatch.setattr(cli, "ensure_local_beads_context", lambda root: (_ for _ in ()).throw(RuntimeError("found dolt_mode=server")))

    code = cli.dispatch(["doctor"])

    assert code == 1
    out = capsys.readouterr().out
    assert "beads_storage: error" in out
    assert "dolt_mode=server" in out


def test_main_prints_user_friendly_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli, "dispatch", lambda argv=None: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "error: boom" in err
