"""Tests for scripts/gh_remote.py — GitHub remote detection and creation."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import gh_remote


class TestParseGithubUrl:
    def test_ssh_url(self):
        result = gh_remote._parse_github_url("git@github.com:owner/repo.git")
        assert result == ("github.com", "owner", "repo")

    def test_ssh_url_no_git_suffix(self):
        result = gh_remote._parse_github_url("git@github.com:owner/repo")
        assert result == ("github.com", "owner", "repo")

    def test_https_url(self):
        result = gh_remote._parse_github_url("https://github.com/owner/repo.git")
        assert result == ("github.com", "owner", "repo")

    def test_https_url_no_git_suffix(self):
        result = gh_remote._parse_github_url("https://github.com/owner/repo")
        assert result == ("github.com", "owner", "repo")

    def test_ssh_protocol_url(self):
        result = gh_remote._parse_github_url("ssh://git@github.com/owner/repo.git")
        assert result == ("github.com", "owner", "repo")

    def test_ghe_ssh_url(self):
        result = gh_remote._parse_github_url("git@github.corp.example.com:org/project.git")
        assert result == ("github.corp.example.com", "org", "project")

    def test_ghe_https_url(self):
        result = gh_remote._parse_github_url("https://github.wellsfargo.com/team/app.git")
        assert result == ("github.wellsfargo.com", "team", "app")

    def test_gitlab_url_parses(self):
        """Host-agnostic parsing works for any git hosting provider."""
        result = gh_remote._parse_github_url("git@gitlab.com:owner/repo.git")
        assert result == ("gitlab.com", "owner", "repo")

    def test_empty_string_returns_none(self):
        result = gh_remote._parse_github_url("")
        assert result is None

    def test_trailing_whitespace(self):
        result = gh_remote._parse_github_url("  https://github.com/owner/repo.git  ")
        assert result == ("github.com", "owner", "repo")

    def test_trailing_slash(self):
        result = gh_remote._parse_github_url("https://github.com/owner/repo/")
        assert result == ("github.com", "owner", "repo")


class TestDetectGithubRemotes:
    @patch("gh_remote._run")
    def test_finds_github_remotes(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            [],
            0,
            stdout="origin\tgit@github.com:myorg/myrepo.git (fetch)\n"
            "origin\tgit@github.com:myorg/myrepo.git (push)\n",
            stderr="",
        )
        remotes = gh_remote.detect_github_remotes()
        assert len(remotes) == 1
        assert remotes[0]["name"] == "origin"
        assert remotes[0]["host"] == "github.com"
        assert remotes[0]["owner"] == "myorg"
        assert remotes[0]["repo"] == "myrepo"

    @patch("gh_remote._run")
    def test_multiple_remotes(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            [],
            0,
            stdout="origin\tgit@github.com:org1/repo1.git (fetch)\n"
            "origin\tgit@github.com:org1/repo1.git (push)\n"
            "upstream\thttps://github.com/org2/repo2.git (fetch)\n"
            "upstream\thttps://github.com/org2/repo2.git (push)\n",
            stderr="",
        )
        remotes = gh_remote.detect_github_remotes()
        assert len(remotes) == 2
        names = {r["name"] for r in remotes}
        assert "origin" in names
        assert "upstream" in names

    @patch("gh_remote._run")
    def test_detects_any_git_host(self, mock_run):
        """Host-agnostic parsing detects remotes on any git hosting provider."""
        mock_run.return_value = subprocess.CompletedProcess(
            [],
            0,
            stdout="origin\tgit@gitlab.com:org/repo.git (fetch)\n"
            "origin\tgit@gitlab.com:org/repo.git (push)\n",
            stderr="",
        )
        remotes = gh_remote.detect_github_remotes()
        assert len(remotes) == 1
        assert remotes[0]["host"] == "gitlab.com"

    @patch("gh_remote._run")
    def test_handles_no_remotes(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        remotes = gh_remote.detect_github_remotes()
        assert len(remotes) == 0

    @patch("gh_remote._run")
    def test_handles_git_failure(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            [], 128, stdout="", stderr="not a git repo"
        )
        remotes = gh_remote.detect_github_remotes()
        assert len(remotes) == 0


class TestDetectGithubRemotesGetUrlFallback:
    """Tests for the git remote get-url fallback (insteadOf rewrites)."""

    @patch("gh_remote._run")
    def test_resolves_insteadof_rewrite(self, mock_run):
        """When raw URL isn't GitHub but resolved URL is, detect it."""

        def side_effect(cmd, **kwargs):
            if cmd == ["git", "remote", "-v"]:
                return subprocess.CompletedProcess(
                    [],
                    0,
                    stdout="origin\tgh:myorg/myrepo (fetch)\norigin\tgh:myorg/myrepo (push)\n",
                    stderr="",
                )
            if cmd == ["git", "remote", "get-url", "origin"]:
                return subprocess.CompletedProcess(
                    [],
                    0,
                    stdout="git@github.com:myorg/myrepo.git\n",
                    stderr="",
                )
            return subprocess.CompletedProcess([], 1, stdout="", stderr="")

        mock_run.side_effect = side_effect
        remotes = gh_remote.detect_github_remotes()
        assert len(remotes) == 1
        assert remotes[0]["host"] == "github.com"
        assert remotes[0]["owner"] == "myorg"
        assert remotes[0]["repo"] == "myrepo"
        assert remotes[0]["url"] == "git@github.com:myorg/myrepo.git"

    @patch("gh_remote._run")
    def test_get_url_failure_skips(self, mock_run):
        """If get-url also fails, the remote is skipped."""

        def side_effect(cmd, **kwargs):
            if cmd == ["git", "remote", "-v"]:
                return subprocess.CompletedProcess(
                    [],
                    0,
                    stdout="origin\tgh:myorg/myrepo (fetch)\n",
                    stderr="",
                )
            # get-url fails too
            return subprocess.CompletedProcess([], 1, stdout="", stderr="error")

        mock_run.side_effect = side_effect
        remotes = gh_remote.detect_github_remotes()
        assert len(remotes) == 0


