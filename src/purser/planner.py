from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .beads import BeadsClient
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
        self.beads = BeadsClient(config.root, auto_commit=config.beads.auto_commit)

    def intake_spec(
        self, spec_path: Path, synthesize: bool = False, output_path: Path | None = None
    ) -> IntakeResult:
        prompt_path = self._planner_prompt_path()
        spec_abs = self._resolve_spec_path(spec_path)
        result = self.pi.run_role(
            role="planner",
            model=self.config.roles.models.planner,
            prompt_path=prompt_path,
            message=self._intake_message(spec_abs, synthesize=synthesize),
            timeout_seconds=self.config.roles.timeout_seconds,
        )
        target_path: Path | None = None
        if synthesize:
            target_path = output_path or (
                self.config.spec_output_dir_path / f"{spec_abs.stem}.synthesized.md"
            )
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(result.final_text.rstrip() + "\n", encoding="utf-8")
        return IntakeResult(
            source_spec=spec_abs,
            synthesized=synthesize,
            output_path=target_path,
            role_result=result,
        )

    def plan_spec(self, spec_path: Path) -> RoleResult:
        prompt_path = self._planner_prompt_path()
        spec_abs = self._resolve_spec_path(spec_path)
        before_ids = {bead.id for bead in self.beads.list_all()}
        result = self.pi.run_role(
            role="planner",
            model=self.config.roles.models.planner,
            prompt_path=prompt_path,
            message=self._plan_message(spec_abs),
            tools="read,bash,grep,find,ls",
            timeout_seconds=self.config.roles.timeout_seconds,
        )
        after_beads = self.beads.list_all()
        after_ids = {bead.id for bead in after_beads}
        created_ids = sorted(after_ids - before_ids)
        if not created_ids:
            summary = result.final_text.strip()
            raise RuntimeError(
                "planner did not create any beads in Beads; "
                "planning must mutate the local Beads database via bd create/bd dep. "
                f"Planner summary: {summary}"
            )
        created_beads = [bead for bead in after_beads if bead.id in created_ids]
        missing_spec = [
            bead.id
            for bead in created_beads
            if str(bead.raw.get("spec_id") or "").strip() != str(spec_abs)
        ]
        weak_acceptance = [
            bead.id
            for bead in created_beads
            if not str(bead.raw.get("acceptance_criteria") or "").strip()
        ]
        if missing_spec or weak_acceptance:
            problems: list[str] = []
            if missing_spec:
                problems.append(
                    f"missing/incorrect spec_id on beads: {', '.join(missing_spec)}"
                )
            if weak_acceptance:
                problems.append(
                    f"missing acceptance criteria on beads: {', '.join(weak_acceptance)}"
                )
            raise RuntimeError(
                "planner created beads but did not satisfy the Beads planning contract; "
                + "; ".join(problems)
            )
        return result

    def _planner_prompt_path(self) -> Path:
        prompt_path = self.config.prompt_path("planner")
        if prompt_path is None:
            raise RuntimeError(
                "planner prompt path is required; run `purser init` or configure [roles].planner_prompt"
            )
        if not prompt_path.exists():
            raise FileNotFoundError(prompt_path)
        return prompt_path

    def _resolve_spec_path(self, spec_path: Path) -> Path:
        resolved = (
            (self.config.root / spec_path).resolve()
            if not spec_path.is_absolute()
            else spec_path.resolve()
        )
        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(resolved)
        return resolved

    def _intake_message(self, spec_abs: Path, *, synthesize: bool) -> str:
        return (
            f"Planner intake for spec: {spec_abs}\n"
            f"Synthesize: {'true' if synthesize else 'false'}\n\n"
            "Read the spec and produce:\n"
            "1. A readiness assessment.\n"
            "2. Any ambiguities or missing decisions.\n"
            "3. If synthesize=true, produce improved markdown that is clearer, more testable, and easier to decompose.\n"
            "4. Do not create beads yet."
        )

    def _plan_message(self, spec_abs: Path) -> str:
        approval_line = (
            "Human approval is required before implementation; optimize for a reviewable plan summary.\n"
            if self.config.loop.human_approve_plan
            else "Human approval is disabled; proceed with autonomous planning.\n"
        )
        return (
            f"Plan spec: {spec_abs}\n\n"
            "Read the full spec and decompose it into atomic beads in Beads.\n"
            "You must actually create the beads in the local Beads database during this run using bd create and bd dep.\n"
            f"Every created bead must include --spec-id {spec_abs}.\n"
            "Create open beads with clear titles, descriptions, acceptance criteria, and dependency edges.\n"
            "Preserve exact literals from the spec in acceptance criteria when they matter (file names, exact output strings, exact commands, exact paths).\n"
            "Use discovered-from dependencies when scope spillover appears.\n"
            "Do not execute source-code work. Only plan and create/update beads.\n"
            "Do not stop at prose. A textual plan without Beads mutations is a failure.\n"
            f"{approval_line}"
            "At the end, provide a concise summary of the created bead graph, key sequencing choices, and any ambiguities that still need human input."
        )
