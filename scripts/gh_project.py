"""Manage GitHub Projects v2 board for beads issue tracking.

Creates/maintains a project board with Status columns (Backlog, Ready,
In Progress, Done) and custom fields (Priority, Type).
"""

import json
import subprocess
import sys

from lib import get_repo_owner, get_repo_name

PROJECT_TITLE = "Ralph-Beads"

STATUS_OPTIONS = [
    {"name": "Backlog", "color": "GRAY", "description": "Not yet ready to work on"},
    {"name": "Ready", "color": "BLUE", "description": "Unblocked and available for work"},
    {"name": "In Progress", "color": "YELLOW", "description": "Currently being worked on"},
    {"name": "Done", "color": "GREEN", "description": "Completed"},
]

PRIORITY_OPTIONS = [
    {"name": "P0 Critical", "color": "RED", "description": "Security, data loss, broken builds"},
    {"name": "P1 High", "color": "ORANGE", "description": "Major features, important bugs"},
    {"name": "P2 Medium", "color": "YELLOW", "description": "Default priority"},
    {"name": "P3 Low", "color": "BLUE", "description": "Polish, optimization"},
    {"name": "P4 Backlog", "color": "GRAY", "description": "Future ideas"},
]

TYPE_OPTIONS = [
    {"name": "bug", "color": "RED", "description": "Something broken"},
    {"name": "feature", "color": "GREEN", "description": "New functionality"},
    {"name": "task", "color": "BLUE", "description": "Work item"},
    {"name": "epic", "color": "PURPLE", "description": "Large feature with subtasks"},
    {"name": "chore", "color": "GRAY", "description": "Maintenance"},
]

PRIORITY_MAP = {
    0: "P0 Critical",
    1: "P1 High",
    2: "P2 Medium",
    3: "P3 Low",
    4: "P4 Backlog",
}


def parse_args(argv):
    """Parse CLI arguments."""
    dry_run = "--dry-run" in argv
    setup_only = "--setup" in argv
    return {"dry_run": dry_run, "setup_only": setup_only}


def gql(query, **variables):
    """Execute a GraphQL query/mutation via gh api."""
    cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in variables.items():
        cmd.extend(["-f", f"{k}={v}"])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        err = result.stderr.strip()
        print(f"  GraphQL error: {err}", file=sys.stderr)
        return None
    return json.loads(result.stdout)


def get_owner_id():
    """Get the authenticated user's node ID."""
    data = gql("query { viewer { id } }")
    return data["data"]["viewer"]["id"] if data else None


def get_repo_id():
    """Get the repository node ID."""
    data = gql("""
        query($owner: String!, $repo: String!) {
            repository(owner: $owner, name: $repo) { id }
        }
    """, owner=get_repo_owner(), repo=get_repo_name())
    return data["data"]["repository"]["id"] if data else None


def find_project():
    """Find an existing project by title, return (project_id, number) or (None, None)."""
    data = gql("""
        query($owner: String!, $repo: String!) {
            repository(owner: $owner, name: $repo) {
                projectsV2(first: 20) {
                    nodes { id title number }
                }
            }
        }
    """, owner=get_repo_owner(), repo=get_repo_name())
    if not data:
        return None, None
    for p in data["data"]["repository"]["projectsV2"]["nodes"]:
        if p["title"] == PROJECT_TITLE:
            return p["id"], p["number"]
    return None, None


def create_project():
    """Create a new project and return (project_id, number)."""
    owner_id = get_owner_id()
    if not owner_id:
        return None, None
    data = gql("""
        mutation($ownerId: ID!, $title: String!) {
            createProjectV2(input: {ownerId: $ownerId, title: $title}) {
                projectV2 { id title number }
            }
        }
    """, ownerId=owner_id, title=PROJECT_TITLE)
    if not data:
        return None, None
    p = data["data"]["createProjectV2"]["projectV2"]
    return p["id"], p["number"]


