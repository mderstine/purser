"""Tests for scripts/config.py — Ralph-Beads configuration loader."""

import os
import sys
from pathlib import Path

import pytest

# Add scripts/ to path so we can import config
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import config


class TestParseYaml:
    def test_basic_structure(self):
        text = "github:\n  owner: myorg\n  repo: myrepo\n"
        result = config._parse_yaml(text)
        assert result == {"github": {"owner": "myorg", "repo": "myrepo"}}

    def test_multiple_sections(self):
        text = "github:\n  owner: foo\nlabels:\n  bootstrap: true\n"
        result = config._parse_yaml(text)
        assert result["github"]["owner"] == "foo"
        assert result["labels"]["bootstrap"] == "true"

    def test_quoted_values(self):
        text = 'github:\n  owner: "my org"\n  repo: \'my-repo\'\n'
        result = config._parse_yaml(text)
        assert result["github"]["owner"] == "my org"
        assert result["github"]["repo"] == "my-repo"

    def test_comments_ignored(self):
        text = "# top comment\ngithub:\n  # nested comment\n  owner: foo  # inline comment\n"
        result = config._parse_yaml(text)
        assert result == {"github": {"owner": "foo"}}

    def test_blank_lines_ignored(self):
        text = "\ngithub:\n\n  owner: foo\n\n"
        result = config._parse_yaml(text)
        assert result == {"github": {"owner": "foo"}}

    def test_empty_value(self):
        text = "github:\n  owner:\n"
        result = config._parse_yaml(text)
        assert result["github"]["owner"] == ""

    def test_numeric_value(self):
        text = "github:\n  project_number: 42\n"
        result = config._parse_yaml(text)
        assert result["github"]["project_number"] == "42"


class TestSerializeYaml:
    def test_roundtrip(self):
        original = {"github": {"owner": "foo", "repo": "bar"}}
        text = config._serialize_yaml(original)
        parsed = config._parse_yaml(text)
        assert parsed == original

    def test_special_chars_quoted(self):
        data = {"github": {"owner": "foo:bar"}}
        text = config._serialize_yaml(data)
        assert '"foo:bar"' in text


class TestLoadConfig:
    def test_defaults_when_no_file(self, tmp_path):
        result = config.load_config(tmp_path)
        assert result["github"]["remote"] == "origin"
        assert result["github"]["auto_create"] == "prompt"
        assert result["labels"]["bootstrap"] == "false"

    def test_file_overrides_defaults(self, tmp_path):
        cfg_file = tmp_path / ".ralph-beads.yml"
        cfg_file.write_text("github:\n  owner: myorg\n  repo: myrepo\n")
        result = config.load_config(tmp_path)
        assert result["github"]["owner"] == "myorg"
        assert result["github"]["repo"] == "myrepo"
        # Defaults still present for unset keys
        assert result["github"]["remote"] == "origin"

    def test_env_overrides_file(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / ".ralph-beads.yml"
        cfg_file.write_text("github:\n  owner: from-file\n")
        monkeypatch.setenv("RALPH_BEADS_GITHUB_OWNER", "from-env")
        result = config.load_config(tmp_path)
        assert result["github"]["owner"] == "from-env"

    def test_env_overrides_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setenv("RALPH_BEADS_GITHUB_AUTO_CREATE", "skip")
        result = config.load_config(tmp_path)
        assert result["github"]["auto_create"] == "skip"


class TestSaveConfig:
    def test_creates_file(self, tmp_path):
        cfg = {"github": {"owner": "test", "repo": "myrepo"}}
        path = config.save_config(cfg, tmp_path)
        assert path.exists()
        assert path.name == ".ralph-beads.yml"
        content = path.read_text()
        assert "owner: test" in content
        assert "repo: myrepo" in content

    def test_save_then_load(self, tmp_path):
        cfg = {"github": {"owner": "org", "repo": "proj", "remote": "upstream"}}
        config.save_config(cfg, tmp_path)
        loaded = config.load_config(tmp_path)
        assert loaded["github"]["owner"] == "org"
        assert loaded["github"]["repo"] == "proj"
        assert loaded["github"]["remote"] == "upstream"


class TestGet:
    def test_get_existing_value(self, tmp_path):
        cfg_file = tmp_path / ".ralph-beads.yml"
        cfg_file.write_text("github:\n  owner: testorg\n")
        result = config.get("github", "owner", tmp_path)
        assert result == "testorg"

    def test_get_missing_returns_empty(self, tmp_path):
        result = config.get("github", "owner", tmp_path)
        assert result == ""

    def test_get_missing_section_returns_empty(self, tmp_path):
        result = config.get("nonexistent", "key", tmp_path)
        assert result == ""


class TestConfigPath:
    def test_returns_yml_in_root(self, tmp_path):
        path = config.config_path(tmp_path)
        assert path == tmp_path / ".ralph-beads.yml"
