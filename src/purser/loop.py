from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

from .artifacts import RunArtifacts
from .beads import Bead, BeadsClient, BeadsError, is_review_ready
from .config import PurserConfig
from .gates import GateFailure, GatesRunner
from .outcomes import (
    EXECUTOR_OUTCOME_SCHEMA,
    REVIEWER_OUTCOME_SCHEMA,
    OutcomeProtocolError,
    parse_executor_outcome,
    parse_reviewer_outcome,
)
from .roles import PiRunner, RoleExecutionError, RoleResult
from .validation import (
    ValidationRecord,
    append_validation_log,
    verification_items_from_gates,
)


@dataclass(slots=True)
class LoopRunResult:
    status: str
    processed_beads: list[str]


MAX_OUTCOME_REPAIR_ATTEMPTS = 1


class PurserLoop:
    def __init__(self, config: PurserConfig) -> None:
        self.config = config
        self.root = config.root
        self.beads = BeadsClient(self.root, auto_commit=config.beads.auto_commit)
        self.pi = PiRunner(self.root)
        self.gates = GatesRunner(self.root, config, beads=self.beads)
        self.artifacts = RunArtifacts(self.root)

    def run_once(self, bead_id: str | None = None) -> str:
        bead = (
            self.beads.show(bead_id) if bead_id else self._next_review_or_ready_bead()
        )
        if bead is None:
            return "done"
        if is_review_ready(bead):
            self._review(bead)
            return bead.id
        claimed = (
            bead
            if bead.normalized_status == "in_progress"
            else self.beads.claim(bead.id)
        )
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
                self.beads.update_status(
                    bead.id, "blocked", notes="purser iteration cap hit"
                )
                processed.append(bead.id)
                continue
            processed.append(self.run_once(bead.id))

    def _next_review_or_ready_bead(self) -> Bead | None:
        review_ready = self.beads.list_review_ready()
        if review_ready:
            return review_ready[0]
        ready = self.beads.ready(limit=1)
        return ready[0] if ready else None

    def _execute(self, bead: Bead) -> RoleResult:
        prompt_path = self.config.prompt_path("executor")
        if prompt_path is None:
            raise RuntimeError(
                "executor prompt path is required; run `purser init` or configure [roles].executor_prompt"
            )
        spec_reference = str(bead.raw.get("spec_id") or "").strip()
        spec_line = (
            f"The originating spec is: {spec_reference}. Read it and preserve exact literals from it.\n"
            if spec_reference
            else "If the bead omits exact literals needed to implement correctly, do not guess: add a concrete clarification note and report a blocked outcome for Purser to handle.\n"
        )
        message = (
            f"Execute bead {bead.id}.\n"
            "Run `bd show <id> --json` and read the bead carefully.\n"
            f"{spec_line}"
            "Implement only the bead's acceptance criteria.\n"
            "Treat exact file names, exact strings, exact paths, and exact commands as binding requirements, not loose intent.\n"
            "If the bead/spec is too ambiguous to implement faithfully, do not guess; leave a concrete clarification note in Beads instead of fabricating details.\n"
            "Run the configured gates until all pass.\n"
            "When done, leave the bead in progress/open for Purser to mark review-ready.\n"
            "Do not close, reopen, or otherwise change bead lifecycle state; Purser owns lifecycle transitions.\n"
            "At the end, return a JSON structured outcome with these fields exactly: status, bead_id, files_touched, new_beads, gates_run, ready_for_review, summary, blocking_reason.\n"
            "Use status completed, blocked, or failed. Use blocking_reason null unless work is blocked or failed."
        )
        bead = self.beads.increment_attempts(bead.id)
        result = self.pi.run_role(
            role="executor",
            model=self.config.roles.resolved_model("executor"),
            prompt_path=prompt_path,
            message=message,
            timeout_seconds=self.config.roles.timeout_seconds,
        )
        outcome, errors, repair_attempts = self._parse_outcome_with_repair(
            kind="executor",
            bead_id=bead.id,
            role_result=result,
            prompt_path=prompt_path,
            parser=parse_executor_outcome,
            schema=EXECUTOR_OUTCOME_SCHEMA,
        )
        updated = self.beads.show(bead.id)
        if outcome is None:
            self.artifacts.write_role_artifact(
                kind="executor",
                bead_id=bead.id,
                role_result=result,
                structured_outcome=None,
                state={
                    "status_before": bead.normalized_status,
                    "status_after": updated.normalized_status,
                },
                errors=errors,
                extra={"repair_attempts": repair_attempts},
            )
            raise RuntimeError(errors[0])
        if outcome.bead_id != bead.id:
            message = f"executor structured outcome bead_id mismatch: expected {bead.id}, got {outcome.bead_id}"
            self.artifacts.write_role_artifact(
                kind="executor",
                bead_id=bead.id,
                role_result=result,
                structured_outcome=outcome,
                state={
                    "status_before": bead.normalized_status,
                    "status_after": updated.normalized_status,
                },
                errors=[message],
                extra={"repair_attempts": repair_attempts},
            )
            raise RuntimeError(message)
        if not outcome.ready_for_review:
            message = f"executor structured outcome must set ready_for_review=true for bead {bead.id}"
            self.artifacts.write_role_artifact(
                kind="executor",
                bead_id=bead.id,
                role_result=result,
                structured_outcome=outcome,
                state={
                    "status_before": bead.normalized_status,
                    "status_after": updated.normalized_status,
                },
                errors=[message],
                extra={"repair_attempts": repair_attempts},
            )
            raise RuntimeError(message)
        if updated.normalized_status == "closed":
            self.beads.reopen(bead.id, reason="purser executor may not self-close")
            latest = self.beads.show(bead.id)
            message = f"Executor illegally closed bead {bead.id}"
            self.artifacts.write_role_artifact(
                kind="executor",
                bead_id=bead.id,
                role_result=result,
                structured_outcome=outcome,
                state={
                    "status_before": bead.normalized_status,
                    "status_after": latest.normalized_status,
                },
                errors=[message],
                extra={"repair_attempts": repair_attempts},
            )
            raise BeadsError(message)
        if updated.normalized_status not in {"in_review", "in_progress"}:
            self.beads.update_status(
                bead.id, "in_progress", notes="purser normalized executor completion"
            )
            updated = self.beads.show(bead.id)
        gate_results = []
        gate_failure = None
        try:
            gate_results = self.gates.run_all(bead.id)
        except GateFailure as error:
            gate_failure = error.result
            self.beads.mark_review_ready(bead.id, ready=False)
            self.beads.update_status(
                bead.id, "open", notes=error.result.format_summary()
            )
            latest = self.beads.show(bead.id)
            self.artifacts.write_role_artifact(
                kind="executor",
                bead_id=bead.id,
                role_result=result,
                structured_outcome=outcome,
                gate_results=gate_results,
                gate_failure=gate_failure,
                state={
                    "status_before": bead.normalized_status,
                    "status_after": latest.normalized_status,
                },
                errors=[f"gate failed: {error.result.name}"],
                extra={"repair_attempts": repair_attempts},
            )
            raise
        final_bead = self.beads.show(bead.id)
        if final_bead.normalized_status not in {"in_review", "in_progress"}:
            final_bead = self.beads.update_status(
                bead.id,
                "in_progress",
                notes="purser kept bead active after green gates",
            )
        final_bead = self.beads.mark_review_ready(bead.id, ready=True)
        self.artifacts.write_role_artifact(
            kind="executor",
            bead_id=bead.id,
            role_result=result,
            structured_outcome=outcome,
            gate_results=gate_results,
            state={
                "status_before": bead.normalized_status,
                "status_after": final_bead.normalized_status,
            },
            extra={"repair_attempts": repair_attempts},
        )
        return result

    def _parse_outcome_with_repair(
        self,
        *,
        kind: str,
        bead_id: str,
        role_result: RoleResult,
        prompt_path: Path,
        parser: Callable[[str], Any],
        schema: dict[str, Any],
    ) -> tuple[Any | None, list[str], list[dict[str, object]]]:
        errors: list[str] = []
        repair_attempts: list[dict[str, object]] = []
        try:
            return parser(role_result.final_text), errors, repair_attempts
        except OutcomeProtocolError as exc:
            first_error = f"{kind} did not return a valid structured outcome payload: {exc}"
            errors.append(first_error)

        for attempt in range(1, MAX_OUTCOME_REPAIR_ATTEMPTS + 1):
            repair_record: dict[str, object] = {
                "attempt": attempt,
                "role": f"{kind}-outcome-repair",
            }
            try:
                repair_result = self.pi.run_role(
                    role=f"{kind}-outcome-repair",
                    model=self.config.roles.resolved_model(kind),
                    prompt_path=prompt_path,
                    message=self._outcome_repair_message(
                        kind=kind,
                        bead_id=bead_id,
                        schema=schema,
                        error=errors[-1],
                        role_result=role_result,
                    ),
                    timeout_seconds=self.config.roles.timeout_seconds,
                )
            except RoleExecutionError as exc:
                repair_error = f"{kind} structured outcome repair attempt {attempt} failed to run: {exc}"
                errors.append(repair_error)
                repair_record["error"] = repair_error
                repair_record["parsed"] = False
                repair_attempts.append(repair_record)
                continue
            repair_record.update(
                {
                    "exit_code": repair_result.exit_code,
                    "final_text": repair_result.final_text,
                    "stderr": repair_result.stderr,
                    "provider_error": repair_result.provider_error,
                }
            )
            try:
                outcome = parser(repair_result.final_text)
            except OutcomeProtocolError as exc:
                repair_error = f"{kind} structured outcome repair attempt {attempt} failed: {exc}"
                errors.append(repair_error)
                repair_record["error"] = repair_error
                repair_record["parsed"] = False
                repair_attempts.append(repair_record)
                continue
            repair_record["parsed"] = True
            repair_attempts.append(repair_record)
            return outcome, errors, repair_attempts
        return None, errors, repair_attempts

    def _outcome_repair_message(
        self,
        *,
        kind: str,
        bead_id: str,
        schema: dict[str, Any],
        error: str,
        role_result: RoleResult,
    ) -> str:
        transcript = json.dumps(role_result.transcript, indent=2, sort_keys=True)
        schema_text = json.dumps(schema, indent=2, sort_keys=True)
        return (
            f"Repair the structured outcome for {kind} bead {bead_id}.\n"
            "The previous agent run completed, but Purser could not parse or validate its structured outcome.\n"
            f"Validation error: {error}\n\n"
            "Required JSON schema-like contract:\n"
            f"{schema_text}\n\n"
            "Original final assistant text:\n"
            f"{role_result.final_text}\n\n"
            "Original JSON-mode transcript:\n"
            f"{transcript}\n\n"
            "Return only one JSON object matching the required contract. Do not wrap it in Markdown. "
            "Use only evidence from the transcript/final text. If the evidence is insufficient, return a failed outcome with a clear summary/blocking reason rather than fabricating success."
        )

    def _review(self, bead: Bead) -> RoleResult:
        prompt_path = self.config.prompt_path("reviewer")
        if prompt_path is None:
            raise RuntimeError(
                "reviewer prompt path is required; run `purser init` or configure [roles].reviewer_prompt"
            )
        spec_reference = str(bead.raw.get("spec_id") or "").strip()
        spec_line = (
            f"The originating spec is: {spec_reference}. Re-read it and enforce exact literals from it.\n"
            if spec_reference
            else "No spec_id is attached to this bead; if exact requirements are unclear, reject rather than infer.\n"
        )
        message = (
            f"Review bead {bead.id}.\n"
            "Your job is to validate accuracy, atomicity, and elegance against the spec and acceptance criteria.\n"
            f"{spec_line}"
            "Re-read the bead and inspect the codebase. Purser will run lint/types/tests after your review, so do not spend time running gates yourself unless absolutely necessary.\n"
            "Verify exact file names, exact strings, exact paths, and exact commands when they matter.\n"
            "Be decisive and concise.\n"
            "Do not close, reopen, or otherwise change the bead lifecycle state; Purser will perform Beads status transitions after validating your structured outcome and gates.\n"
            "Do not edit source files.\n"
            "At the end, return a JSON structured outcome with these fields exactly: status, bead_id, issues_found, gates_run, summary.\n"
            "Use status approved, rejected, blocked, or failed. Use issues_found objects with severity, summary, and file fields."
        )
        result = self.pi.run_role(
            role="reviewer",
            model=self.config.roles.resolved_model("reviewer"),
            prompt_path=prompt_path,
            message=message,
            tools="read,bash,grep,find,ls",
            timeout_seconds=self.config.roles.timeout_seconds,
        )
        outcome, errors, repair_attempts = self._parse_outcome_with_repair(
            kind="reviewer",
            bead_id=bead.id,
            role_result=result,
            prompt_path=prompt_path,
            parser=parse_reviewer_outcome,
            schema=REVIEWER_OUTCOME_SCHEMA,
        )
        current = self.beads.show(bead.id)
        if outcome is None:
            self.artifacts.write_role_artifact(
                kind="reviewer",
                bead_id=bead.id,
                role_result=result,
                structured_outcome=None,
                state={
                    "status_before": bead.normalized_status,
                    "status_after": current.normalized_status,
                },
                errors=errors,
                extra={"repair_attempts": repair_attempts},
            )
            raise RuntimeError(errors[0])
        if outcome.bead_id != bead.id:
            message = f"reviewer structured outcome bead_id mismatch: expected {bead.id}, got {outcome.bead_id}"
            self.artifacts.write_role_artifact(
                kind="reviewer",
                bead_id=bead.id,
                role_result=result,
                structured_outcome=outcome,
                state={
                    "status_before": bead.normalized_status,
                    "status_after": current.normalized_status,
                },
                errors=[message],
                extra={"repair_attempts": repair_attempts},
            )
            raise RuntimeError(message)
        gate_results = []
        gate_failure = None
        try:
            gate_results = self.gates.run_all(bead.id)
        except GateFailure as error:
            gate_failure = error.result
            self.beads.mark_review_ready(bead.id, ready=False)
            self.beads.update_status(
                bead.id, "open", notes=error.result.format_summary()
            )
            latest = self.beads.show(bead.id)
            self.artifacts.write_role_artifact(
                kind="reviewer",
                bead_id=bead.id,
                role_result=result,
                structured_outcome=outcome,
                gate_results=gate_results,
                gate_failure=gate_failure,
                state={
                    "status_before": bead.normalized_status,
                    "status_after": latest.normalized_status,
                },
                errors=[f"gate failed: {error.result.name}"],
                extra={"repair_attempts": repair_attempts},
            )
            return result
        current = self.beads.show(bead.id)
        if outcome.status == "approved":
            if current.normalized_status != "closed":
                current = self.beads.close(bead.id, reason=outcome.summary)
        else:
            self.beads.mark_review_ready(bead.id, ready=False)
            if current.normalized_status == "closed":
                current = self.beads.reopen(
                    bead.id, reason="purser reviewer outcome rejected closed work"
                )
            target_status = "blocked" if outcome.status == "blocked" else "open"
            latest = self.beads.update_status(bead.id, target_status, notes=outcome.summary)
            self.artifacts.write_role_artifact(
                kind="reviewer",
                bead_id=bead.id,
                role_result=result,
                structured_outcome=outcome,
                gate_results=gate_results,
                state={
                    "status_before": bead.normalized_status,
                    "status_after": latest.normalized_status,
                },
                extra={"repair_attempts": repair_attempts},
            )
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
        self.artifacts.write_role_artifact(
            kind="reviewer",
            bead_id=bead.id,
            role_result=result,
            structured_outcome=outcome,
            gate_results=gate_results,
            state={
                "status_before": bead.normalized_status,
                "status_after": current.normalized_status,
            },
            extra={
                "validation_log_path": str(self.config.validation_log_path),
                "repair_attempts": repair_attempts,
            },
        )
        return result
