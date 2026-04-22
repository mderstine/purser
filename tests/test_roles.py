import subprocess
from pathlib import Path

import pytest

from purser.roles import (
    PiRunner,
    RoleExecutionError,
    _assistant_text_from_message,
    parse_json_mode_stdout,
)


def test_assistant_text_from_string_content() -> None:
    assert (
        _assistant_text_from_message({"role": "assistant", "content": "hello"})
        == "hello"
    )


def test_assistant_text_from_list_content() -> None:
    message = {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "hello"},
            {"type": "text", "text": " world"},
        ],
    }
    assert _assistant_text_from_message(message) == "hello world"


def test_parse_json_mode_stdout_prefers_message_end() -> None:
    stdout = "\n".join(
        [
            '{"type":"message_update","assistantMessageEvent":{"delta":"hel"}}',
            '{"type":"message_update","assistantMessageEvent":{"delta":"lo"}}',
            '{"type":"message_end","message":{"role":"assistant","content":"hello from end"}}',
        ]
    )
    transcript, final_text, provider_error = parse_json_mode_stdout(stdout)
    assert len(transcript) == 3
    assert final_text == "hello from end"
    assert provider_error == ""


def test_parse_json_mode_stdout_falls_back_to_streamed_text() -> None:
    stdout = "\n".join(
        [
            '{"type":"message_update","assistantMessageEvent":{"delta":"hel"}}',
            '{"type":"message_update","assistantMessageEvent":{"delta":"lo"}}',
        ]
    )
    transcript, final_text, provider_error = parse_json_mode_stdout(stdout)
    assert len(transcript) == 2
    assert final_text == "hello"
    assert provider_error == ""


def test_parse_json_mode_stdout_extracts_provider_error() -> None:
    stdout = "\n".join(
        [
            '{"type":"message_end","message":{"role":"assistant","content":[],"errorMessage":"provider exploded"}}',
            '{"type":"agent_end","messages":[{"role":"assistant","content":[],"errorMessage":"provider exploded"}]}',
        ]
    )
    transcript, final_text, provider_error = parse_json_mode_stdout(stdout)
    assert len(transcript) == 2
    assert final_text == ""
    assert provider_error == "provider exploded"


def test_pi_runner_timeout_surfaces_clean_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = PiRunner(tmp_path)

    def fake_run(*args, **kwargs):
        del args, kwargs
        raise subprocess.TimeoutExpired(cmd=["pi"], timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RoleExecutionError) as exc:
        runner.run_role(
            role="executor",
            model="ollama/qwen3.5:397b-cloud",
            prompt_path=tmp_path / "executor.md",
            message="hi",
            timeout_seconds=1,
        )

    assert "timed out" in str(exc.value)
