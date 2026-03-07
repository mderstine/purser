#!/usr/bin/env bash
# Triage GitHub Issues labeled 'spec-candidate' into specs/ files.
# This is the inbound flow: collaborators create GitHub Issues with the
# 'spec-candidate' label, and this script converts them to spec files
# that the planning loop can decompose into beads tasks.
#
# Usage:
#   scripts/gh-triage.sh              # Triage all spec-candidate issues
#   scripts/gh-triage.sh --dry-run    # Preview without making changes
#
# Requires: gh (authenticated), python3

set -euo pipefail

DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        -h|--help)
            echo "Usage: $0 [--dry-run]"
            echo "Triage GitHub Issues labeled 'spec-candidate' into specs/ files."
            exit 0
            ;;
    esac
done

for cmd in gh python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: $cmd not found"
        exit 1
    fi
done

if ! gh auth status &>/dev/null; then
    echo "Error: gh CLI not authenticated. Run: gh auth login"
    exit 1
fi

echo "=== GitHub Issue Triage → Specs ==="
$DRY_RUN && echo "(dry-run mode)"
echo ""

export DRY_RUN
export PYTHONPATH="$(cd "$(dirname "$0")" && pwd)${PYTHONPATH:+:$PYTHONPATH}"

python3 - "$@" << 'PYEOF'
import json
import os
import re
import sys

from lib import run, slugify

DRY_RUN = os.environ.get("DRY_RUN") == "true"


def get_spec_candidates():
    """Get GitHub Issues labeled spec-candidate that don't have spec-created."""
    raw = run([
        'gh', 'issue', 'list', '--label', 'spec-candidate', '--state', 'open',
        '--limit', '100', '--json', 'number,title,body,labels'
    ])
    if not raw:
        return []
    issues = json.loads(raw)
    # Filter out issues that already have spec-created label
    return [
        i for i in issues
        if not any(l["name"] == "spec-created" for l in i.get("labels", []))
    ]


def extract_sections(body):
    """Try to extract structured content from the issue body."""
    if not body:
        return {"raw": ""}

    sections = {"raw": body}

    # Try to find common patterns people use in issues
    lines = body.split('\n')
    requirements = []
    constraints = []
    notes = []
    description_lines = []
    current_section = "description"

    for line in lines:
        lower = line.lower().strip()
        if lower.startswith('## requirement') or lower.startswith('### requirement'):
            current_section = "requirements"
            continue
        elif lower.startswith('## constraint') or lower.startswith('### constraint'):
            current_section = "constraints"
            continue
        elif lower.startswith('## note') or lower.startswith('### note'):
            current_section = "notes"
            continue
        elif lower.startswith('## ') or lower.startswith('### '):
            current_section = "notes"  # Unknown sections go to notes

        if current_section == "requirements":
            requirements.append(line)
        elif current_section == "constraints":
            constraints.append(line)
        elif current_section == "notes":
            notes.append(line)
        else:
            description_lines.append(line)

    sections["description"] = '\n'.join(description_lines).strip()
    sections["requirements"] = '\n'.join(requirements).strip()
    sections["constraints"] = '\n'.join(constraints).strip()
    sections["notes"] = '\n'.join(notes).strip()

    return sections


def generate_spec(issue):
    """Generate a spec file content from a GitHub Issue."""
    title = issue["title"]
    number = issue["number"]
    body = issue.get("body", "") or ""
    sections = extract_sections(body)

    parts = [f"# {title}"]
    parts.append("")
    parts.append(f"> Source: GitHub Issue #{number}")
    parts.append("")

    # Job To Be Done
    parts.append("## Job To Be Done")
    desc = sections.get("description", "").strip()
    if desc:
        # Use first sentence or paragraph as the JTBD
        first_para = desc.split('\n\n')[0].strip()
        parts.append(first_para)
    else:
        parts.append(f"<!-- Summarize the user outcome from Issue #{number} -->")
    parts.append("")

    # Requirements
    parts.append("## Requirements")
    reqs = sections.get("requirements", "").strip()
    if reqs:
        parts.append(reqs)
    elif desc:
        # Convert remaining description into requirement bullets
        remaining = desc.split('\n\n', 1)
        if len(remaining) > 1:
            for line in remaining[1].strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    if not line.startswith('- '):
                        line = f"- {line}"
                    parts.append(line)
        if len(parts) == 6:  # Only header added
            parts.append(f"<!-- Extract requirements from Issue #{number} -->")
    else:
        parts.append(f"<!-- Extract requirements from Issue #{number} -->")
    parts.append("")

    # Constraints
    parts.append("## Constraints")
    cons = sections.get("constraints", "").strip()
    if cons:
        parts.append(cons)
    else:
        parts.append("<!-- Add technical constraints if applicable -->")
    parts.append("")

    # Notes
    parts.append("## Notes")
    notes = sections.get("notes", "").strip()
    if notes:
        parts.append(notes)
    parts.append(f"- Triaged from GitHub Issue #{number}")
    parts.append("")

    return '\n'.join(parts)


def main():
    candidates = get_spec_candidates()

    if not candidates:
        print("No unprocessed spec-candidate issues found.")
        return

    print(f"Found {len(candidates)} spec-candidate issue(s) to triage")
    print("")

    created = 0

    for issue in candidates:
        number = issue["number"]
        title = issue["title"]
        slug = slugify(title)
        spec_path = f"specs/{slug}.md"

        # Check if spec file already exists
        if os.path.exists(spec_path):
            print(f"  skip: #{number} \"{title}\" → {spec_path} (file exists)")
            continue

        spec_content = generate_spec(issue)

        if DRY_RUN:
            print(f"  would create: #{number} \"{title}\" → {spec_path}")
            created += 1
            continue

        # Write spec file
        os.makedirs("specs", exist_ok=True)
        with open(spec_path, 'w') as f:
            f.write(spec_content)

        # Comment back on the GitHub Issue
        comment = (
            f"Spec created: [`{spec_path}`]"
            f"(../blob/main/{spec_path})\n\n"
            f"Run `./loop.sh plan` to decompose this spec into tasks."
        )
        run(['gh', 'issue', 'comment', str(number), '--body', comment])

        # Add spec-created label
        run(['gh', 'issue', 'edit', str(number), '--add-label', 'spec-created'])

        print(f"  created: #{number} \"{title}\" → {spec_path}")
        created += 1

    print("")
    print(f"Summary: {created} spec(s) {'would be ' if DRY_RUN else ''}created")

    if created > 0 and not DRY_RUN:
        print("")
        print("Next steps:")
        print("  1. Review the generated specs in specs/")
        print("  2. Run ./loop.sh plan to decompose into tasks")


if __name__ == "__main__":
    main()
PYEOF