def link_project_to_repo(project_id):
    """Link the project to the repository."""
    repo_id = get_repo_id()
    if not repo_id:
        return
    gql("""
        mutation($projectId: ID!, $repositoryId: ID!) {
            linkProjectV2ToRepository(input: {
                projectId: $projectId, repositoryId: $repositoryId
            }) { repository { nameWithOwner } }
        }
    """, projectId=project_id, repositoryId=repo_id)


def get_project_fields(project_id):
    """Get all fields on the project, return dict keyed by field name."""
    data = gql("""
        query($projectId: ID!) {
            node(id: $projectId) {
                ... on ProjectV2 {
                    fields(first: 30) {
                        nodes {
                            ... on ProjectV2Field { id name dataType }
                            ... on ProjectV2SingleSelectField {
                                id name dataType
                                options { id name }
                            }
                            ... on ProjectV2IterationField { id name dataType }
                        }
                    }
                }
            }
        }
    """, projectId=project_id)
    if not data:
        return {}
    fields = {}
    for f in data["data"]["node"]["fields"]["nodes"]:
        if "name" in f:
            fields[f["name"]] = f
    return fields


def create_single_select_field(project_id, name, options):
    """Create a single-select custom field on the project."""
    opts_str = ", ".join(
        f'{{name: "{o["name"]}", color: {o["color"]}, description: "{o["description"]}"}}'
        for o in options
    )
    data = gql(f"""
        mutation($projectId: ID!) {{
            createProjectV2Field(input: {{
                projectId: $projectId
                dataType: SINGLE_SELECT
                name: "{name}"
                singleSelectOptions: [{opts_str}]
            }}) {{
                projectV2Field {{
                    ... on ProjectV2SingleSelectField {{
                        id name options {{ id name }}
                    }}
                }}
            }}
        }}
    """, projectId=project_id)
    if data:
        return data["data"]["createProjectV2Field"]["projectV2Field"]
    return None


def update_status_options(field_id):
    """Update the Status field to have our custom options."""
    opts_str = ", ".join(
        f'{{name: "{o["name"]}", color: {o["color"]}, description: "{o["description"]}"}}'
        for o in STATUS_OPTIONS
    )
    gql(f"""
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
    """, fieldId=field_id)


def setup_project(dry_run):
    """Ensure project exists with correct fields. Returns (project_id, fields_dict)."""
    project_id, project_num = find_project()

    if project_id:
        print(f"Found project: {PROJECT_TITLE} (#{project_num})")
    else:
        if dry_run:
            print(f"Would create project: {PROJECT_TITLE}")
            return None, {}
        print(f"Creating project: {PROJECT_TITLE}")
        project_id, project_num = create_project()
        if not project_id:
            print("ERROR: Failed to create project")
            return None, {}
        link_project_to_repo(project_id)
        print(f"  Created and linked to repo (#{project_num})")

    fields = get_project_fields(project_id)

    if "Status" in fields:
        existing_options = {o["name"] for o in fields["Status"].get("options", [])}
        desired_options = {o["name"] for o in STATUS_OPTIONS}
        if existing_options != desired_options:
            if dry_run:
                print(f"  Would update Status options: {existing_options} -> {desired_options}")
            else:
                update_status_options(fields["Status"]["id"])
                print("  Updated Status field options")
                fields = get_project_fields(project_id)
        else:
            print("  Status field: OK")

    if "Priority" not in fields:
        if dry_run:
            print("  Would create Priority field")
        else:
            create_single_select_field(project_id, "Priority", PRIORITY_OPTIONS)
            print("  Created Priority field")
            fields = get_project_fields(project_id)
    else:
        print("  Priority field: OK")

    if "Type" not in fields:
        if dry_run:
            print("  Would create Type field")
        else:
            create_single_select_field(project_id, "Type", TYPE_OPTIONS)
            print("  Created Type field")
            fields = get_project_fields(project_id)
    else:
        print("  Type field: OK")

    return project_id, fields


