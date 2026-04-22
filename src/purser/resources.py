from __future__ import annotations

from importlib.resources import files
from pathlib import Path

PACKAGE_PROMPTS = {
    "planner": "planner.md",
    "executor": "executor.md",
    "reviewer": "reviewer.md",
}


def prompt_resource_text(name: str) -> str:
    return files("purser.prompts").joinpath(PACKAGE_PROMPTS[name]).read_text(encoding="utf-8")


def write_default_prompts(target_dir: Path) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for role, filename in PACKAGE_PROMPTS.items():
        path = target_dir / filename
        path.write_text(prompt_resource_text(role), encoding="utf-8")
        written.append(path)
    return written
