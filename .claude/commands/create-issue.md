Create a new beads issue from the provided description.

1. Parse the request to determine title, description, priority (0-4), and type (task/bug/feature/epic/chore)
2. Check for duplicates: `bd list --status open --json`
3. Create the issue: `bd create "<title>" --description="<description>" -p <priority> -t <type> --json`
4. If related to existing work, add dependencies: `bd dep add <new-id> <related-id> --type <dep-type> --json`
5. Confirm by showing: `bd show <new-id> --json`

$ARGUMENTS
