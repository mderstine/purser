from pathlib import Path
import subprocess

import pytest

from purser.runtime import BinaryStatus, ensure_local_beads_context, format_binary_status


def test_format_binary_status() -> None:
    text = format_binary_status(BinaryStatus(name="bd", path="/tmp/bd", version="1.0.0", ok=True))
    assert "bd: ok" in text
    assert "version=1.0.0" in text


def test_ensure_local_beads_context_accepts_embedded_repo_local(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    payload = {
        "beads_dir": str(tmp_path / ".beads"),
        "repo_root": str(tmp_path),
        "backend": "dolt",
        "dolt_mode": "embedded",
        "database": "demo",
        "role": "maintainer",
    }

    def fake_run(*args, **kwargs):
        del args, kwargs
        return subprocess.CompletedProcess(["bd"], 0, stdout=__import__("json").dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    context = ensure_local_beads_context(tmp_path)

    assert context.dolt_mode == "embedded"
    assert context.beads_dir == tmp_path / ".beads"


def test_ensure_local_beads_context_rejects_server_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    payload = {
        "beads_dir": str(tmp_path / ".beads"),
        "repo_root": str(tmp_path),
        "backend": "dolt",
        "dolt_mode": "server",
        "database": "beads_global",
        "role": "maintainer",
    }

    def fake_run(*args, **kwargs):
        del args, kwargs
        return subprocess.CompletedProcess(["bd"], 0, stdout=__import__("json").dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as exc:
        ensure_local_beads_context(tmp_path)

    assert "repo-local embedded" in str(exc.value)
