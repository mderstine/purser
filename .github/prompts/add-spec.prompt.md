---
mode: agent
description: Create a new spec file in specs/ from the provided description.
tools:
  - read
  - edit
  - search
---

Create a new spec file in `specs/` from the provided description: ${input:description}

A spec represents one "topic of concern" — a distinct aspect of the project that can be described in one sentence without using "and". If the request covers multiple topics, create separate spec files.

Each spec should follow this structure:

```markdown
# <Topic Name>

## Job To Be Done
<One sentence describing the user outcome>

## Requirements
- <Specific, testable requirement>
- <Include inputs, outputs, error cases>
- <State acceptance criteria>

## Constraints
- <Technical constraints: database, framework, API format>
- <Performance requirements if any>

## Notes
- <Context that helps implementation>
```

After creating the spec file(s), suggest running `/plan` to generate the task graph.
