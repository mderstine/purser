from __future__ import annotations

from pathlib import Path
import json
import re


PURSER_AGENTS_BEGIN = "<!-- purser:agents begin -->"
PURSER_AGENTS_END = "<!-- purser:agents end -->"


def upsert_delimited_markdown_section(
    path: Path,
    *,
    begin_marker: str,
    end_marker: str,
    body: str,
    heading: str = "# Agent Instructions",
) -> bool:
    section = _delimited_section(begin_marker, end_marker, body)
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    pattern = re.compile(
        rf"{re.escape(begin_marker)}.*?{re.escape(end_marker)}", re.DOTALL
    )
    if pattern.search(original):
        updated = pattern.sub(section, original, count=1)
    else:
        stripped = original.rstrip()
        if stripped:
            updated = f"{stripped}\n\n{section}\n"
        else:
            updated = f"{heading}\n\n{section}\n"
    if updated == original:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")
    return True


def merge_pi_settings_prompts(path: Path, prompt_dir: str) -> bool:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    data: dict[str, object]
    if original.strip():
        loaded = json.loads(original)
        if not isinstance(loaded, dict):
            raise ValueError(f"Expected JSON object in {path}")
        data = dict(loaded)
    else:
        data = {}
    existing = data.get("prompts", [])
    prompts: list[str] = []
    if isinstance(existing, list):
        for item in existing:
            if isinstance(item, str) and item not in prompts:
                prompts.append(item)
    elif existing:
        raise ValueError(f"Expected 'prompts' to be a JSON array in {path}")
    if prompt_dir not in prompts:
        prompts.append(prompt_dir)
    data["prompts"] = prompts
    updated = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if updated == original:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")
    return True


def append_gitignore_entries(path: Path, entries: list[str]) -> bool:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    existing = {line.strip() for line in original.splitlines() if line.strip()}
    missing = [entry for entry in entries if entry.strip() and entry.strip() not in existing]
    if not missing:
        return False
    stripped = original.rstrip("\n")
    prefix = f"{stripped}\n" if stripped else ""
    separator = "\n" if stripped else ""
    updated = prefix + separator + "\n".join(missing) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")
    return True


def _delimited_section(begin_marker: str, end_marker: str, body: str) -> str:
    content = body.strip()
    return f"{begin_marker}\n{content}\n{end_marker}"
