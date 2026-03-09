"""Tests for scripts/gh_project_setup.py — GitHub Projects detection and setup."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import gh_project_setup


class TestListProjects:
    @patch("gh_project_setup._gql")
    def test_returns_projects(self, mock_gql):
        mock_gql.return_value = {
            "data": {
                "repository": {
                    "projectsV2": {
                        "nodes": [
                            {"id": "PVT_1", "title": "Board", "number": 1, "url": "https://..."},
                        ]
                    }
                }
            }
        }
        projects = gh_project_setup.list_projects("owner", "repo")
        assert len(projects) == 1
        assert projects[0]["title"] == "Board"
        assert projects[0]["number"] == 1

    @patch("gh_project_setup._gql")
    def test_returns_empty_on_failure(self, mock_gql):
        mock_gql.return_value = None
        projects = gh_project_setup.list_projects("owner", "repo")
        assert projects == []

    @patch("gh_project_setup._gql")
    def test_returns_empty_on_no_projects(self, mock_gql):
        mock_gql.return_value = {
            "data": {"repository": {"projectsV2": {"nodes": []}}}
        }
        projects = gh_project_setup.list_projects("owner", "repo")
        assert projects == []


class TestDetectOrSetup:
    @patch("gh_project_setup._has_gh", return_value=False)
    def test_no_gh_skips(self, _):
        result = gh_project_setup.detect_or_setup("owner", "repo", check_only=True)
        assert result["status"] == "skipped"
        assert "gh CLI" in result["message"]

    @patch("gh_project_setup._has_gh", return_value=True)
    def test_no_owner_skips(self, _):
        result = gh_project_setup.detect_or_setup("", "", check_only=True)
        assert result["status"] == "skipped"
        assert "No GitHub remote" in result["message"]

    @patch("gh_project_setup._has_gh", return_value=True)
    @patch("gh_project_setup.list_projects")
    @patch("gh_project_setup.config.load_config")
    def test_single_project_check_only(self, mock_cfg, mock_list, _):
        mock_cfg.return_value = {
            "github": {"remote": "origin", "owner": "o", "repo": "r", "auto_create": "prompt", "project_number": ""},
            "labels": {"bootstrap": "false"},
        }
        mock_list.return_value = [
            {"id": "PVT_1", "title": "My Board", "number": 3, "url": "https://..."},
        ]
        result = gh_project_setup.detect_or_setup("o", "r", check_only=True)
        assert result["status"] == "found"
        assert result["project"]["number"] == 3

    @patch("gh_project_setup._has_gh", return_value=True)
    @patch("gh_project_setup.list_projects")
    @patch("gh_project_setup.config.load_config")
    def test_multiple_projects_check_only_returns_first(self, mock_cfg, mock_list, _):
        mock_cfg.return_value = {
            "github": {"remote": "origin", "owner": "o", "repo": "r", "auto_create": "prompt", "project_number": ""},
            "labels": {"bootstrap": "false"},
        }
        mock_list.return_value = [
            {"id": "PVT_1", "title": "Board A", "number": 1, "url": ""},
            {"id": "PVT_2", "title": "Board B", "number": 2, "url": ""},
        ]
        result = gh_project_setup.detect_or_setup("o", "r", check_only=True)
        assert result["status"] == "found"
        assert result["project"]["title"] == "Board A"

    @patch("gh_project_setup._has_gh", return_value=True)
    @patch("gh_project_setup.list_projects", return_value=[])
    @patch("gh_project_setup.config.load_config")
    def test_no_projects_check_only(self, mock_cfg, mock_list, _):
        mock_cfg.return_value = {
            "github": {"remote": "origin", "owner": "o", "repo": "r", "auto_create": "prompt", "project_number": ""},
            "labels": {"bootstrap": "false"},
        }
        result = gh_project_setup.detect_or_setup("o", "r", check_only=True)
        assert result["status"] == "skipped"

    @patch("gh_project_setup._has_gh", return_value=True)
    @patch("gh_project_setup.list_projects")
    @patch("gh_project_setup.config.load_config")
    def test_configured_project_number(self, mock_cfg, mock_list, _):
        mock_cfg.return_value = {
            "github": {"remote": "origin", "owner": "o", "repo": "r", "auto_create": "prompt", "project_number": "5"},
            "labels": {"bootstrap": "false"},
        }
        mock_list.return_value = [
            {"id": "PVT_1", "title": "Board A", "number": 3, "url": ""},
            {"id": "PVT_2", "title": "Board B", "number": 5, "url": ""},
        ]
        result = gh_project_setup.detect_or_setup("o", "r", check_only=True)
        assert result["status"] == "found"
        assert result["project"]["number"] == 5


class TestJsonOutput:
    @patch("gh_project_setup._has_gh", return_value=True)
    @patch("gh_project_setup.list_projects")
    @patch("gh_project_setup.config.load_config")
    def test_result_is_json_serializable(self, mock_cfg, mock_list, _):
        mock_cfg.return_value = {
            "github": {"remote": "origin", "owner": "o", "repo": "r", "auto_create": "prompt", "project_number": ""},
            "labels": {"bootstrap": "false"},
        }
        mock_list.return_value = [
            {"id": "PVT_1", "title": "Board", "number": 1, "url": "https://..."},
        ]
        result = gh_project_setup.detect_or_setup("o", "r", check_only=True)
        output = json.dumps(result)
        parsed = json.loads(output)
        assert parsed["status"] == "found"


class TestPromptSelect:
    @patch("builtins.input", return_value="2")
    def test_selects_second_project(self, _):
        projects = [
            {"id": "PVT_1", "title": "A", "number": 1, "url": ""},
            {"id": "PVT_2", "title": "B", "number": 2, "url": ""},
        ]
        result = gh_project_setup._prompt_select(projects)
        assert result["title"] == "B"

    @patch("builtins.input", return_value="0")
    def test_skip_selection(self, _):
        projects = [{"id": "PVT_1", "title": "A", "number": 1, "url": ""}]
        result = gh_project_setup._prompt_select(projects)
        assert result is None

    @patch("builtins.input", return_value="")
    def test_default_is_first(self, _):
        projects = [
            {"id": "PVT_1", "title": "A", "number": 1, "url": ""},
            {"id": "PVT_2", "title": "B", "number": 2, "url": ""},
        ]
        result = gh_project_setup._prompt_select(projects)
        assert result["title"] == "A"

    @patch("builtins.input", return_value="99")
    def test_out_of_range_returns_none(self, _):
        projects = [{"id": "PVT_1", "title": "A", "number": 1, "url": ""}]
        result = gh_project_setup._prompt_select(projects)
        assert result is None

    @patch("builtins.input", side_effect=EOFError)
    def test_eof_returns_none(self, _):
        projects = [{"id": "PVT_1", "title": "A", "number": 1, "url": ""}]
        result = gh_project_setup._prompt_select(projects)
        assert result is None


class TestListOwnerProjects:
    @patch("gh_project_setup._gql")
    def test_returns_user_projects(self, mock_gql):
        mock_gql.side_effect = [
            # viewer query
            {
                "data": {
                    "viewer": {
                        "projectsV2": {
                            "nodes": [
                                {"id": "PVT_1", "title": "My Board", "number": 1, "url": ""},
                            ]
                        }
                    }
                }
            },
            # org query — fails (user is not an org)
            None,
        ]
        projects = gh_project_setup.list_owner_projects("myuser")
        assert len(projects) == 1
        assert projects[0]["title"] == "My Board"

    @patch("gh_project_setup._gql")
    def test_merges_org_projects(self, mock_gql):
        mock_gql.side_effect = [
            # viewer query
            {
                "data": {
                    "viewer": {
                        "projectsV2": {
                            "nodes": [
                                {"id": "PVT_1", "title": "Personal", "number": 1, "url": ""},
                            ]
                        }
                    }
                }
            },
            # org query
            {
                "data": {
                    "organization": {
                        "projectsV2": {
                            "nodes": [
                                {"id": "PVT_2", "title": "Org Board", "number": 2, "url": ""},
                            ]
                        }
                    }
                }
            },
        ]
        projects = gh_project_setup.list_owner_projects("myorg")
        assert len(projects) == 2
        titles = {p["title"] for p in projects}
        assert titles == {"Personal", "Org Board"}

    @patch("gh_project_setup._gql")
    def test_deduplicates_by_id(self, mock_gql):
        mock_gql.side_effect = [
            {
                "data": {
                    "viewer": {
                        "projectsV2": {
                            "nodes": [
                                {"id": "PVT_1", "title": "Shared", "number": 1, "url": ""},
                            ]
                        }
                    }
                }
            },
            {
                "data": {
                    "organization": {
                        "projectsV2": {
                            "nodes": [
                                {"id": "PVT_1", "title": "Shared", "number": 1, "url": ""},
                            ]
                        }
                    }
                }
            },
        ]
        projects = gh_project_setup.list_owner_projects("myorg")
        assert len(projects) == 1

    @patch("gh_project_setup._gql")
    def test_returns_empty_on_total_failure(self, mock_gql):
        mock_gql.return_value = None
        projects = gh_project_setup.list_owner_projects("owner")
        assert projects == []


class TestLinkProjectToRepo:
    @patch("gh_project_setup._gql")
    @patch("gh_project_setup._get_repo_id", return_value="R_123")
    def test_success(self, mock_repo_id, mock_gql):
        mock_gql.return_value = {
            "data": {
                "linkProjectV2ToRepository": {
                    "repository": {"nameWithOwner": "owner/repo"}
                }
            }
        }
        result = gh_project_setup.link_project_to_repo("PVT_1", "owner", "repo")
        assert result is True
        mock_gql.assert_called_once()

    @patch("gh_project_setup._get_repo_id", return_value=None)
    def test_fails_without_repo_id(self, _):
        result = gh_project_setup.link_project_to_repo("PVT_1", "owner", "repo")
        assert result is False

    @patch("gh_project_setup._gql", return_value=None)
    @patch("gh_project_setup._get_repo_id", return_value="R_123")
    def test_fails_on_mutation_error(self, _, __):
        result = gh_project_setup.link_project_to_repo("PVT_1", "owner", "repo")
        assert result is False
