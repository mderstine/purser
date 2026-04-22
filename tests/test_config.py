from pathlib import Path

from purser.config import load_config


def test_load_config(tmp_path: Path) -> None:
    (tmp_path / ".purser.toml").write_text(
        """
[project]
name = "demo"
language = "python"

[gates]
lint = "ruff check ."
types = "python3 -m pyright"
tests = "python3 -m pytest"
timeout_seconds = 120

[roles]
planner_prompt = ".purser/prompts/planner.md"
executor_prompt = ".purser/prompts/executor.md"
reviewer_prompt = ".purser/prompts/reviewer.md"
""",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    assert config.project.name == "demo"
    assert config.gates.timeout_seconds == 120
    assert config.prompt_path("planner") == tmp_path / ".purser/prompts/planner.md"
