#!/usr/bin/env python3
"""
add_spec.py: Draft a polished spec from a user prompt and save to specs/ directory.
"""
import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import slugify

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
        print("Usage: add_spec.py <title> <description>")
        sys.exit(1)
    title = sys.argv[1]
    description = sys.argv[2]
    slug = slugify(title)
    out_path = os.path.join('specs', f'{slug}.md')
    os.makedirs('specs', exist_ok=True)
    with open(out_path, 'w') as f:
        f.write(draft_spec(title, description))
    print(f"Spec saved to {out_path}")

if __name__ == "__main__":
    main()
