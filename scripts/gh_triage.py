"""Triage GitHub Issues labeled 'spec-candidate' into specs/ files.

This is the inbound flow: collaborators create GitHub Issues with the
'spec-candidate' label, and this script converts them to spec files
that the planning loop can decompose into beads tasks.
"""

import json
import os
import sys

from lib import run, slugify


def parse_args(argv):
    """Parse CLI arguments."""
    dry_run = "--dry-run" in argv
    return {"dry_run": dry_run}


def get_spec_candidates():
    """Get GitHub Issues labeled spec-candidate that don't have spec-created."""
    raw = run([
        'gh', 'issue', 'list', '--label', 'spec-candidate', '--state', 'open',
        '--limit', '100', '--json', 'number,title,body,labels'
    ])
    if not raw:
        return []
    issues = json.loads(raw)
    return [
        i for i in issues
        if not any(l["name"] == "spec-created" for l in i.get("labels", []))
    ]


def extract_sections(body):
    """Try to extract structured content from the issue body."""
    if not body:
        return {"raw": ""}

    sections = {"raw": body}

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
            current_section = "notes"

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

    parts.append("## Job To Be Done")
    desc = sections.get("description", "").strip()
    if desc:
        first_para = desc.split('\n\n')[0].strip()
        parts.append(first_para)
    else:
        parts.append(f"<!-- Summarize the user outcome from Issue #{number} -->")
    parts.append("")

    parts.append("## Requirements")
    reqs = sections.get("requirements", "").strip()
    if reqs:
        parts.append(reqs)
    elif desc:
        remaining = desc.split('\n\n', 1)
        if len(remaining) > 1:
            for line in remaining[1].strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    if not line.startswith('- '):
                        line = f"- {line}"
                    parts.append(line)
        if len(parts) == 6:
            parts.append(f"<!-- Extract requirements from Issue #{number} -->")
    else:
        parts.append(f"<!-- Extract requirements from Issue #{number} -->")
    parts.append("")

    parts.append("## Constraints")
    cons = sections.get("constraints", "").strip()
    if cons:
        parts.append(cons)
    else:
        parts.append("<!-- Add technical constraints if applicable -->")
    parts.append("")

    parts.append("## Notes")
    notes = sections.get("notes", "").strip()
    if notes:
        parts.append(notes)
    parts.append(f"- Triaged from GitHub Issue #{number}")
    parts.append("")

    return '\n'.join(parts)


def main():
    args = parse_args(sys.argv[1:])
    dry_run = args["dry_run"]

    print("=== GitHub Issue Triage -> Specs ===")
    if dry_run:
        print("(dry-run mode)")
    print("")

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

        if os.path.exists(spec_path):
            print(f"  skip: #{number} \"{title}\" -> {spec_path} (file exists)")
            continue

        spec_content = generate_spec(issue)

        if dry_run:
            print(f"  would create: #{number} \"{title}\" -> {spec_path}")
            created += 1
            continue

        os.makedirs("specs", exist_ok=True)
        with open(spec_path, 'w') as f:
            f.write(spec_content)

        comment = (
            f"Spec created: [`{spec_path}`]"
            f"(../blob/main/{spec_path})\n\n"
            f"Run `./loop.sh plan` to decompose this spec into tasks."
        )
        run(['gh', 'issue', 'comment', str(number), '--body', comment])

        run(['gh', 'issue', 'edit', str(number), '--add-label', 'spec-created'])

        print(f"  created: #{number} \"{title}\" -> {spec_path}")
        created += 1

    print("")
    print(f"Summary: {created} spec(s) {'would be ' if dry_run else ''}created")

    if created > 0 and not dry_run:
        print("")
        print("Next steps:")
        print("  1. Review the generated specs in specs/")
        print("  2. Run ./loop.sh plan to decompose into tasks")


if __name__ == "__main__":
    main()
