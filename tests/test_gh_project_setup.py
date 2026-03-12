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


_NO_PROJECT_CFG = {
    "github": {
        "remote": "origin",
        "owner": "o",
        "repo": "r",
        "auto_create": "prompt",
        "project_number": "",
    },
    "labels": {"bootstrap": "false"},
}


class TestDetectOrSetupMenu:
    """Tests for the 3-option menu when no projects are linked."""

    @patch("gh_project_setup._has_gh", return_value=True)
    @patch("gh_project_setup.list_projects", return_value=[])
    @patch("gh_project_setup.config.load_config", return_value=_NO_PROJECT_CFG)
    @patch("gh_project_setup._prompt_menu", return_value=0)
    @patch("gh_project_setup.list_owner_projects")
    @patch("gh_project_setup._prompt_select")
    @patch("gh_project_setup.link_project_to_repo", return_value=True)
    def test_attach_existing_success(
        self, mock_link, mock_select, mock_list_owner, mock_menu, *_
    ):
        mock_list_owner.return_value = [
            {"id": "PVT_1", "title": "My Board", "number": 5, "url": ""},
        ]
        mock_select.return_value = {
            "id": "PVT_1",
            "title": "My Board",
            "number": 5,
            "url": "",
        }
        result = gh_project_setup.detect_or_setup("o", "r")
        assert result["status"] == "found"
        assert result["project"]["number"] == 5
        assert "Attached" in result["message"]
        mock_link.assert_called_once_with("PVT_1", "o", "r")

    @patch("gh_project_setup._has_gh", return_value=True)
    @patch("gh_project_setup.list_projects", return_value=[])
    @patch("gh_project_setup.config.load_config", return_value=_NO_PROJECT_CFG)
    @patch("gh_project_setup._prompt_menu", return_value=0)
    @patch("gh_project_setup.list_owner_projects", return_value=[])
    def test_attach_no_projects_available(self, *_):
        result = gh_project_setup.detect_or_setup("o", "r")
        assert result["status"] == "skipped"
        assert "No projects available" in result["message"]

    @patch("gh_project_setup._has_gh", return_value=True)
    @patch("gh_project_setup.list_projects", return_value=[])
    @patch("gh_project_setup.config.load_config", return_value=_NO_PROJECT_CFG)
    @patch("gh_project_setup._prompt_menu", return_value=0)
    @patch("gh_project_setup.list_owner_projects")
    @patch("gh_project_setup._prompt_select", return_value=None)
    def test_attach_user_cancels_selection(self, mock_select, mock_list_owner, *_):
        mock_list_owner.return_value = [
            {"id": "PVT_1", "title": "A", "number": 1, "url": ""},
        ]
        result = gh_project_setup.detect_or_setup("o", "r")
        assert result["status"] == "declined"

    @patch("gh_project_setup._has_gh", return_value=True)
    @patch("gh_project_setup.list_projects", return_value=[])
    @patch("gh_project_setup.config.load_config", return_value=_NO_PROJECT_CFG)
    @patch("gh_project_setup._prompt_menu", return_value=0)
    @patch("gh_project_setup.list_owner_projects")
    @patch("gh_project_setup._prompt_select")
    @patch("gh_project_setup.link_project_to_repo", return_value=False)
    def test_attach_link_fails(self, mock_link, mock_select, mock_list_owner, *_):
        mock_list_owner.return_value = [
            {"id": "PVT_1", "title": "A", "number": 1, "url": ""},
        ]
        mock_select.return_value = {
            "id": "PVT_1",
            "title": "A",
            "number": 1,
            "url": "",
        }
        result = gh_project_setup.detect_or_setup("o", "r")
        assert result["status"] == "error"

    @patch("gh_project_setup._has_gh", return_value=True)
    @patch("gh_project_setup.list_projects", return_value=[])
    @patch("gh_project_setup.config.load_config", return_value=_NO_PROJECT_CFG)
    @patch("gh_project_setup._prompt_menu", return_value=1)
    @patch("gh_project_setup.create_project")
    def test_create_new_via_menu(self, mock_create, *_):
        mock_create.return_value = {
            "id": "PVT_2",
            "title": "Purser",
            "number": 1,
            "url": "",
        }
        result = gh_project_setup.detect_or_setup("o", "r")
        assert result["status"] == "created"
        mock_create.assert_called_once_with("o", "r")

    @patch("gh_project_setup._has_gh", return_value=True)
    @patch("gh_project_setup.list_projects", return_value=[])
    @patch("gh_project_setup.config.load_config", return_value=_NO_PROJECT_CFG)
    @patch("gh_project_setup._prompt_menu", return_value=2)
    def test_skip_via_menu(self, *_):
        result = gh_project_setup.detect_or_setup("o", "r")
        assert result["status"] == "declined"

    @patch("gh_project_setup._has_gh", return_value=True)
    @patch("gh_project_setup.list_projects", return_value=[])
    @patch("gh_project_setup.config.load_config", return_value=_NO_PROJECT_CFG)
    @patch("gh_project_setup._prompt_menu", return_value=None)
    def test_cancelled_menu(self, *_):
        result = gh_project_setup.detect_or_setup("o", "r")
        assert result["status"] == "declined"