class TestDetectViaGhCli:
    @patch("gh_remote._has_gh", return_value=True)
    @patch("gh_remote._run")
    def test_detects_repo_from_gh(self, mock_run, _):
        mock_run.return_value = subprocess.CompletedProcess(
            [],
            0,
            stdout='{"owner":{"login":"myorg"},"name":"myrepo","url":"https://github.com/myorg/myrepo"}',
            stderr="",
        )
        result = gh_remote._detect_via_gh_cli()
        assert result is not None
        assert result["host"] == "github.com"
        assert result["owner"] == "myorg"
        assert result["repo"] == "myrepo"

    @patch("gh_remote._has_gh", return_value=True)
    @patch("gh_remote._run")
    def test_detects_ghe_repo(self, mock_run, _):
        mock_run.return_value = subprocess.CompletedProcess(
            [],
            0,
            stdout='{"owner":{"login":"team"},"name":"app",'
            '"url":"https://github.corp.example.com/team/app"}',
            stderr="",
        )
        result = gh_remote._detect_via_gh_cli()
        assert result is not None
        assert result["host"] == "github.corp.example.com"
        assert result["owner"] == "team"

    @patch("gh_remote._has_gh", return_value=False)
    def test_returns_none_without_gh(self, _):
        assert gh_remote._detect_via_gh_cli() is None

    @patch("gh_remote._has_gh", return_value=True)
    @patch("gh_remote._run")
    def test_returns_none_on_failure(self, mock_run, _):
        mock_run.return_value = subprocess.CompletedProcess(
            [], 1, stdout="", stderr="not a github repo"
        )
        assert gh_remote._detect_via_gh_cli() is None

    @patch("gh_remote._has_gh", return_value=True)
    @patch("gh_remote._run")
    def test_returns_none_on_bad_json(self, mock_run, _):
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="not json", stderr="")
        assert gh_remote._detect_via_gh_cli() is None


class TestDetectOrCreateGhFallback:
    @patch("gh_remote._detect_via_gh_cli")
    @patch("gh_remote.validate_remote", return_value=True)
    @patch("gh_remote.detect_github_remotes", return_value=[])
    def test_uses_gh_fallback_when_no_remotes(self, mock_detect, mock_validate, mock_gh):
        mock_gh.return_value = {
            "name": "origin",
            "url": "https://github.com/org/repo",
            "owner": "org",
            "repo": "repo",
        }
        result = gh_remote.detect_or_create(Path("/tmp/fake"))
        assert result["status"] == "found"
        assert result["remote"]["owner"] == "org"

    @patch("gh_remote._detect_via_gh_cli", return_value=None)
    @patch("gh_remote.detect_github_remotes", return_value=[])
    def test_falls_through_when_gh_fails(self, mock_detect, mock_gh):
        result = gh_remote.detect_or_create(Path("/tmp/fake"), check_only=True)
        assert result["status"] == "skipped"