def get_project_items(project_id):
    """Get all items on the project board, return dict keyed by issue number."""
    items = {}
    cursor = None
    while True:
        after = f', after: "{cursor}"' if cursor else ""
        data = gql(f"""
            query($projectId: ID!) {{
                node(id: $projectId) {{
                    ... on ProjectV2 {{
                        items(first: 100{after}) {{
                            pageInfo {{ hasNextPage endCursor }}
                            nodes {{
                                id
                                content {{
                                    ... on Issue {{ number }}
                                }}
                                fieldValues(first: 20) {{
                                    nodes {{
                                        ... on ProjectV2ItemFieldSingleSelectValue {{
                                            field {{ ... on ProjectV2SingleSelectField {{ name }} }}
                                            name
                                            optionId
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        """, projectId=project_id)
        if not data:
            break
        item_data = data["data"]["node"]["items"]
        for item in item_data["nodes"]:
            content = item.get("content")
            if content and "number" in content:
                field_values = {}
                for fv in item.get("fieldValues", {}).get("nodes", []):
                    if "field" in fv and "name" in fv:
                        field_values[fv["field"]["name"]] = {
                            "name": fv["name"],
                            "optionId": fv.get("optionId"),
                        }
                items[content["number"]] = {
                    "item_id": item["id"],
                    "fields": field_values,
                }
        if item_data["pageInfo"]["hasNextPage"]:
            cursor = item_data["pageInfo"]["endCursor"]
        else:
            break
    return items


def add_issue_to_project(project_id, issue_node_id):
    """Add an issue to the project. Returns the item ID."""
    data = gql("""
        mutation($projectId: ID!, $contentId: ID!) {
            addProjectV2ItemById(input: {
                projectId: $projectId, contentId: $contentId
            }) {
                item { id }
            }
        }
    """, projectId=project_id, contentId=issue_node_id)
    if data:
        return data["data"]["addProjectV2ItemById"]["item"]["id"]
    return None


def set_field_value(project_id, item_id, field_id, option_id):
    """Set a single-select field value on a project item."""
    gql("""
        mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
            updateProjectV2ItemFieldValue(input: {
                projectId: $projectId
                itemId: $itemId
                fieldId: $fieldId
                value: { singleSelectOptionId: $optionId }
            }) {
                projectV2Item { id }
            }
        }
    """, projectId=project_id, itemId=item_id, fieldId=field_id, optionId=option_id)


def get_option_id(fields, field_name, option_name):
    """Look up the option ID for a named option in a field."""
    field = fields.get(field_name, {})
    for opt in field.get("options", []):
        if opt["name"] == option_name:
            return opt["id"]
    return None


def beads_to_status(issue):
    """Map beads issue state to project Status column."""
    status = issue.get("status", "open")
    if status == "closed":
        return "Done"
    if status == "in_progress":
        return "In Progress"
    dep_count = issue.get("dependency_count", 0)
    if dep_count > 0:
        return "Backlog"
    return "Ready"


