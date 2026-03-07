"""Generate a PR description from beads issues addressed in the current branch.

Reads git log to find 'Closes: <bd-id>' references, looks up those issues
and their GitHub counterparts, and formats a PR body.
"""

import json
import re
import sys
from collections import defaultdict

from lib import run, get_repo_url


def parse_args(argv):
    """Parse CLI arguments."""
    args = {"base": "main", "output": None}
    i = 0
    while i < len(argv):
        if argv[i] == "--base" and i + 1 < len(argv):
            args["base"] = argv[i + 1]
            i += 2
        elif argv[i] == "--output" and i + 1 < len(argv):
            args["output"] = argv[i + 1]
            i += 2
        else:
            i += 1
    return args


def get_branch_name():
    """Get current branch name."""
    return run(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def get_commit_messages(base):
    """Get commit messages from base..HEAD."""
    return run(["git", "log", "--format=%H %s%n%b---", f"{base}..HEAD"])


def extract_beads_ids(commit_text):
    """Extract beads IDs from 'Closes: <id>' lines in commit messages."""
    return list(dict.fromkeys(re.findall(r"Closes:\s+([\w-]+\.?\w*)", commit_text)))


def extract_gh_closes(commit_text):
    """Extract GitHub issue numbers from 'Closes #N' lines."""
    return list(dict.fromkeys(re.findall(r"Closes\s+#(\d+)", commit_text)))


def get_commit_subjects(base):
    """Get commit subject lines."""
    raw = run(["git", "log", "--format=%s", f"{base}..HEAD"])
    return [line for line in raw.splitlines() if line.strip()] if raw else []


def lookup_beads_issue(beads_id):
    """Look up a beads issue by ID."""
    raw = run(["bd", "show", beads_id, "--json"])
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return None


def type_label(t):
    """Human-readable type."""
    return {"bug": "Bug fix", "feature": "Feature", "task": "Task",
            "chore": "Chore", "epic": "Epic"}.get(t, t)


def format_pr_body(beads_ids, commit_subjects, base, repo_url=None):
    """Format a PR description from beads issues."""
    lines = []

    issues = []
    for bid in beads_ids:
        issue = lookup_beads_issue(bid)
        if issue:
            issues.append(issue)

    lines.append("## Summary")
    lines.append("")

    if issues:
        by_type = defaultdict(list)
        for issue in issues:
            itype = issue.get("issue_type", "task")
            by_type[itype].append(issue)

        for itype in ["feature", "bug", "task", "chore"]:
            if itype not in by_type:
                continue
            for issue in by_type[itype]:
                title = issue["title"]
                lines.append(f"- **{type_label(itype)}:** {title}")
    else:
        for subject in commit_subjects[:10]:
            lines.append(f"- {subject}")

    lines.append("")

    if issues:
        lines.append("## Linked Issues")
        lines.append("")
        lines.append("| Beads ID | GitHub | Type | Status |")
        lines.append("|----------|--------|------|--------|")
        for issue in issues:
            bid = issue["id"]
            itype = issue.get("issue_type", "task")
            status = issue.get("status", "open")
            gh_ref = issue.get("external_ref", "")
            gh_link = ""
            if gh_ref and gh_ref.startswith("gh-"):
                gh_num = gh_ref[3:]
                if repo_url:
                    gh_link = f"[#{gh_num}]({repo_url}/issues/{gh_num})"
                else:
                    gh_link = f"#{gh_num}"
            lines.append(f"| `{bid}` | {gh_link} | {itype} | {status} |")
        lines.append("")

    if commit_subjects:
        lines.append("## Commits")
        lines.append("")
        for subject in commit_subjects:
            lines.append(f"- {subject}")
        lines.append("")

    lines.append("## Test plan")
    lines.append("")
    lines.append("- [ ] Review linked issues for acceptance criteria")
    lines.append("- [ ] Verify all quality gates pass (`pytest`, `mypy`, `ruff`)")
    lines.append("- [ ] Check `bd ready --json` for unblocked follow-up work")
    lines.append("")

    branch = get_branch_name()
    lines.append("---")
    lines.append(f"*Generated from `{base}..{branch}` by `scripts/gh-pr-body.sh`*")
    lines.append("")

    return "\n".join(lines)


def main():
    args = parse_args(sys.argv[1:])
    base = args["base"]

    check = run(["git", "rev-parse", "--verify", base])
    if not check:
        print(f"Error: base branch '{base}' not found", file=sys.stderr)
        sys.exit(1)

    commit_text = get_commit_messages(base)
    if not commit_text:
        print(f"No commits found between {base} and HEAD.", file=sys.stderr)
        sys.exit(1)

    beads_ids = extract_beads_ids(commit_text)
    commit_subjects = get_commit_subjects(base)

    repo_url = get_repo_url()
    body = format_pr_body(beads_ids, commit_subjects, base, repo_url)

    if args["output"]:
        with open(args["output"], "w") as f:
            f.write(body)
        print(f"Wrote PR body to {args['output']} ({len(beads_ids)} beads issues, {len(commit_subjects)} commits)")
    else:
        print(body)


if __name__ == "__main__":
    main()
