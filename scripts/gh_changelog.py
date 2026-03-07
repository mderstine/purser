"""Generate a changelog from closed beads issues.

Groups by epic and type, includes commit SHAs and GitHub issue links.
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone

from lib import run, get_commit_for_issue, get_repo_url


def parse_args(argv):
    """Parse CLI arguments."""
    args = {"since": None, "output": None, "dry_run": False}
    i = 0
    while i < len(argv):
        if argv[i] == "--since" and i + 1 < len(argv):
            args["since"] = argv[i + 1]
            i += 2
        elif argv[i] == "--output" and i + 1 < len(argv):
            args["output"] = argv[i + 1]
            i += 2
        elif argv[i] == "--dry-run":
            args["dry_run"] = True
            i += 1
        else:
            i += 1
    return args


def get_closed_issues(since=None):
    """Get all closed beads issues, optionally filtered by date."""
    raw = run(["bd", "list", "--status", "closed", "--json"])
    if not raw:
        return []
    issues = json.loads(raw)
    if since:
        issues = [i for i in issues if i.get("closed_at", "") >= since]
    return issues


def priority_label(p):
    """Human-readable priority."""
    labels = {0: "Critical", 1: "High", 2: "Medium", 3: "Low", 4: "Backlog"}
    return labels.get(p, f"P{p}")


def type_emoji(t):
    """Type indicator for changelog entries."""
    emojis = {"bug": "fix", "feature": "feat", "task": "task", "chore": "chore", "epic": "epic"}
    return emojis.get(t, t)


def format_changelog(issues, repo_url=None):
    """Format issues as a markdown changelog."""
    lines = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines.append(f"# Changelog")
    lines.append(f"")
    lines.append(f"Generated {now} from beads issue tracker.")
    lines.append("")

    by_epic = defaultdict(list)
    no_epic = []
    epic_titles = {}

    for issue in issues:
        if issue.get("issue_type") == "epic":
            epic_titles[issue["id"]] = issue["title"]
            continue
        parent = issue.get("parent", "")
        if parent:
            by_epic[parent].append(issue)
        else:
            no_epic.append(issue)

    for epic_id in by_epic:
        if epic_id not in epic_titles:
            raw = run(["bd", "show", epic_id, "--json"])
            if raw:
                try:
                    epic_data = json.loads(raw)
                    if isinstance(epic_data, list) and epic_data:
                        epic_data = epic_data[0]
                    if isinstance(epic_data, dict):
                        epic_titles[epic_id] = epic_data.get("title", epic_id)
                    else:
                        epic_titles[epic_id] = epic_id
                except json.JSONDecodeError:
                    epic_titles[epic_id] = epic_id

    def format_issue_line(issue):
        """Format a single issue as a changelog bullet."""
        beads_id = issue["id"]
        title = issue["title"]
        itype = type_emoji(issue.get("issue_type", "task"))
        sha = get_commit_for_issue(beads_id)
        gh_ref = issue.get("external_ref", "")
        gh_num = None
        if gh_ref and gh_ref.startswith("gh-"):
            try:
                gh_num = int(gh_ref[3:])
            except ValueError:
                pass

        parts = [f"- **{itype}:** {title}"]

        refs = []
        if sha:
            if repo_url:
                refs.append(f"[`{sha}`]({repo_url}/commit/{sha})")
            else:
                refs.append(f"`{sha}`")
        if gh_num:
            if repo_url:
                refs.append(f"[#{gh_num}]({repo_url}/issues/{gh_num})")
            else:
                refs.append(f"#{gh_num}")

        if refs:
            parts.append(f" ({', '.join(refs)})")

        return "".join(parts)

    for epic_id in sorted(by_epic.keys(), key=lambda eid: epic_titles.get(eid, eid)):
        epic_title = epic_titles.get(epic_id, epic_id)
        lines.append(f"## {epic_title}")
        lines.append("")

        by_type = defaultdict(list)
        for issue in by_epic[epic_id]:
            by_type[issue.get("issue_type", "task")].append(issue)

        for itype in ["feature", "bug", "task", "chore"]:
            if itype not in by_type:
                continue
            for issue in sorted(by_type[itype], key=lambda i: i.get("closed_at", "")):
                lines.append(format_issue_line(issue))

        lines.append("")

    if no_epic:
        lines.append("## Other")
        lines.append("")
        for issue in sorted(no_epic, key=lambda i: i.get("closed_at", "")):
            lines.append(format_issue_line(issue))
        lines.append("")

    lines.append("---")
    lines.append(f"*{len(issues)} issue(s) closed.*")
    lines.append("")

    return "\n".join(lines)


def main():
    args = parse_args(sys.argv[1:])

    issues = get_closed_issues(since=args["since"])
    if not issues:
        since_msg = f" since {args['since']}" if args["since"] else ""
        print(f"No closed issues found{since_msg}.")
        return

    repo_url = get_repo_url()
    changelog = format_changelog(issues, repo_url)

    if args["output"] and not args["dry_run"]:
        with open(args["output"], "w") as f:
            f.write(changelog)
        print(f"Wrote changelog to {args['output']} ({len(issues)} issues)")
    else:
        print(changelog)


if __name__ == "__main__":
    main()
