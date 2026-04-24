from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import subprocess


@dataclass(slots=True)
class RoleResult:
    role: str
    model: str
    prompt_path: Path
    command: list[str]
    exit_code: int
    transcript: list[dict]
    final_text: str
    stderr: str
    stdout: str
    provider_error: str = ""

    @property
    def had_events(self) -> bool:
        return bool(self.transcript)


class RoleExecutionError(RuntimeError):
    pass


class RoleProtocolError(RoleExecutionError):
    pass


def parse_json_mode_stdout(stdout: str) -> tuple[list[dict], str, str]:
    transcript: list[dict] = []
    final_text = ""
    provider_error = ""
    streamed_chunks: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        transcript.append(event)
        event_type = event.get("type")
        if event_type == "message_update":
            delta = ((event.get("assistantMessageEvent") or {}).get("delta")) or ""
            if isinstance(delta, str) and delta:
                streamed_chunks.append(delta)
        elif event_type == "message_end":
            message = event.get("message")
            text = _assistant_text_from_message(message)
            if text:
                final_text = text
            elif not provider_error:
                provider_error = _assistant_error_from_message(message)
        elif event_type == "turn_end":
            message = event.get("message")
            text = _assistant_text_from_message(message)
            if text:
                final_text = text
            elif not provider_error:
                provider_error = _assistant_error_from_message(message)
        elif event_type == "agent_end":
            for message in reversed(event.get("messages") or []):
                text = _assistant_text_from_message(message)
                if text and not final_text:
                    final_text = text
                    break
                if not provider_error:
                    provider_error = _assistant_error_from_message(message)
    return (
        transcript,
        (final_text or "".join(streamed_chunks).strip()),
        provider_error.strip(),
    )


def _assistant_text_from_message(message: object) -> str:
    if not isinstance(message, dict) or message.get("role") != "assistant":
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts).strip()
    return ""


def _assistant_error_from_message(message: object) -> str:
    if not isinstance(message, dict) or message.get("role") != "assistant":
        return ""
    error_message = message.get("errorMessage")
    return error_message.strip() if isinstance(error_message, str) else ""


class PiRunner:
    def __init__(self, root: Path) -> None:
        self.root = root

    def run_role(
        self,
        *,
        role: str,
        model: str | None,
        prompt_path: Path,
        message: str,
        tools: str | None = None,
        extra_args: list[str] | None = None,
        timeout_seconds: int | None = None,
    ) -> RoleResult:
        command = [
            "pi",
            "--mode",
            "json",
            "--print",
            "--no-session",
            "--append-system-prompt",
            str(prompt_path),
        ]
        if model:
            command[1:1] = ["--model", model]
        if tools:
            command += ["--tools", tools]
        if extra_args:
            command += extra_args
        command.append(message)

        try:
            completed = subprocess.run(
                command,
                cwd=self.root,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise RoleExecutionError(
                f"pi timed out for role {role} after {timeout_seconds}s"
            ) from exc
        transcript, final_text, provider_error = parse_json_mode_stdout(
            completed.stdout
        )
        result = RoleResult(
            role=role,
            model=model or "<pi-default>",
            prompt_path=prompt_path,
            command=command,
            exit_code=completed.returncode,
            transcript=transcript,
            final_text=final_text,
            stderr=completed.stderr.strip(),
            stdout=completed.stdout,
            provider_error=provider_error,
        )
        if result.exit_code != 0:
            raise RoleExecutionError(
                result.provider_error or result.stderr or f"pi failed for role {role}"
            )
        if not result.had_events:
            raise RoleProtocolError(f"pi returned no JSON events for role {role}")
        if not result.final_text:
            raise RoleProtocolError(
                result.provider_error
                or f"pi returned no final assistant text for role {role}"
            )
        return result
