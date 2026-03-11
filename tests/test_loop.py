"""Tests for scripts/loop.py — Purser loop orchestrator."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import loop


class TestParseArgs:
    def test_defaults(self):
        mode, max_iter, timeout, batch, agent, passthrough = loop._parse_args([])
        assert mode == "build"
        assert max_iter == 0
        assert timeout == ""
        assert batch is False
        assert agent == "claude"
        assert passthrough == []

    def test_plan_mode(self):
        mode, *_ = loop._parse_args(["plan"])
        assert mode == "plan"

    def test_status_mode(self):
        mode, *_ = loop._parse_args(["status"])
        assert mode == "status"

    def test_sync_mode(self):
        mode, *_ = loop._parse_args(["sync"])
        assert mode == "sync"

    def test_triage_mode(self):
        mode, *_ = loop._parse_args(["triage"])
        assert mode == "triage"

    def test_changelog_mode(self):
        mode, *_ = loop._parse_args(["changelog"])
        assert mode == "changelog"

    def test_max_iterations(self):
        _, max_iter, *_ = loop._parse_args(["20"])
        assert max_iter == 20

    def test_plan_with_max_iterations(self):
        mode, max_iter, *_ = loop._parse_args(["plan", "5"])
        assert mode == "plan"
        assert max_iter == 5

    def test_timeout_override(self):
        _, _, timeout, *_ = loop._parse_args(["--timeout=1800"])
        assert timeout == "1800"

    def test_batch_flag(self):
        _, _, _, batch, *_ = loop._parse_args(["--batch"])
        assert batch is True

    def test_agent_claude(self):
        _, _, _, _, agent, _ = loop._parse_args(["--agent=claude"])
        assert agent == "claude"

    def test_agent_vscode(self):
        _, _, _, _, agent, _ = loop._parse_args(["--agent=vscode"])
        assert agent == "vscode"

    def test_agent_env_var(self, monkeypatch):
        monkeypatch.setenv("PURSER_AGENT", "vscode")
        _, _, _, _, agent, _ = loop._parse_args([])
        assert agent == "vscode"

    def test_agent_flag_overrides_env(self, monkeypatch):
        monkeypatch.setenv("PURSER_AGENT", "vscode")
        _, _, _, _, agent, _ = loop._parse_args(["--agent=claude"])
        assert agent == "claude"

    def test_dry_run_passthrough(self):
        _, _, _, _, _, passthrough = loop._parse_args(["sync", "--dry-run"])
        assert "--dry-run" in passthrough

    def test_combined_args(self):
        mode, max_iter, timeout, batch, agent, passthrough = loop._parse_args(
            ["plan", "10", "--timeout=300", "--dry-run", "--agent=vscode", "--batch"]
        )
        assert mode == "plan"
        assert max_iter == 10
        assert timeout == "300"
        assert batch is True
        assert agent == "vscode"
        assert "--dry-run" in passthrough


class TestRunStatus:
    def test_no_summary_file(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(loop, "REPO_ROOT", tmp_path)
        loop._run_status()
        captured = capsys.readouterr()
        assert "No iteration logs found" in captured.out

    def test_empty_summary(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(loop, "REPO_ROOT", tmp_path)
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "summary.jsonl").write_text("")
        loop._run_status()
        captured = capsys.readouterr()
        assert "No iteration data found" in captured.out

    def test_valid_summary(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(loop, "REPO_ROOT", tmp_path)
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        entry = {
            "iteration": 1,
            "mode": "build",
            "start_time": "2026-03-08T00:00:00",
            "duration_s": 120,
            "exit_code": 0,
            "beads_issue_id": "test-123",
            "outcome": "success",
            "log_file": "logs/build-iter-1.log",
        }
        (logs_dir / "summary.jsonl").write_text(json.dumps(entry) + "\n")
        loop._run_status()
        captured = capsys.readouterr()
        assert "Purser Iteration Stats" in captured.out
        assert "Total iterations:  1" in captured.out
        assert "Success:           1" in captured.out
        assert "100%" in captured.out


class TestGetClosedIssueIds:
    @patch("subprocess.run")
    def test_returns_ids(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"id": "bd-1"}, {"id": "bd-2"}]),
        )
        result = loop._get_closed_issue_ids()
        assert result == {"bd-1", "bd-2"}

    @patch("subprocess.run")
    def test_returns_empty_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        result = loop._get_closed_issue_ids()
        assert result == set()

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_returns_empty_when_bd_missing(self, _):
        result = loop._get_closed_issue_ids()
        assert result == set()


class TestGetReadyCount:
    @patch("subprocess.run")
    def test_returns_count(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"id": "bd-1"}, {"id": "bd-2"}, {"id": "bd-3"}]),
        )
        assert loop._get_ready_count() == 3

    @patch("subprocess.run")
    def test_returns_zero_on_empty(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        assert loop._get_ready_count() == 0

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_returns_zero_when_bd_missing(self, _):
        assert loop._get_ready_count() == 0


class TestPreflightChecks:
    @patch("subprocess.run")
    @patch("shutil.which")
    def test_exits_when_bd_missing(self, mock_which, mock_run):
        mock_which.side_effect = lambda cmd: None if cmd == "bd" else f"/usr/bin/{cmd}"
        with pytest.raises(SystemExit) as exc_info:
            loop._preflight_checks(agent="claude")
        assert exc_info.value.code == 1

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_exits_when_claude_missing(self, mock_which, mock_run):
        mock_which.side_effect = lambda cmd: None if cmd == "claude" else f"/usr/bin/{cmd}"
        with pytest.raises(SystemExit) as exc_info:
            loop._preflight_checks(agent="claude")
        assert exc_info.value.code == 1

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_vscode_agent_does_not_require_claude(self, mock_which, mock_run):
        # claude missing, but agent=vscode — should not error
        mock_which.side_effect = lambda cmd: None if cmd == "claude" else f"/usr/bin/{cmd}"
        mock_run.return_value = MagicMock(returncode=0, stdout="feature\n")
        # Should not raise
        loop._preflight_checks(agent="vscode")

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_vscode_agent_warns_when_code_cli_missing(self, mock_which, mock_run, caplog):
        # Both claude and code are missing, but we're in vscode mode
        missing = {"claude", "code"}
        mock_which.side_effect = lambda cmd: None if cmd in missing else f"/usr/bin/{cmd}"
        mock_run.return_value = MagicMock(returncode=0, stdout="feature\n")
        loop._preflight_checks(agent="vscode")
        assert "code" in caplog.text.lower() or "VS Code" in caplog.text

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_exits_on_unknown_agent(self, mock_which, mock_run):
        mock_which.return_value = "/usr/bin/tool"
        with pytest.raises(SystemExit) as exc_info:
            loop._preflight_checks(agent="unknown-agent")
        assert exc_info.value.code == 1

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/tool")
    def test_exits_when_bd_prime_fails(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        with pytest.raises(SystemExit) as exc_info:
            loop._preflight_checks(agent="claude")
        assert exc_info.value.code == 1

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/tool")
    def test_passes_when_all_ok(self, mock_which, mock_run, capsys):
        # bd prime succeeds, git branch returns "feature", no uncommitted changes
        def run_side_effect(cmd, **kwargs):
            if cmd == ["bd", "prime"]:
                return MagicMock(returncode=0)
            if cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return MagicMock(returncode=0, stdout="feature-branch\n")
            if cmd[0] == "git" and "--quiet" in cmd:
                return MagicMock(returncode=0)
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = run_side_effect
        # Should not raise
        loop._preflight_checks(agent="claude")

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/tool")
    def test_warns_on_main_branch(self, mock_which, mock_run, caplog):
        def run_side_effect(cmd, **kwargs):
            if cmd == ["bd", "prime"]:
                return MagicMock(returncode=0)
            if cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return MagicMock(returncode=0, stdout="main\n")
            return MagicMock(returncode=0)

        mock_run.side_effect = run_side_effect
        loop._preflight_checks(agent="claude")
        assert "WARNING" in caplog.text
        assert "main" in caplog.text


class TestMainExitsOnNoPromptFile:
    @patch("shutil.which", return_value="/usr/bin/tool")
    @patch("subprocess.run")
    def test_exits_when_prompt_file_missing(self, mock_run, mock_which, tmp_path, monkeypatch):
        monkeypatch.setattr(loop, "REPO_ROOT", tmp_path)
        # Mock preflight to pass
        monkeypatch.setattr(loop, "_preflight_checks", lambda **kwargs: None)
        with pytest.raises(SystemExit) as exc_info:
            loop.main(["build"])
        assert exc_info.value.code == 1
