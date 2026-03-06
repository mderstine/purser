#!/usr/bin/env bash
# Sync beads issues to GitHub Issues (outbound).
# Beads is source of truth for task state. GitHub is the public mirror.
#
# Usage:
#   scripts/gh-sync.sh              # Sync all beads issues to GitHub
#   scripts/gh-sync.sh --dry-run    # Preview without making changes
#
# Requires: gh (authenticated), bd, python3

set -euo pipefail

DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        -h|--help)
            echo "Usage: $0 [--dry-run]"
            echo "Sync beads issues to GitHub Issues."
            exit 0
            ;;
    esac
done

# Verify prerequisites
for cmd in gh bd python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: $cmd not found"
        exit 1
    fi
done

if ! gh auth status &>/dev/null; then
    echo "Error: gh CLI not authenticated. Run: gh auth login"
    exit 1
fi

echo "=== Beads → GitHub Sync ==="
$DRY_RUN && echo "(dry-run mode)"
echo ""

# Export for python
export DRY_RUN

python3 - "$@" << 'PYEOF'
import json
import os
import subprocess
import sys

DRY_RUN = os.environ.get("DRY_RUN") == "true"


def run(cmd, capture=True):
    """Run a command (list of args) and return stdout."""
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if result.returncode != 0 and capture:
        print(f"  ERROR: {cmd}", file=sys.stderr)
        print(f"  {result.stderr.strip()}", file=sys.stderr)
    return result.stdout.strip() if capture else ""


def get_beads_issues():
    """Get all beads issues (open + closed) as a list of dicts."""
    # Include all statuses so we can close GH issues when beads issues close
    all_issues = []
    for status in ("open", "in_progress", "closed"):
        raw = run(["bd", "list", "--status", status, "--json"])
        if raw:
            all_issues.extend(json.loads(raw))
    return all_issues


def get_gh_issues():
    """Get all GitHub issues (open and closed) as a dict keyed by number."""
    raw = run(['gh', 'issue', 'list', '--state', 'all', '--limit', '1000',
               '--json', 'number,title,state,labels,body'])
    if not raw:
        return {}
    issues = json.loads(raw)
    return {i["number"]: i for i in issues}


def get_commit_for_issue(beads_id):
    """Find the commit SHA that closed a beads issue."""
    result = run(["git", "log", "--format=%H", f"--grep=Closes: {beads_id}", "-1"])
    return result[:12] if result else None


def slugify_epic(title):
    """Convert an epic title to a label-safe slug."""
    import re
    slug = title.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')[:40]


def beads_to_labels(issue, epic_titles=None):
    """Convert beads issue type, priority, and epic to GitHub label names."""
    labels = []
    itype = issue.get("issue_type", "")
    if itype:
        labels.append(f"type:{itype}")
    priority = issue.get("priority")
    if priority is not None:
        labels.append(f"priority:{priority}")
    status = issue.get("status", "")
    # Add blocked label if issue has unresolved dependencies
    dep_count = issue.get("dependency_count", 0)
    if dep_count > 0 and status == "open":
        labels.append("blocked")
    # Add epic label if issue has a parent
    parent = issue.get("parent", "")
    if parent and epic_titles:
        epic_title = epic_titles.get(parent)
        if epic_title:
            labels.append(f"epic:{slugify_epic(epic_title)}")
    return labels


def beads_to_gh_state(issue):
    """Map beads status to GitHub issue state."""
    status = issue.get("status", "open")
    if status == "closed":
        return "closed"
    return "open"


def build_dependency_maps(beads_issues):
    """Build maps for dependency references.
    Returns (ext_ref_map, blocked_by_map, blocks_map) where:
    - ext_ref_map: beads_id → gh_issue_number
    - blocked_by_map: beads_id → [beads_ids that block it]
    - blocks_map: beads_id → [beads_ids it blocks]
    """
    ext_ref_map = {}
    blocked_by_map = {}
    blocks_map = {}

    for issue in beads_issues:
        beads_id = issue["id"]
        ref = issue.get("external_ref", "")
        if ref and ref.startswith("gh-"):
            try:
                ext_ref_map[beads_id] = int(ref[3:])
            except ValueError:
                pass

    for issue in beads_issues:
        beads_id = issue["id"]
        for dep in issue.get("dependencies", []):
            dep_type = dep.get("type", "")
            dep_id = dep.get("depends_on_id", "")
            if dep_type == "blocks" and dep_id:
                # This issue is blocked by dep_id
                blocked_by_map.setdefault(beads_id, []).append(dep_id)
                # dep_id blocks this issue
                blocks_map.setdefault(dep_id, []).append(beads_id)

    return ext_ref_map, blocked_by_map, blocks_map