class TestPromptMenu:
    @patch("builtins.input", return_value="1")
    def test_select_first(self, _):
        result = gh_remote._prompt_menu(["A", "B", "C"])
        assert result == 0

    @patch("builtins.input", return_value="2")
    def test_select_second(self, _):
        result = gh_remote._prompt_menu(["A", "B", "C"])
        assert result == 1

    @patch("builtins.input", return_value="")
    def test_default_is_first(self, _):
        result = gh_remote._prompt_menu(["A", "B"])
        assert result == 0

    @patch("builtins.input", return_value="99")
    def test_invalid_returns_none(self, _):
        result = gh_remote._prompt_menu(["A", "B"])
        assert result is None

    @patch("builtins.input", side_effect=EOFError)
    def test_eof_returns_none(self, _):
        assert gh_remote._prompt_menu(["A"]) is None


class TestPromptOwnerRepo:
    @patch("builtins.input", return_value="myorg/myrepo")
    def test_valid_slug(self, _):
        result = gh_remote._prompt_owner_repo()
        assert result == ("myorg", "myrepo")

    @patch("builtins.input", return_value="noslash")
    def test_no_slash_returns_none(self, _):
        assert gh_remote._prompt_owner_repo() is None

    @patch("builtins.input", return_value="/repo")
    def test_empty_owner_returns_none(self, _):
        assert gh_remote._prompt_owner_repo() is None

    @patch("builtins.input", side_effect=EOFError)
    def test_eof_returns_none(self, _):
        assert gh_remote._prompt_owner_repo() is None


