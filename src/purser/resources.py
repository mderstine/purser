from __future__ import annotations

from importlib.resources import files
from pathlib import Path

ROLE_PROMPT_RESOURCES = {
    "planner": ("planner.md", Path("roles/planner-role.md")),
    "executor": ("executor.md", Path("roles/executor-role.md")),
    "reviewer": ("reviewer.md", Path("roles/reviewer-role.md")),
}

WORKFLOW_PROMPTS = {
    "purser-add-spec.md": """# purser-add-spec\n\nUse this workflow to create or refine a repo-local spec for the work to be done.\n\nRules:\n- stay in specification mode\n- write or refine a markdown spec under `specs/`\n- do not create beads\n- stop for human review before planning\n""",
    "purser-plan.md": """# purser-plan\n\nUse this workflow to plan an approved spec into atomic Beads.\n\nRules:\n- read the approved spec carefully\n- create actual beads and dependencies in Beads\n- do not implement source-code changes\n- keep beads atomic and verifiable\n""",
    "purser-build.md": """# purser-build\n\nUse this workflow to execute exactly one ready bead.\n\nRules:\n- work only one bead\n- keep scope narrow\n- run validation as required\n- do not silently expand scope\n""",
    "purser-build-all.md": """# purser-build-all\n\nUse this workflow to execute a sequential bead loop until no actionable work remains.\n\nRules:\n- execute one bead at a time\n- re-evaluate the graph after each bead\n- stop when blocked or when no ready work remains\n""",
}

PURSER_README = """# Purser local scaffold\n\nThis directory contains repo-local Purser artifacts.\n\nLayout:\n- `prompts/roles/`: runtime role prompts used internally by Purser\n- `prompts/workflows/`: operator workflow prompts intended for Pi prompt discovery\n\nTypical next steps:\n1. edit `.purser.toml` for this repo's real gates and model choices\n2. wire `.pi/settings.json` to `.purser/prompts/workflows`\n3. run `purser doctor`\n"""


def prompt_resource_text(name: str) -> str:
    resource_name, _ = ROLE_PROMPT_RESOURCES[name]
    return files("purser.prompts").joinpath(resource_name).read_text(encoding="utf-8")


def write_default_prompts(target_dir: Path, *, force: bool = False) -> list[Path]:
    written: list[Path] = []
    for role in ["planner", "executor", "reviewer"]:
        _, relative_path = ROLE_PROMPT_RESOURCES[role]
        path = target_dir / relative_path
        if path.exists() and not force:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(prompt_resource_text(role), encoding="utf-8")
        written.append(path)
    workflow_dir = target_dir / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in WORKFLOW_PROMPTS.items():
        path = workflow_dir / filename
        if path.exists() and not force:
            continue
        path.write_text(content.strip() + "\n", encoding="utf-8")
        written.append(path)
    return written


def write_scaffold_readme(path: Path, *, force: bool = False) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PURSER_README, encoding="utf-8")
    return True