def format_gh_body(issue, ext_ref_map=None, blocked_by_map=None, blocks_map=None):
    """Format a GitHub issue body from a beads issue."""
    parts = []

    desc = issue.get("description", "")
    if desc:
        parts.append(desc)

    # Add dependency references
    beads_id = issue["id"]
    dep_lines = []

    if blocked_by_map and beads_id in blocked_by_map:
        for blocker_id in blocked_by_map[beads_id]:
            gh_num = ext_ref_map.get(blocker_id) if ext_ref_map else None
            if gh_num:
                dep_lines.append(f"- Blocked by #{gh_num} (`{blocker_id}`)")
            else:
                dep_lines.append(f"- Blocked by `{blocker_id}`")

    if blocks_map and beads_id in blocks_map:
        for blocked_id in blocks_map[beads_id]:
            gh_num = ext_ref_map.get(blocked_id) if ext_ref_map else None
            if gh_num:
                dep_lines.append(f"- Blocks #{gh_num} (`{blocked_id}`)")
            else:
                dep_lines.append(f"- Blocks `{blocked_id}`")

    if dep_lines:
        parts.append("")
        parts.append("### Dependencies")
        parts.extend(dep_lines)

    parts.append("")
    parts.append("---")
    parts.append(f"**Beads ID:** `{issue['id']}`")

    parent = issue.get("parent", "")
    if parent:
        parts.append(f"**Epic:** `{parent}`")

    status = issue.get("status", "open")
    parts.append(f"**Status:** {status}")

    assignee = issue.get("assignee", "")
    if assignee:
        parts.append(f"**Assignee:** {assignee}")

    parts.append("")
    parts.append("*Synced from [beads](https://github.com/steveyegge/beads) issue tracker*")

    return "\n".join(parts)


def get_external_ref(issue):
    """Extract GitHub issue number from external_ref field (format: 'gh-N')."""
    ref = issue.get("external_ref", "")
    if ref and ref.startswith("gh-"):
        try:
            return int(ref[3:])
        except ValueError:
            pass
    return None