def _fields_response(has_status: bool) -> dict:
    """Build a mock _gql response for the fields query."""
    nodes = []
    if has_status:
        nodes.append({"id": "FIELD_1", "name": "Status", "options": []})
    return {"data": {"node": {"fields": {"nodes": nodes}}}}


class TestConfigureStatusField:
    """Tests for _configure_status_field() — creates or updates Status field."""

    @patch("gh_project_setup._gql")
    def test_absent_creates_status_field(self, mock_gql):
        """When no Status field exists, createProjectV2Field mutation is called."""
        mock_gql.side_effect = [
            _fields_response(has_status=False),
            {
                "data": {
                    "createProjectV2Field": {
                        "projectV2Field": {"id": "F_new", "name": "Status", "options": []}
                    }
                }
            },
        ]
        gh_project_setup._configure_status_field("PVT_1")
        assert mock_gql.call_count == 2
        create_query = mock_gql.call_args_list[1][0][0]
        assert "createProjectV2Field" in create_query
        assert "SINGLE_SELECT" in create_query
        assert "Status" in create_query

    @patch("gh_project_setup._gql")
    def test_present_updates_status_field(self, mock_gql):
        """When Status field already exists, updateProjectV2Field is called, not create."""
        mock_gql.side_effect = [
            _fields_response(has_status=True),
            {"data": {"updateProjectV2Field": {"projectV2Field": {"options": []}}}},
        ]
        gh_project_setup._configure_status_field("PVT_1")
        assert mock_gql.call_count == 2
        update_query = mock_gql.call_args_list[1][0][0]
        assert "updateProjectV2Field" in update_query
        assert "createProjectV2Field" not in update_query

    @patch("gh_project_setup._gql", return_value=None)
    def test_query_failure_logs_warning(self, mock_gql, caplog):
        """When the fields query fails, a warning is logged and no second call is made."""
        import logging

        with caplog.at_level(logging.WARNING, logger="gh_project_setup"):
            gh_project_setup._configure_status_field("PVT_1")
        assert mock_gql.call_count == 1
        assert any(r.levelname == "WARNING" for r in caplog.records)

    @patch("gh_project_setup._gql")
    def test_create_failure_logs_warning(self, mock_gql, caplog):
        """When Status field is absent and createProjectV2Field fails, a warning is logged."""
        import logging

        mock_gql.side_effect = [
            _fields_response(has_status=False),
            None,  # create mutation fails
        ]
        with caplog.at_level(logging.WARNING, logger="gh_project_setup"):
            gh_project_setup._configure_status_field("PVT_1")
        assert mock_gql.call_count == 2
        assert any(r.levelname == "WARNING" for r in caplog.records)

    @patch("gh_project_setup._gql")
    def test_absent_configures_all_default_columns(self, mock_gql):
        """When creating the Status field, all DEFAULT_COLUMNS are included in the query."""
        mock_gql.side_effect = [
            _fields_response(has_status=False),
            {
                "data": {
                    "createProjectV2Field": {
                        "projectV2Field": {"id": "F_new", "name": "Status", "options": []}
                    }
                }
            },
        ]
        gh_project_setup._configure_status_field("PVT_1")
        create_query = mock_gql.call_args_list[1][0][0]
        for col in gh_project_setup.DEFAULT_COLUMNS:
            assert col["name"] in create_query


class TestPromptMenu:
    @patch("builtins.input", return_value="")
    def test_default_is_first(self, _):
        result = gh_project_setup._prompt_menu(["A", "B", "C"])
        assert result == 0

    @patch("builtins.input", return_value="2")
    def test_selects_second(self, _):
        result = gh_project_setup._prompt_menu(["A", "B", "C"])
        assert result == 1

    @patch("builtins.input", return_value="99")
    def test_out_of_range_returns_none(self, _):
        result = gh_project_setup._prompt_menu(["A", "B"])
        assert result is None

    @patch("builtins.input", side_effect=EOFError)
    def test_eof_returns_none(self, _):
        result = gh_project_setup._prompt_menu(["A"])
        assert result is None

    @patch("builtins.input", return_value="abc")
    def test_non_numeric_returns_none(self, _):
        result = gh_project_setup._prompt_menu(["A"])
        assert result is None