def get_gh_issue_node_ids():
    """Get GitHub issue node IDs keyed by issue number."""
    result = subprocess.run(
        ["gh", "issue", "list", "--state", "all", "--limit", "1000",
         "--json", "number,id"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return {}
    issues = json.loads(result.stdout)
    return {i["number"]: i["id"] for i in issues}


def sync_issues_to_board(project_id, fields, dry_run):
    """Add beads-linked GitHub issues to the project board and set fields."""
    beads_issues = []
    for status in ("open", "in_progress", "closed"):
        result = subprocess.run(
            ["bd", "list", "--status", status, "--json"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            beads_issues.extend(json.loads(result.stdout))

    linked = []
    for issue in beads_issues:
        ref = issue.get("external_ref", "")
        if ref.startswith("gh-"):
            try:
                gh_num = int(ref[3:])
                linked.append((gh_num, issue))
            except ValueError:
                pass

    if not linked:
        print("No beads issues linked to GitHub. Run gh-sync.sh first.")
        return

    print(f"\nSyncing {len(linked)} linked issue(s) to project board...")

    existing_items = get_project_items(project_id)
    gh_node_ids = get_gh_issue_node_ids()

    status_field_id = fields.get("Status", {}).get("id")
    priority_field_id = fields.get("Priority", {}).get("id")
    type_field_id = fields.get("Type", {}).get("id")

    added = 0
    updated = 0

    for gh_num, issue in linked:
        node_id = gh_node_ids.get(gh_num)
        if not node_id:
            print(f"  skip: #{gh_num} (not found in GitHub)")
            continue

        target_status = beads_to_status(issue)
        target_priority = PRIORITY_MAP.get(issue.get("priority"), "P2 Medium")
        target_type = issue.get("issue_type", "task")

        if gh_num in existing_items:
            item = existing_items[gh_num]
            item_id = item["item_id"]
            current_fields = item["fields"]
            changes = []

            current_status = current_fields.get("Status", {}).get("name")
            if current_status != target_status:
                changes.append(f"status:{current_status}->{target_status}")

            current_priority = current_fields.get("Priority", {}).get("name")
            if current_priority != target_priority:
                changes.append(f"priority->{target_priority}")

            current_type = current_fields.get("Type", {}).get("name")
            if current_type != target_type:
                changes.append(f"type->{target_type}")

            if not changes:
                print(f"  unchanged: #{gh_num} ({issue['id']})")
                continue

            if dry_run:
                print(f"  would update: #{gh_num} ({', '.join(changes)})")
                continue

            if current_status != target_status and status_field_id:
                opt_id = get_option_id(fields, "Status", target_status)
                if opt_id:
                    set_field_value(project_id, item_id, status_field_id, opt_id)

            if current_priority != target_priority and priority_field_id:
                opt_id = get_option_id(fields, "Priority", target_priority)
                if opt_id:
                    set_field_value(project_id, item_id, priority_field_id, opt_id)

            if current_type != target_type and type_field_id:
                opt_id = get_option_id(fields, "Type", target_type)
                if opt_id:
                    set_field_value(project_id, item_id, type_field_id, opt_id)

            print(f"  updated: #{gh_num} ({', '.join(changes)})")
            updated += 1
        else:
            if dry_run:
                print(f"  would add: #{gh_num} ({issue['id']}) [{target_status}]")
                added += 1
                continue

            item_id = add_issue_to_project(project_id, node_id)
            if not item_id:
                print(f"  ERROR: failed to add #{gh_num}")
                continue

            if status_field_id:
                opt_id = get_option_id(fields, "Status", target_status)
                if opt_id:
                    set_field_value(project_id, item_id, status_field_id, opt_id)

            if priority_field_id:
                opt_id = get_option_id(fields, "Priority", target_priority)
                if opt_id:
                    set_field_value(project_id, item_id, priority_field_id, opt_id)

            if type_field_id:
                opt_id = get_option_id(fields, "Type", target_type)
                if opt_id:
                    set_field_value(project_id, item_id, type_field_id, opt_id)

            print(f"  added: #{gh_num} ({issue['id']}) [{target_status}]")
            added += 1

    print(f"\nBoard sync: {added} added, {updated} updated")


def main():
    args = parse_args(sys.argv[1:])
    dry_run = args["dry_run"]
    setup_only = args["setup_only"]

    print("=== GitHub Project Board Sync ===")
    if dry_run:
        print("(dry-run mode)")
    print("")

    project_id, fields = setup_project(dry_run)
    if not project_id and not dry_run:
        print("ERROR: Could not set up project")
        sys.exit(1)

    if setup_only:
        print("\nSetup complete.")
        return

    if project_id:
        sync_issues_to_board(project_id, fields, dry_run)

    print("\nDone.")


if __name__ == "__main__":
    main()
