from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import PurserConfig
from .roles import PiRunner, RoleResult


@dataclass(slots=True)
class IntakeResult:
    source_spec: Path
    synthesized: bool
    output_path: Path | None
    role_result: RoleResult


class PlannerService:
    def __init__(self, config: PurserConfig) -> None:
        self.config = config
        self.pi = PiRunner(config.root)

    def intake_spec(self, spec_path: Path, synthesize: bool = False, output_path: Path | None = None) -> IntakeResult:
        prompt_path = self.config.prompt_path("planner")
        if prompt_path is None:
            raise RuntimeError("planner prompt path is required; run `purser init` or configure [roles].planner_prompt")
        spec_abs = (self.config.root / spec_path).resolve() if not spec_path.is_absolute() else spec_path
        if not spec_abs.exists():
            raise FileNotFoundError(spec_abs)
        message = (
            f"Planner intake for spec: {spec_abs}\n"
            f"Synthesize: {'true' if synthesize else 'false'}\n\n"
            "Read the spec and produce:\n"
            "1. A readiness assessment.\n"
            "2. Any ambiguities or missing decisions.\n"
            "3. If synthesize=true, write an improved spec markdown file and state the path you wrote.\n"
            "4. Do not create beads yet."
        )
        result = self.pi.run_role(
            role="planner",
            model=self.config.roles.models.planner,
            prompt_path=prompt_path,
            message=message,
        )
        target_path: Path | None = None
        if synthesize:
            target_path = output_path or (self.config.spec_output_dir_path / f"{spec_abs.stem}.synthesized.md")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if result.final_text:
                target_path.write_text(result.final_text + "\n", encoding="utf-8")
        return IntakeResult(source_spec=spec_abs, synthesized=synthesize, output_path=target_path, role_result=result)

    def plan_spec(self, spec_path: Path) -> RoleResult:
        prompt_path = self.config.prompt_path("planner")
        if prompt_path is None:
            raise RuntimeError("planner prompt path is required; run `purser init` or configure [roles].planner_prompt")
        spec_abs = (self.config.root / spec_path).resolve() if not spec_path.is_absolute() else spec_path
        message = (
            f"Plan spec: {spec_abs}\n\n"
            "Read the full spec and decompose it into atomic beads in Beads.\n"
            "Create open beads with clear titles, descriptions, acceptance criteria, and dependency edges.\n"
            "Use discovered-from dependencies when scope spillover appears.\n"
            "Do not execute source-code work. Only plan and create/update beads.\n"
            "At the end, provide a concise summary of the created bead graph."
        )
        return self.pi.run_role(
            role="planner",
            model=self.config.roles.models.planner,
            prompt_path=prompt_path,
            message=message,
        )
