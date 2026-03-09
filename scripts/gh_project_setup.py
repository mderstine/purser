"""GitHub Projects v2 detection and setup flow for Purser.

Detects GitHub Projects associated with a repository, offers selection
when multiple exist, and optionally creates a new project with default
columns (Backlog, Ready, In Progress, Done).

Uses only Python stdlib. Reuses GraphQL patterns from gh_project.py.

Usage:
    python3 scripts/gh_project_setup.py              # interactive detection/setup
    python3 scripts/gh_project_setup.py --json       # output result as JSON
    python3 scripts/gh_project_setup.py --check      # check only, no prompts
"""

import contextlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Allow importing sibling modules
sys.path.insert(0, str(Path(__file__).parent))
import config

DEFAULT_COLUMNS = [
    {"name": "Backlog", "color": "GRAY", "description": "Not yet ready to work on"},
    {"name": "Ready", "color": "BLUE", "description": "Unblocked and available for work"},
    {"name": "In Progress", "color": "YELLOW", "description": "Currently being worked on"},
    {"name": "Done", "color": "GREEN", "description": "Completed"},
]


def _has_gh() -> bool:
    """Check if gh CLI is available."""
    return shutil.which("gh") is not None


def _gql(query: str, **variables) -> dict | None:
    """Execute a GraphQL query/mutation via gh api."""
    cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in variables.items():
        cmd.extend(["-f", f"{k}={v}"])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def list_projects(owner: str, repo: str) -> list[dict]:
    """List all GitHub Projects v2 associated with a repository.

    Returns a list of dicts with keys: id, title, number, url.
    """
    data = _gql(
        """
        query($owner: String!, $repo: String!) {
            repository(owner: $owner, name: $repo) {
                projectsV2(first: 50) {
                    nodes { id title number url }
                }
            }
        }
    """,
        owner=owner,
        repo=repo,
    )
    if not data:
        return []
    try:
        return data["data"]["repository"]["projectsV2"]["nodes"]
    except (KeyError, TypeError):
        return []


def _get_owner_id() -> str | None:
    """Get the authenticated user's node ID."""
    data = _gql("query { viewer { id } }")
    if not data:
        return None
    try:
        return data["data"]["viewer"]["id"]
    except (KeyError, TypeError):
        return None


def _get_repo_id(owner: str, repo: str) -> str | None:
    """Get the repository node ID."""
    data = _gql(
        """
        query($owner: String!, $repo: String!) {
            repository(owner: $owner, name: $repo) { id }
        }
    """,
        owner=owner,
        repo=repo,
    )
    if not data:
        return None
    try:
        return data["data"]["repository"]["id"]
    except (KeyError, TypeError):
        return None


def list_owner_projects(owner: str) -> list[dict]:
    """List all GitHub Projects v2 owned by a user or organization.

    Tries the user query first (``viewer.projectsV2``), then falls back to
    ``organization.projectsV2`` for org-owned projects.

    Returns a list of dicts with keys: id, title, number, url.
    """
    # Try user projects first
    data = _gql(
        """
        query {
            viewer {
                projectsV2(first: 50, orderBy: {field: UPDATED_AT, direction: DESC}) {
                    nodes { id title number url }
                }
            }
        }
    """
    )
    projects: list[dict] = []
    if data:
        with contextlib.suppress(KeyError, TypeError):
            projects = data["data"]["viewer"]["projectsV2"]["nodes"]

    # Also try organization projects if owner differs from viewer
    org_data = _gql(
        """
        query($owner: String!) {
            organization(login: $owner) {
                projectsV2(first: 50, orderBy: {field: UPDATED_AT, direction: DESC}) {
                    nodes { id title number url }
                }
            }
        }
    """,
        owner=owner,
    )
    if org_data:
        try:
            org_projects = org_data["data"]["organization"]["projectsV2"]["nodes"]
            # Merge, avoiding duplicates by id
            seen = {p["id"] for p in projects}
            for p in org_projects:
                if p["id"] not in seen:
                    projects.append(p)
        except (KeyError, TypeError):
            pass

    return projects


