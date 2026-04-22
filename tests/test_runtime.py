from purser.runtime import BinaryStatus, format_binary_status


def test_format_binary_status() -> None:
    text = format_binary_status(BinaryStatus(name="bd", path="/tmp/bd", version="1.0.0", ok=True))
    assert "bd: ok" in text
    assert "version=1.0.0" in text
