"""Tests for scripts/prereqs.py — prerequisite checker."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import prereqs


class TestDetectPlatform:
    @patch("platform.system", return_value="Darwin")
    def test_macos(self, _):
        assert prereqs._detect_platform() == "macos"

    @patch("platform.system", return_value="Windows")
    def test_windows(self, _):
        assert prereqs._detect_platform() == "windows"

    @patch("platform.system", return_value="Linux")
    @patch("shutil.which", side_effect=lambda x: "/usr/bin/apt" if x == "apt" else None)
    def test_linux_apt(self, _, __):
        assert prereqs._detect_platform() == "linux-apt"

    @patch("platform.system", return_value="Linux")
    @patch("shutil.which", return_value=None)
    def test_linux_other(self, _, __):
        assert prereqs._detect_platform() == "linux-other"


class TestGetVersion:
    def test_finds_python(self):
        version = prereqs._get_version("python3", "--version")
        assert version is not None
        assert "Python" in version or "python" in version

    def test_finds_git(self):
        version = prereqs._get_version("git", "--version")
        assert version is not None
        assert "git" in version.lower()

    def test_missing_tool_returns_none(self):
        version = prereqs._get_version("nonexistent_tool_xyz", "--version")
        assert version is None

    def test_accepts_multiple_tokens(self):
        """_get_version should work with >2 args (e.g. py -3 --version)."""
        # Use git as a stand-in: "git --no-pager --version" is valid
        version = prereqs._get_version("git", "--no-pager", "--version")
        assert version is not None


class TestGetPythonVersion:
    def test_finds_python_on_current_platform(self):
        plat = prereqs._detect_platform()
        version = prereqs._get_python_version(plat)
        assert version is not None
        assert "Python" in version or "python" in version

    @patch.object(prereqs, "_get_version", return_value=None)
    def test_returns_none_when_all_fallbacks_fail(self, _mock):
        assert prereqs._get_python_version("linux-apt") is None

    @patch.object(prereqs, "_get_version", side_effect=[None, "Python 3.12.0"])
    def test_falls_back_to_second_candidate(self, mock_gv):
        result = prereqs._get_python_version("linux-apt")
        assert result == "Python 3.12.0"
        # First call: python3 --version (failed), second: python --version
        assert mock_gv.call_count == 2

    @patch.object(prereqs, "_get_version", side_effect=["Python 3.12.0"])
    def test_windows_tries_python_first(self, mock_gv):
        result = prereqs._get_python_version("windows")
        assert result == "Python 3.12.0"
        mock_gv.assert_called_once_with("python", "--version")


class TestCheckPrerequisites:
    def test_returns_required_keys(self):
        result = prereqs.check_prerequisites()
        assert "platform" in result
        assert "all_ok" in result
        assert "tools" in result
        assert isinstance(result["tools"], list)

    def test_each_tool_has_fields(self):
        result = prereqs.check_prerequisites()
        for tool in result["tools"]:
            assert "name" in tool
            assert "description" in tool
            assert "found" in tool
            assert "version" in tool
            assert "install" in tool

    def test_checks_all_required_tools(self):
        result = prereqs.check_prerequisites()
        names = {t["name"] for t in result["tools"]}
        assert "git" in names
        assert "python3" in names
        assert "gh" in names
        assert "bd" in names

    def test_git_and_python_found(self):
        """git and python3 should be available in any dev environment."""
        result = prereqs.check_prerequisites()
        tool_map = {t["name"]: t for t in result["tools"]}
        assert tool_map["git"]["found"] is True
        assert tool_map["python3"]["found"] is True

    def test_install_instructions_present_for_missing(self):
        result = prereqs.check_prerequisites()
        for tool in result["tools"]:
            if not tool["found"]:
                assert tool["install"], f"Missing install instructions for {tool['name']}"


class TestInstallInstructions:
    def test_all_platforms_covered(self):
        for plat in ["macos", "linux-apt", "linux-other", "windows"]:
            assert plat in prereqs.INSTALL_INSTRUCTIONS

    def test_all_tools_have_instructions(self):
        for plat, instructions in prereqs.INSTALL_INSTRUCTIONS.items():
            for command, _, _ in prereqs.REQUIRED_TOOLS:
                assert command in instructions, f"Missing {command} for {plat}"


class TestPrintReport:
    def test_prints_without_error(self, capsys):
        result = prereqs.check_prerequisites()
        prereqs.print_report(result)
        captured = capsys.readouterr()
        assert "Platform:" in captured.out

    def test_shows_ok_for_found_tools(self, capsys):
        result = {
            "platform": "linux-apt",
            "all_ok": True,
            "tools": [{"name": "git", "description": "Git", "found": True,
                       "version": "git 2.43", "install": "apt install git"}],
        }
        prereqs.print_report(result)
        captured = capsys.readouterr()
        assert "[ok]" in captured.out

    def test_shows_missing_with_install(self, capsys):
        result = {
            "platform": "macos",
            "all_ok": False,
            "tools": [{"name": "bd", "description": "Beads CLI", "found": False,
                       "version": None, "install": "npm install -g @beads/bd"}],
        }
        prereqs.print_report(result)
        captured = capsys.readouterr()
        assert "[MISSING]" in captured.out
        assert "npm install" in captured.out


class TestJsonOutput:
    def test_result_is_json_serializable(self):
        result = prereqs.check_prerequisites()
        # Should not raise
        output = json.dumps(result)
        parsed = json.loads(output)
        assert parsed["platform"] == result["platform"]
