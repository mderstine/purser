"""Tests for scripts/gh_project.py — GitHub Projects v2 board management."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import gh_project


class TestCheckProjectScopes:
    """Tests for check_project_scopes() auth hint hostname."""

    def test_uses_default_host_when_no_config(self, tmp_path, capsys):
        """Auth hint defaults to github.com when no config file exists."""
        fake_result = subprocess.CompletedProcess([], returncode=1, stdout="", stderr="error")
        with (
            patch("gh_project.subprocess.run", return_value=fake_result),
            patch("gh_project.config.load_config", return_value={"github": {"host": "github.com"}}),
            pytest.raises(SystemExit),
        ):
            gh_project.check_project_scopes()
        captured = capsys.readouterr()
        assert "gh auth refresh -h github.com" in captured.out

    def test_uses_configured_ghe_host(self, capsys):
        """Auth hint uses the configured GHE hostname."""
        fake_result = subprocess.CompletedProcess([], returncode=1, stdout="", stderr="error")
        with (
            patch("gh_project.subprocess.run", return_value=fake_result),
            patch(
                "gh_project.config.load_config",
                return_value={"github": {"host": "github.wellsfargo.com"}},
            ),
            pytest.raises(SystemExit),
        ):
            gh_project.check_project_scopes()
        captured = capsys.readouterr()
        assert "gh auth refresh -h github.wellsfargo.com" in captured.out

    def test_passes_when_scopes_ok(self):
        """No error when gh API call succeeds."""
        fake_result = subprocess.CompletedProcess([], returncode=0, stdout="{}", stderr="")
        with patch("gh_project.subprocess.run", return_value=fake_result):
            gh_project.check_project_scopes()  # should not raise