class TestConnectExisting:
    @patch("gh_remote._run")
    @patch("gh_remote.validate_remote", return_value=True)
    def test_adds_remote_when_not_exists(self, _, mock_run):
        # get-url fails (remote doesn't exist), then add succeeds
        mock_run.side_effect = [
            subprocess.CompletedProcess([], 1, stdout="", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        ]
        result = gh_remote.connect_existing("org", "repo")
        assert result is not None
        assert result["owner"] == "org"
        assert result["host"] == "github.com"
        assert result["url"] == "git@github.com:org/repo.git"

    @patch("gh_remote._run")
    @patch("gh_remote.validate_remote", return_value=True)
    def test_uses_custom_host(self, _, mock_run):
        mock_run.side_effect = [
            subprocess.CompletedProcess([], 1, stdout="", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        ]
        result = gh_remote.connect_existing("team", "app", host="github.corp.example.com")
        assert result is not None
        assert result["host"] == "github.corp.example.com"
        assert result["url"] == "git@github.corp.example.com:team/app.git"

    @patch("gh_remote._run")
    @patch("gh_remote.validate_remote", return_value=True)
    def test_updates_url_when_remote_exists(self, _, mock_run):
        # get-url succeeds (remote exists), then set-url succeeds
        mock_run.side_effect = [
            subprocess.CompletedProcess([], 0, stdout="old-url\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        ]
        result = gh_remote.connect_existing("org", "repo")
        assert result is not None

    @patch("gh_remote.validate_remote", return_value=False)
    def test_returns_none_if_validation_fails(self, _):
        assert gh_remote.connect_existing("bad", "repo") is None


class TestDetectOrCreateMenu:
    @patch("gh_remote._prompt_new_branch", return_value=None)
    @patch("gh_remote.connect_existing")
    @patch("gh_remote._prompt_owner_repo", return_value=("org", "repo"))
    @patch("gh_remote._prompt_menu", return_value=0)
    @patch("gh_remote._has_gh", return_value=True)
    @patch("gh_remote._detect_via_gh_cli", return_value=None)
    @patch("gh_remote.detect_github_remotes", return_value=[])
    def test_connect_existing_flow(
        self, _det, _gh_cli, _has_gh, _menu, _owner, mock_connect, _branch
    ):
        mock_connect.return_value = {
            "name": "origin",
            "url": "git@github.com:org/repo.git",
            "owner": "org",
            "repo": "repo",
        }
        result = gh_remote.detect_or_create(Path("/tmp/fake"))
        assert result["status"] == "connected"
        assert result["remote"]["owner"] == "org"

    @patch("gh_remote._prompt_menu", return_value=2)
    @patch("gh_remote._has_gh", return_value=True)
    @patch("gh_remote._detect_via_gh_cli", return_value=None)
    @patch("gh_remote.detect_github_remotes", return_value=[])
    def test_skip_choice(self, _det, _gh_cli, _has_gh, _menu):
        result = gh_remote.detect_or_create(Path("/tmp/fake"))
        assert result["status"] == "declined"

    @patch("gh_remote._prompt_menu", return_value=None)
    @patch("gh_remote._has_gh", return_value=True)
    @patch("gh_remote._detect_via_gh_cli", return_value=None)
    @patch("gh_remote.detect_github_remotes", return_value=[])
    def test_cancelled_menu(self, _det, _gh_cli, _has_gh, _menu):
        result = gh_remote.detect_or_create(Path("/tmp/fake"))
        assert result["status"] == "declined"


class TestSelectRemote:
    def test_prefers_origin(self):
        remotes = [
            {"name": "upstream", "url": "", "owner": "a", "repo": "b"},
            {"name": "origin", "url": "", "owner": "c", "repo": "d"},
        ]
        result = gh_remote.select_remote(remotes)
        assert result["name"] == "origin"

    def test_falls_back_to_first(self):
        remotes = [
            {"name": "upstream", "url": "", "owner": "a", "repo": "b"},
        ]
        result = gh_remote.select_remote(remotes)
        assert result["name"] == "upstream"

    def test_respects_preferred(self):
        remotes = [
            {"name": "origin", "url": "", "owner": "a", "repo": "b"},
            {"name": "mine", "url": "", "owner": "c", "repo": "d"},
        ]
        result = gh_remote.select_remote(remotes, preferred="mine")
        assert result["name"] == "mine"

    def test_empty_returns_none(self):
        assert gh_remote.select_remote([]) is None


class TestDetectOrCreate:
    @patch("gh_remote.validate_remote", return_value=True)
    @patch("gh_remote.detect_github_remotes")
    def test_found_remote(self, mock_detect, mock_validate):
        mock_detect.return_value = [
            {
                "name": "origin",
                "url": "git@github.com:org/repo.git",
                "owner": "org",
                "repo": "repo",
            },
        ]
        result = gh_remote.detect_or_create(Path("/tmp/fake"))
        assert result["status"] == "found"
        assert result["remote"]["owner"] == "org"
        assert result["validated"] is True

    @patch("gh_remote._detect_via_gh_cli", return_value=None)
    @patch("gh_remote.detect_github_remotes", return_value=[])
    @patch("gh_remote._has_gh", return_value=False)
    def test_no_remote_no_gh(self, mock_gh, mock_detect, _):
        result = gh_remote.detect_or_create(Path("/tmp/fake"))
        assert result["status"] == "skipped"
        assert "gh CLI" in result["message"]

    @patch("gh_remote._detect_via_gh_cli", return_value=None)
    @patch("gh_remote.detect_github_remotes", return_value=[])
    def test_check_only_skips(self, mock_detect, _):
        result = gh_remote.detect_or_create(Path("/tmp/fake"), check_only=True)
        assert result["status"] == "skipped"

    @patch("gh_remote._detect_via_gh_cli", return_value=None)
    @patch("gh_remote.config.load_config")
    @patch("gh_remote.detect_github_remotes", return_value=[])
    def test_auto_create_skip(self, mock_detect, mock_config, _):
        mock_config.return_value = {
            "github": {
                "remote": "origin",
                "auto_create": "skip",
                "owner": "",
                "repo": "",
                "project_number": "",
            },
            "labels": {"bootstrap": "false"},
        }
        result = gh_remote.detect_or_create(Path("/tmp/fake"))
        assert result["status"] == "skipped"


class TestJsonOutput:
    @patch("gh_remote.validate_remote", return_value=True)
    @patch("gh_remote.detect_github_remotes")
    def test_result_is_json_serializable(self, mock_detect, mock_validate):
        mock_detect.return_value = [
            {"name": "origin", "url": "u", "owner": "o", "repo": "r"},
        ]
        result = gh_remote.detect_or_create(Path("/tmp/fake"))
        output = json.dumps(result)
        parsed = json.loads(output)
        assert parsed["status"] == "found"
