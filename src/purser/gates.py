from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .config import PurserConfig
from .beads import BeadsClient


@dataclass(slots=True)
class GateResult:
    name: str
    command: str
    exit_code: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0

    def format_summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"[{status}] {self.name}\n"
            f"command: {self.command}\n"
            f"exit_code: {self.exit_code}\n\n"
            f"stdout:\n{self.stdout or '(empty)'}\n\n"
            f"stderr:\n{self.stderr or '(empty)'}"
        )


class GateFailure(RuntimeError):
    def __init__(self, result: GateResult) -> None:
        super().__init__(f"Gate failed: {result.name}")
        self.result = result


class GatesRunner:
    def __init__(self, root: Path, config: PurserConfig, beads: BeadsClient | None = None) -> None:
        self.root = root
        self.config = config
        self.beads = beads

    def run_all(self, bead_id: str | None = None) -> list[GateResult]:
        results: list[GateResult] = []
        for name, command in self.config.gates.commands():
            result = self.run_one(name, command)
            results.append(result)
            if bead_id and self.beads:
                self.beads.comment(bead_id, result.format_summary())
            if not result.passed:
                raise GateFailure(result)
        return results

    def run_one(self, name: str, command: str) -> GateResult:
        completed = subprocess.run(
            command,
            cwd=self.root,
            shell=True,
            text=True,
            capture_output=True,
            timeout=self.config.gates.timeout_seconds,
            check=False,
        )
        return GateResult(
            name=name,
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
        )
