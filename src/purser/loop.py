from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .beads import Bead, BeadsClient, BeadsError
from .config import PurserConfig
from .gates import GateFailure, GatesRunner
from .roles import PiRunner, RoleResult
from .validation import ValidationRecord, append_validation_log, verification_items_from_gates


@dataclass(slots=True)
class LoopRunResult:
    status: str
    processed_beads: list[str]


class PurserLoop:
    def __init__(self, config: PurserConfig) -> None:
        self.config = config
        self.root = config.root
        self.beads = BeadsClient(self.root, auto_commit=config.beads.auto_commit)
        self.pi = PiRunner(self.root)
        self.gates = GatesRunner(self.root, config, beads=self.beads)

    def run_once(self, bead_id: str | None = None) -> str:
        bead = self.beads.show(bead_id) if bead_id else self._next_review_or_ready_bead()
        if bead is None:
            return "done"
        if bead.normalized_status == "in_review":
            self._review(bead)
            return bead.id
        claimed = bead if bead.normalized_status == "in_progress" else self.beads.claim(bead.id)
        self._execute(claimed)
        self._review(self.beads.show(claimed.id))
        return claimed.id

    def run_all(self) -> LoopRunResult:
        processed: list[str] = []
        while True:
            bead = self._next_review_or_ready_bead()
            if bead is None:
                return LoopRunResult(status="done", processed_beads=processed)
            attempts = int(bead.metadata.get("purser_executor_attempts", 0))
            if attempts >= self.config.loop.max_iterations_per_bead:
                self.beads.update_status(bead.id, "blocked", notes="purser iteration cap hit")
                processed.append(bead.id)
                continue
            processed.append(self.run_once(bead.id))

    def _next_review_or_ready_bead(self) -> Bead | None:
        in_review = self.beads.list_by_statuses(["in_review"])
        if in_review:
            return in_review[0]
        ready = self.beads.ready(limit=1)
        return ready[0] if ready else None

    def _execute(self, bead: Bead) -> RoleResult:
        prompt_path = self.config.prompt_path("executor")
        if prompt_path is None:
            raise RuntimeError("executor prompt path is required; run `purser init` or configure [roles].executor_prompt")
        message = (
            f"Execute bead {bead.id}.\n"
            "Run `bd show <id> --json` and read the bead carefully.\n"
            "Implement only the bead's acceptance criteria.\n"
            "Run the configured gates until all pass.\n"
            "When done, move the bead to in-review.\n"
            "Do not close the bead."
        )
        bead = self.beads.increment_attempts(bead.id)
        result = self.pi.run_role(
            role="executor",
            model=self.config.roles.models.executor,
            prompt_path=prompt_path,
            message=message,
        )
        updated = self.beads.show(bead.id)
        if updated.normalized_status == "closed":
            self.beads.reopen(bead.id, reason="purser executor may not self-close")
            raise BeadsError(f"Executor illegally closed bead {bead.id}")
        if updated.normalized_status not in {"in_review", "in_progress"}:
            self.beads.update_status(bead.id, "in_review", notes="purser normalized executor completion")
            updated = self.beads.show(bead.id)
        try:
            self.gates.run_all(bead.id)
        except GateFailure as error:
            self.beads.update_status(bead.id, "open", notes=error.result.format_summary())
            raise
        if updated.normalized_status != "in_review":
            self.beads.update_status(bead.id, "in_review", notes="purser advanced bead to review after green gates")
        return result

    def _review(self, bead: Bead) -> RoleResult:
        prompt_path = self.config.prompt_path("reviewer")
        if prompt_path is None:
            raise RuntimeError("reviewer prompt path is required; run `purser init` or configure [roles].reviewer_prompt")
        message = (
            f"Review bead {bead.id}.\n"
            "Your job is to validate accuracy, atomicity, and elegance against the spec and acceptance criteria.\n"
            "Re-read the bead, inspect the codebase, and run the gates.\n"
            "If the work is correct, complete, and cohesive, close the bead and summarize why.\n"
            "If not, reopen or move it to open with a concrete rejection note.\n"
            "Do not edit source files."
        )
        result = self.pi.run_role(
            role="reviewer",
            model=self.config.roles.models.reviewer,
            prompt_path=prompt_path,
            message=message,
            tools="read,bash,grep,find,ls",
        )
        try:
            gate_results = self.gates.run_all(bead.id)
        except GateFailure as error:
            self.beads.update_status(bead.id, "open", notes=error.result.format_summary())
            return result
        current = self.beads.show(bead.id)
        if current.normalized_status != "closed":
            summary = result.final_text or "Reviewer requested changes"
            self.beads.update_status(bead.id, "open", notes=summary)
            return result
        record = ValidationRecord(
            bead_id=current.id,
            title=current.title,
            spec_reference=str(current.raw.get("spec_id") or "n/a"),
            summary=result.final_text or "Closed by reviewer",
            verification_items=verification_items_from_gates(gate_results),
            notes=["Reviewed by purser reviewer role"],
            executor_attempts=int(current.metadata.get("purser_executor_attempts", 1)),
            commits=[],
        )
        append_validation_log(self.config.validation_log_path, record)
        return result
