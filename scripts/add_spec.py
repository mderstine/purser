#!/usr/bin/env python3
"""
add_spec.py: Draft a polished spec from a user prompt and save to specs/ directory.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cli_utils import setup_logging  # noqa: E402
from lib import slugify  # noqa: E402

logger = setup_logging(__name__)


def draft_spec(title, description):
    today = date.today().isoformat()
    return f"""# {title}

**Date:** {today}

## Overview
{description}

## Requirements
- Clearly describe the desired outcome
- List any constraints or edge cases
- Define acceptance criteria

## Rationale
- Why is this needed?
- What value does it provide?

## Open Questions
- ...
"""


def main():
    if len(sys.argv) < 3:
        logger.error("Usage: add_spec.py <title> <description>")
        sys.exit(1)
    title = sys.argv[1]
    description = sys.argv[2]
    slug = slugify(title)
    out_path = Path("specs") / f"{slug}.md"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        f.write(draft_spec(title, description))
    logger.info("Spec saved to %s", out_path)


if __name__ == "__main__":
    main()
