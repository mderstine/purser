from pathlib import Path

from purser.detect import detect_init_profile


def test_detect_init_profile_prefers_uv_python_with_ty_when_signals_are_strong(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='demo'\n\n[dependency-groups]\ndev=['ty','ruff']\n",
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")

    profile = detect_init_profile(tmp_path)

    assert profile.language == "python"
    assert profile.lint == "uv run ruff check . && uv run ruff format --check ."
    assert profile.types == "uv run ty check"
    assert profile.tests == "uv run pytest -x --tb=short"


def test_detect_init_profile_uses_pyright_for_uv_python_without_ty(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='demo'\n\n[dependency-groups]\ndev=['ruff']\n",
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")

    profile = detect_init_profile(tmp_path)

    assert profile.language == "python"
    assert profile.types == "uv run pyright"


def test_detect_init_profile_falls_back_conservatively_for_python_without_strong_uv_signals(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='demo'\n", encoding="utf-8"
    )

    profile = detect_init_profile(tmp_path)

    assert profile.language == "python"
    assert profile.lint == "ruff check . && ruff format --check ."
    assert profile.types == "python3 -m pyright"
    assert profile.tests == "python3 -m pytest -x --tb=short"


def test_detect_init_profile_uses_package_json_scripts_when_present(
    tmp_path: Path,
) -> None:
    (tmp_path / "package.json").write_text(
        '{"scripts":{"lint":"eslint .","typecheck":"tsc --noEmit","test":"vitest"}}',
        encoding="utf-8",
    )

    profile = detect_init_profile(tmp_path)

    assert profile.language == "node"
    assert profile.lint == "npm run lint"
    assert profile.types == "npm run typecheck"
    assert profile.tests == "npm test"


def test_detect_init_profile_unknown_repo_is_safe(tmp_path: Path) -> None:
    profile = detect_init_profile(tmp_path)

    assert profile.language == "unknown"
    assert profile.lint == ""
    assert profile.types == ""
    assert profile.tests == ""