def link_project_to_repo(project_id: str, owner: str, repo: str) -> bool:
    """Link an existing GitHub Project to a repository.

    Returns True on success, False on failure.
    """
    repo_id = _get_repo_id(owner, repo)
    if not repo_id:
        print("  Failed to get repository ID.", file=sys.stderr)
        return False

    data = _gql(
        """
        mutation($projectId: ID!, $repositoryId: ID!) {
            linkProjectV2ToRepository(input: {
                projectId: $projectId, repositoryId: $repositoryId
            }) { repository { nameWithOwner } }
        }
    """,
        projectId=project_id,
        repositoryId=repo_id,
    )
    if not data:
        print("  Failed to link project to repository.", file=sys.stderr)
        return False
    return True


def create_project(owner: str, repo: str, title: str = "Purser") -> dict | None:
    """Create a new GitHub Project v2 and link it to the repository.

    Returns dict with id, title, number, url on success, None on failure.
    """
    owner_id = _get_owner_id()
    if not owner_id:
        print("  Failed to get owner ID for project creation.", file=sys.stderr)
        return None

    data = _gql(
        """
        mutation($ownerId: ID!, $title: String!) {
            createProjectV2(input: {ownerId: $ownerId, title: $title}) {
                projectV2 { id title number url }
            }
        }
    """,
        ownerId=owner_id,
        title=title,
    )
    if not data:
        print("  Failed to create project.", file=sys.stderr)
        return None

    try:
        project = data["data"]["createProjectV2"]["projectV2"]
    except (KeyError, TypeError):
        print("  Unexpected response from project creation.", file=sys.stderr)
        return None

    # Link project to repository
    link_project_to_repo(project["id"], owner, repo)

    # Configure Status field with default columns
    _configure_status_field(project["id"])

    return project


def _configure_status_field(project_id: str) -> None:
    """Update the Status field to have the default columns."""
    # Get fields to find the Status field ID
    data = _gql(
        """
        query($projectId: ID!) {
            node(id: $projectId) {
                ... on ProjectV2 {
                    fields(first: 30) {
                        nodes {
                            ... on ProjectV2SingleSelectField {
                                id name options { id name }
                            }
                        }
                    }
                }
            }
        }
    """,
        projectId=project_id,
    )
    if not data:
        return

    try:
        fields = data["data"]["node"]["fields"]["nodes"]
    except (KeyError, TypeError):
        return

    status_field_id = None
    for f in fields:
        if f.get("name") == "Status":
            status_field_id = f["id"]
            break

    if not status_field_id:
        return

    opts_str = ", ".join(
        f'{{name: "{c["name"]}", color: {c["color"]}, description: "{c["description"]}"}}'
        for c in DEFAULT_COLUMNS
    )
    _gql(
        f"""
        mutation($fieldId: ID!) {{
            updateProjectV2Field(input: {{
                fieldId: $fieldId
                singleSelectOptions: [{opts_str}]
            }}) {{
                projectV2Field {{
                    ... on ProjectV2SingleSelectField {{
                        options {{ id name }}
                    }}
                }}
            }}
        }}
    """,
        fieldId=status_field_id,
    )


