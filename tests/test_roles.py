from purser.roles import _assistant_text_from_message, parse_json_mode_stdout


def test_assistant_text_from_string_content() -> None:
    assert _assistant_text_from_message({"role": "assistant", "content": "hello"}) == "hello"


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
    transcript, final_text = parse_json_mode_stdout(stdout)
    assert len(transcript) == 3
    assert final_text == "hello from end"


def test_parse_json_mode_stdout_falls_back_to_streamed_text() -> None:
    stdout = "\n".join(
        [
            '{"type":"message_update","assistantMessageEvent":{"delta":"hel"}}',
            '{"type":"message_update","assistantMessageEvent":{"delta":"lo"}}',
        ]
    )
    transcript, final_text = parse_json_mode_stdout(stdout)
    assert len(transcript) == 2
    assert final_text == "hello"
