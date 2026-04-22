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


class RoleExecutionError(RuntimeError):
    pass


class PiRunner:
    def __init__(self, root: Path) -> None:
        self.root = root

    def run_role(
        self,
        *,
        role: str,
        model: str,
        prompt_path: Path,
        message: str,
        tools: str | None = None,
        extra_args: list[str] | None = None,
    ) -> RoleResult:
        command = [
            "pi",
            "--model",
            model,
            "--mode",
            "json",
            "--print",
            "--no-session",
            "--append-system-prompt",
            str(prompt_path),
        ]
        if tools:
            command += ["--tools", tools]
        if extra_args:
            command += extra_args
        command.append(message)

        completed = subprocess.run(
            command,
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
        )
        transcript: list[dict] = []
        final_chunks: list[str] = []
        for line in completed.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            transcript.append(event)
            if event.get("type") == "message_update":
                delta = (((event.get("assistantMessageEvent") or {}).get("delta")) or "")
                if delta:
                    final_chunks.append(delta)
            elif event.get("type") == "message_end":
                message_obj = event.get("message") or {}
                if message_obj.get("role") == "assistant":
                    content = message_obj.get("content")
                    if isinstance(content, str):
                        final_chunks = [content]
        result = RoleResult(
            role=role,
            model=model,
            prompt_path=prompt_path,
            command=command,
            exit_code=completed.returncode,
            transcript=transcript,
            final_text="".join(final_chunks).strip(),
            stderr=completed.stderr.strip(),
        )
        if result.exit_code != 0:
            raise RoleExecutionError(result.stderr or f"pi failed for role {role}")
        return result