def _prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt user for yes/no answer."""
    suffix = " [Y/n]: " if default else " [y/N]: "
    try:
        answer = input(question + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def _prompt_select(projects: list[dict]) -> dict | None:
    """Present a selection menu for multiple projects."""
    print()
    print("Multiple GitHub Projects found:")
    for i, p in enumerate(projects, 1):
        print(f"  {i}. {p['title']} (#{p['number']})")
    print("  0. Skip — don't use a project")
    print()
    try:
        choice = input("Select a project [1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if not choice:
        choice = "1"
    try:
        idx = int(choice)
    except ValueError:
        print(f"  Invalid selection: {choice}", file=sys.stderr)
        return None
    if idx == 0:
        return None
    if 1 <= idx <= len(projects):
        return projects[idx - 1]
    print(f"  Selection out of range: {idx}", file=sys.stderr)
    return None


def detect_or_setup(
    owner: str,
    repo: str,
    repo_root: Path | None = None,
    check_only: bool = False,
) -> dict:
    """Main flow: detect or set up a GitHub Project.

    Returns:
        {
            "status": "found" | "created" | "skipped" | "declined" | "error",
            "project": {"id": ..., "title": ..., "number": ..., "url": ...} | null,
            "message": "human-readable summary"
        }
    """
    if not _has_gh():
        return {
            "status": "skipped",
            "project": None,
            "message": "gh CLI not available — GitHub Projects setup skipped.",
        }

    if not owner or not repo:
        return {
            "status": "skipped",
            "project": None,
            "message": "No GitHub remote configured — GitHub Projects setup skipped.",
        }

    # Check config for pre-selected project
    cfg = config.load_config(repo_root)
    configured_number = cfg["github"].get("project_number", "")
    if configured_number:
        projects = list_projects(owner, repo)
        for p in projects:
            if str(p.get("number")) == configured_number:
                return {
                    "status": "found",
                    "project": p,
                    "message": f"Using configured project: {p['title']} (#{p['number']})",
                }
        # Config points to a project that doesn't exist — fall through to detection

    # Detect existing projects
    projects = list_projects(owner, repo)

    if len(projects) == 1:
        project = projects[0]
        if check_only:
            return {
                "status": "found",
                "project": project,
                "message": f"Found project: {project['title']} (#{project['number']})",
            }
        print(f"\nFound GitHub Project: {project['title']} (#{project['number']})")
        if _prompt_yes_no("  Use this project?"):
            return {
                "status": "found",
                "project": project,
                "message": f"Selected project: {project['title']} (#{project['number']})",
            }
        return {
            "status": "declined",
            "project": None,
            "message": "User declined the existing project.",
        }

    if len(projects) > 1:
        if check_only:
            return {
                "status": "found",
                "project": projects[0],
                "message": (
                    f"Found {len(projects)} projects (returning first: {projects[0]['title']})"
                ),
            }
        selected = _prompt_select(projects)
        if selected:
            return {
                "status": "found",
                "project": selected,
                "message": f"Selected project: {selected['title']} (#{selected['number']})",
            }
        return {
            "status": "declined",
            "project": None,
            "message": "No project selected.",
        }

    # No projects found
    if check_only:
        return {
            "status": "skipped",
            "project": None,
            "message": "No GitHub Projects found for this repository.",
        }

    print("\nNo GitHub Projects found for this repository.")
    if not _prompt_yes_no("  Create a new project with default columns?"):
        return {
            "status": "declined",
            "project": None,
            "message": "User declined project creation.",
        }

    project = create_project(owner, repo)
    if not project:
        return {
            "status": "error",
            "project": None,
            "message": "Failed to create GitHub Project.",
        }

    return {
        "status": "created",
        "project": project,
        "message": f"Created project: {project['title']} (#{project['number']})",
    }


def main():
    """CLI entry point."""
    use_json = "--json" in sys.argv
    check_only = "--check" in sys.argv

    # Get owner/repo from config or detection
    cfg = config.load_config()
    owner = cfg["github"].get("owner", "")
    repo = cfg["github"].get("repo", "")

    # Fall back to gh CLI detection if not in config
    if not owner or not repo:
        try:
            from lib import get_repo_name, get_repo_owner

            owner = owner or get_repo_owner()
            repo = repo or get_repo_name()
        except ImportError:
            pass

    result = detect_or_setup(owner, repo, check_only=check_only)

    if use_json:
        print(json.dumps(result, indent=2))
    else:
        print(result["message"])
        if result["project"]:
            p = result["project"]
            print(f"  Project: {p['title']} (#{p['number']})")
            if p.get("url"):
                print(f"  URL: {p['url']}")

    sys.exit(0 if result["status"] in ("found", "created", "skipped") else 1)


if __name__ == "__main__":
    main()
