from pathlib import Path
import json

from purser.scaffold import (
    PURSER_AGENTS_BEGIN,
    PURSER_AGENTS_END,
    append_gitignore_entries,
    merge_pi_settings_prompts,
    upsert_delimited_markdown_section,
)


PURSER_BODY = "## Purser workflow\n\nPurser is tooling, not the repo product."


def test_upsert_delimited_markdown_section_creates_file_when_missing(
    tmp_path: Path,
) -> None:
    path = tmp_path / "AGENTS.md"

    changed = upsert_delimited_markdown_section(
        path,
        begin_marker=PURSER_AGENTS_BEGIN,
        end_marker=PURSER_AGENTS_END,
        body=PURSER_BODY,
    )

    assert changed is True
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Agent Instructions\n\n")
    assert PURSER_AGENTS_BEGIN in text
    assert PURSER_AGENTS_END in text
    assert "## Purser workflow" in text


def test_upsert_delimited_markdown_section_preserves_unrelated_content_and_replaces_owned_section(
    tmp_path: Path,
) -> None:
    path = tmp_path / "AGENTS.md"
    path.write_text(
        "# Agent Instructions\n\nKeep existing guidance.\n\n"
        f"{PURSER_AGENTS_BEGIN}\nold body\n{PURSER_AGENTS_END}\n",
        encoding="utf-8",
    )

    changed = upsert_delimited_markdown_section(
        path,
        begin_marker=PURSER_AGENTS_BEGIN,
        end_marker=PURSER_AGENTS_END,
        body=PURSER_BODY,
    )

    assert changed is True
    text = path.read_text(encoding="utf-8")
    assert "Keep existing guidance." in text
    assert "old body" not in text
    assert text.count(PURSER_AGENTS_BEGIN) == 1
    assert text.count(PURSER_AGENTS_END) == 1
    assert "## Purser workflow" in text


def test_upsert_delimited_markdown_section_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "AGENTS.md"

    first = upsert_delimited_markdown_section(
        path,
        begin_marker=PURSER_AGENTS_BEGIN,
        end_marker=PURSER_AGENTS_END,
        body=PURSER_BODY,
    )
    second = upsert_delimited_markdown_section(
        path,
        begin_marker=PURSER_AGENTS_BEGIN,
        end_marker=PURSER_AGENTS_END,
        body=PURSER_BODY,
    )

    assert first is True
    assert second is False


def test_merge_pi_settings_prompts_creates_file_when_missing(tmp_path: Path) -> None:
    path = tmp_path / ".pi/settings.json"

    changed = merge_pi_settings_prompts(path, "../.purser/prompts/workflows")

    assert changed is True
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"prompts": ["../.purser/prompts/workflows"]}


def test_merge_pi_settings_prompts_preserves_unrelated_keys_and_appends_once(
    tmp_path: Path,
) -> None:
    path = tmp_path / ".pi/settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"theme": "dark", "prompts": ["../existing"]}, indent=2) + "\n",
        encoding="utf-8",
    )

    first = merge_pi_settings_prompts(path, "../.purser/prompts/workflows")
    second = merge_pi_settings_prompts(path, "../.purser/prompts/workflows")

    data = json.loads(path.read_text(encoding="utf-8"))
    assert first is True
    assert second is False
    assert data["theme"] == "dark"
    assert data["prompts"] == ["../existing", "../.purser/prompts/workflows"]


def test_append_gitignore_entries_adds_only_missing_entries(tmp_path: Path) -> None:
    path = tmp_path / ".gitignore"
    path.write_text(".venv/\n.purser/\n", encoding="utf-8")

    first = append_gitignore_entries(path, [".purser/", ".beads/", "VALIDATION.md"])
    second = append_gitignore_entries(path, [".purser/", ".beads/", "VALIDATION.md"])

    text = path.read_text(encoding="utf-8")
    assert first is True
    assert second is False
    assert text.splitlines() == [".venv/", ".purser/", "", ".beads/", "VALIDATION.md"]