def create_gh_issue(issue, ext_ref_map=None, blocked_by_map=None, blocks_map=None, epic_titles=None):
    """Create a new GitHub issue and return the issue number."""
    title = issue["title"]
    body = format_gh_body(issue, ext_ref_map, blocked_by_map, blocks_map)
    labels = beads_to_labels(issue, epic_titles=epic_titles)
    label_args = ",".join(labels)

    if DRY_RUN:
        print(f"  would create: #{issue['id']} → GH issue \"{title}\" [{label_args}]")
        return None

    # Use gh issue create
    cmd_parts = ["gh", "issue", "create", "--title", title, "--body", body]
    if label_args:
        cmd_parts.extend(["--label", label_args])

    result = subprocess.run(cmd_parts, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR creating GH issue for {issue['id']}: {result.stderr.strip()}")
        return None

    # Parse the URL to get the issue number
    url = result.stdout.strip()
    try:
        gh_num = int(url.rstrip("/").split("/")[-1])
    except (ValueError, IndexError):
        print(f"  ERROR: could not parse issue number from: {url}")
        return None

    print(f"  created: {issue['id']} → #{gh_num} \"{title}\"")
    return gh_num


def update_gh_issue(gh_num, issue, gh_issue, ext_ref_map=None, blocked_by_map=None, blocks_map=None, epic_titles=None):
    """Update an existing GitHub issue if it differs from beads state."""
    changes = []
    title = issue["title"]
    body = format_gh_body(issue, ext_ref_map, blocked_by_map, blocks_map)
    target_state = beads_to_gh_state(issue)
    target_labels = set(beads_to_labels(issue, epic_titles=epic_titles))

    # Check title
    if gh_issue.get("title") != title:
        changes.append("title")

    # Check state
    current_state = "open" if gh_issue.get("state") == "OPEN" else "closed"
    if current_state != target_state:
        changes.append(f"state:{current_state}→{target_state}")

    # Check labels (only beads-managed labels)
    current_labels = {l["name"] for l in gh_issue.get("labels", [])}
    beads_label_prefixes = ("type:", "priority:", "epic:", "blocked", "spec-candidate", "spec-created")
    current_beads_labels = {l for l in current_labels if any(l.startswith(p) or l == p for p in beads_label_prefixes)}
    if current_beads_labels != target_labels:
        changes.append("labels")

    if not changes:
        print(f"  unchanged: {issue['id']} → #{gh_num}")
        return

    if DRY_RUN:
        change_desc = ', '.join(changes)
        if target_state == "closed":
            change_desc += " +closing-comment"
        print(f"  would update: #{gh_num} ({change_desc})")
        return

    # Build update command
    cmd_parts = ["gh", "issue", "edit", str(gh_num), "--title", title, "--body", body]

    # Manage labels: remove old beads labels, add new ones
    for old_label in current_beads_labels - target_labels:
        cmd_parts.extend(["--remove-label", old_label])
    for new_label in target_labels - current_beads_labels:
        cmd_parts.extend(["--add-label", new_label])

    result = subprocess.run(cmd_parts, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR updating #{gh_num}: {result.stderr.strip()}")
        return

    # Handle state changes separately
    if current_state != target_state:
        if target_state == "closed":
            # Post closing comment with commit SHA and close reason
            beads_id = issue["id"]
            close_reason = issue.get("close_reason", "")
            sha = get_commit_for_issue(beads_id)
            comment_parts = []
            if sha:
                comment_parts.append(f"Implemented in {sha}.")
            if close_reason:
                comment_parts.append(close_reason)
            if comment_parts:
                comment = "\n\n".join(comment_parts)
                run(["gh", "issue", "comment", str(gh_num), "--body", comment])
            run(["gh", "issue", "close", str(gh_num)])
        else:
            run(["gh", "issue", "reopen", str(gh_num)])

    print(f"  updated: {issue['id']} → #{gh_num} ({', '.join(changes)})")


def store_external_ref(beads_id, gh_num):
    """Store the GitHub issue number on the beads issue."""
    if DRY_RUN:
        return
    run(["bd", "update", beads_id, "--external-ref", f"gh-{gh_num}", "--json"])


def main():
    beads_issues = get_beads_issues()
    gh_issues = get_gh_issues()

    if not beads_issues:
        print("No beads issues found.")
        return

    # Build epic title map (beads_id → title) for epic label generation
    epic_titles = {
        i["id"]: i["title"]
        for i in beads_issues
        if i.get("issue_type") == "epic"
    }

    # Build dependency cross-reference maps
    ext_ref_map, blocked_by_map, blocks_map = build_dependency_maps(beads_issues)
    dep_args = dict(ext_ref_map=ext_ref_map, blocked_by_map=blocked_by_map, blocks_map=blocks_map, epic_titles=epic_titles)

    print(f"Found {len(beads_issues)} beads issue(s), {len(gh_issues)} GitHub issue(s)")
    print("")

    created = 0
    updated = 0
    skipped = 0

    for issue in beads_issues:
        gh_num = get_external_ref(issue)
        is_closed = issue.get("status") == "closed"

        if gh_num and gh_num in gh_issues:
            # Existing linked issue — update if needed
            update_gh_issue(gh_num, issue, gh_issues[gh_num], **dep_args)
            updated += 1
        elif gh_num and gh_num not in gh_issues:
            # Stale reference — issue was deleted on GitHub, recreate
            print(f"  stale ref: {issue['id']} → #{gh_num} (not found on GitHub)")
            new_num = create_gh_issue(issue, **dep_args)
            if new_num:
                store_external_ref(issue["id"], new_num)
                created += 1
        elif not gh_num and is_closed:
            # Skip closed issues that were never synced (historical)
            skipped += 1
        else:
            # No external ref — create new GitHub issue
            new_num = create_gh_issue(issue, **dep_args)
            if new_num:
                store_external_ref(issue["id"], new_num)
                created += 1
            else:
                skipped += 1

    print("")
    print(f"Summary: {created} created, {updated} updated, {skipped} skipped")


if __name__ == "__main__":
    main()
PYEOF
