from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

from .beads import BeadsError
from .config import (
    ConfigError,
    DEFAULT_CONFIG_PATH,
    DEFAULT_PROMPTS_DIR,
    PurserConfig,
    load_config,
)
from .detect import detect_init_profile
from .gates import GateFailure
from .loop import PurserLoop
from .migration import migrate_legacy_layout, migration_health
from .planner import PlannerService
from .repo import resolve_repo_root
from .resources import write_default_prompts, write_scaffold_readme
from .roles import RoleExecutionError
from .scaffold import (
    PURSER_AGENTS_BEGIN,
    PURSER_AGENTS_END,
    append_gitignore_entries,
    merge_pi_settings_prompts,
    upsert_delimited_markdown_section,
)
from .runtime import (
    collect_binary_statuses,
    ensure_local_beads_context,
    format_beads_context_status,
    format_binary_status,
    model_health,
    pi_prompt_integration_health,
    prompt_health,
    prompt_layout_health,
)


DEFAULT_CONFIG_TEMPLATE = """[project]
name = \"{project_name}\"
language = \"{language}\"

[gates]
lint = {lint}
types = {types}
tests = {tests}
timeout_seconds = 600

[loop]
max_iterations_per_bead = 5
validation_log = \"VALIDATION.md\"
human_approve_plan = true

[planner]
spec_output_dir = \".purser/specs\"

[beads]
auto_commit = \"on\"

[roles]
planner_prompt = \".purser/prompts/roles/planner-role.md\"
executor_prompt = \".purser/prompts/roles/executor-role.md\"
reviewer_prompt = \".purser/prompts/roles/reviewer-role.md\"
timeout_seconds = 600
# Optional: set this to pin one shared Pi-routed model for all roles in this repo.
# default_model = \"qwen3.5\"

# Optional per-role overrides. If omitted, Purser falls back to roles.default_model,
# then to Pi's ambient/default model selection by omitting --model.
# [roles.models]
# planner = \"qwen3.5\"
# executor = \"codex\"
# reviewer = \"gpt-oss\"

[completion]
require_empty_ready = true
forbid_open_statuses = [\"open\", \"in-review\"]
"""

PURSER_AGENTS_BODY = """## Purser workflow

This repository uses **Purser** as a planning / execution / review framework.

Important:
- **Purser is not the product or primary deliverable of this repository.**
- The actual goal is to advance this repository's real work.
- That work may include software development, bug fixing, documentation, research, data analysis, data discovery, or other scoped deliverables relevant to this repo.
- Use Purser only as the orchestration layer for that work.

When working in this repo:
- Treat specs as descriptions of the repository's actual work, not Purser development work unless explicitly requested.
- Use Purser to decompose specs into Beads, execute scoped work, run gates or other validation where applicable, and review outcomes.
- Keep scope focused on the requested deliverable in this repository.
- Respect this repo's actual conventions, workflows, validation methods, and success criteria.
- Use repo-local embedded Beads storage only; do not use shared or server-backed Beads databases.

Typical workflow:
1. Write or refine a spec for the desired work in this repo.
2. Have the director (human driver) review and approve the refined spec / planning approach.
3. Only then use Purser to generate the bead graph and plan the work into atomic beads.
4. Execute one bead at a time against this repo's actual artifacts (code, data, docs, analysis, etc.).
5. Review for accuracy, atomicity, and elegance/fitness to the repo's goals.
6. Record validation results for completed work.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="purser")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="write starter config and prompt files")
    init.add_argument("--force", action="store_true")

    intake = subparsers.add_parser(
        "planner-intake-spec",
        help="read a spec and optionally synthesize an improved markdown version",
    )
    intake.add_argument("spec", type=Path)
    intake.add_argument("--synthesize", choices=["true", "false"], default="false")
    intake.add_argument("--output", type=Path)

    plan = subparsers.add_parser(
        "planner-plan", help="decompose a spec into beads and dependencies"
    )
    plan.add_argument("spec", type=Path)

    approve = subparsers.add_parser(
        "approve-plan", help="record human approval for a spec before planning"
    )
    approve.add_argument("spec", type=Path)

    build = subparsers.add_parser("exec-build", help="execute one bead, then review it")
    build.add_argument("bead_id", nargs="?")

    subparsers.add_parser(
        "exec-build-all", help="run the executor/reviewer loop until completion"
    )

    subparsers.add_parser(
        "doctor", help="check local purser, Beads, Dolt, Pi, and config health"
    )

    return parser


def ensure_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Missing required binary on PATH: {name}")


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def load_runtime_config() -> PurserConfig:
    ensure_binary("bd")
    ensure_binary("dolt")
    ensure_binary("pi")
    config = load_config(resolve_repo_root())
    ensure_local_beads_context(config.root)
    return config


def cmd_init(args: argparse.Namespace) -> int:
    root = resolve_repo_root()
    config_path = root / DEFAULT_CONFIG_PATH
    prompts_dir = root / DEFAULT_PROMPTS_DIR
    specs_keep = root / "specs/.gitkeep"
    scaffold_readme = root / ".purser/README.md"
    pi_settings = root / ".pi/settings.json"
    agents_path = root / "AGENTS.md"
    gitignore_path = root / ".gitignore"

    written: list[Path] = []
    skipped: list[Path] = []

    migration = migrate_legacy_layout(root)
    if migration.errors:
        raise RuntimeError("; ".join(migration.errors))

    profile = detect_init_profile(root)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists() and not args.force:
        skipped.append(config_path)
    else:
        config_path.write_text(
            DEFAULT_CONFIG_TEMPLATE.format(
                project_name=root.name,
                language=profile.language,
                lint=_toml_string(profile.lint),
                types=_toml_string(profile.types),
                tests=_toml_string(profile.tests),
            ),
            encoding="utf-8",
        )
        written.append(config_path)

    prompt_paths = write_default_prompts(prompts_dir, force=args.force)
    written.extend(prompt_paths)
    expected_prompt_paths = [
        prompts_dir / "roles/planner-role.md",
        prompts_dir / "roles/executor-role.md",
        prompts_dir / "roles/reviewer-role.md",
        prompts_dir / "workflows/purser-add-spec.md",
        prompts_dir / "workflows/purser-plan.md",
        prompts_dir / "workflows/purser-build.md",
        prompts_dir / "workflows/purser-build-all.md",
    ]
    for path in expected_prompt_paths:
        if path.exists() and path not in prompt_paths:
            skipped.append(path)

    specs_keep.parent.mkdir(parents=True, exist_ok=True)
    if specs_keep.exists() and not args.force:
        skipped.append(specs_keep)
    else:
        specs_keep.write_text("", encoding="utf-8")
        written.append(specs_keep)

    if write_scaffold_readme(scaffold_readme, force=args.force):
        written.append(scaffold_readme)
    else:
        skipped.append(scaffold_readme)

    if merge_pi_settings_prompts(pi_settings, "../.purser/prompts/workflows"):
        written.append(pi_settings)
    else:
        skipped.append(pi_settings)

    if upsert_delimited_markdown_section(
        agents_path,
        begin_marker=PURSER_AGENTS_BEGIN,
        end_marker=PURSER_AGENTS_END,
        body=PURSER_AGENTS_BODY,
    ):
        written.append(agents_path)
    else:
        skipped.append(agents_path)

    if append_gitignore_entries(
        gitignore_path,
        [".beads/", ".purser/", ".purser.toml", "VALIDATION.md"],
    ):
        written.append(gitignore_path)
    else:
        skipped.append(gitignore_path)

    for line in migration.changes:
        print(line)
    for path in written:
        print(f"wrote {path}")
    for path in skipped:
        print(f"kept {path}")
    print("next: edit .purser.toml for your project's gates and models")
    return 0


def cmd_planner_intake_spec(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    service = PlannerService(config)
    result = service.intake_spec(
        args.spec, synthesize=args.synthesize == "true", output_path=args.output
    )
    if result.output_path:
        print(result.output_path)
    if result.role_result.final_text:
        print(result.role_result.final_text)
    return 0


def cmd_planner_plan(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    service = PlannerService(config)
    result = service.plan_spec(args.spec)
    if result.final_text:
        print(result.final_text)
    return 0


def cmd_approve_plan(args: argparse.Namespace) -> int:
    config = load_config(resolve_repo_root())
    service = PlannerService(config)
    approval_path = service.approve_plan(args.spec)
    print(approval_path)
    return 0


def cmd_exec_build(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    loop = PurserLoop(config)
    bead_id = loop.run_once(args.bead_id)
    print(bead_id)
    return 0


def cmd_exec_build_all(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    loop = PurserLoop(config)
    result = loop.run_all()
    print(result.status)
    for bead_id in result.processed_beads:
        print(bead_id)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    del args
    exit_code = 0
    print("== binaries ==")
    for status in collect_binary_statuses():
        print(format_binary_status(status))
        if not status.ok:
            exit_code = 1

    try:
        config = load_config(resolve_repo_root())
    except Exception as exc:
        print("== config ==")
        print(f"config: error ({exc})")
        return 1 if exit_code == 0 else exit_code

    print("== config ==")
    print(f"config: ok ({config.root / DEFAULT_CONFIG_PATH})")
    print(f"validation_log: {config.validation_log_path}")

    print("== prompts ==")
    for line in prompt_health(config.root, config):
        print(line)
        if ": missing file " in line or ": not configured" in line:
            exit_code = 1
    print(pi_prompt_integration_health(config.root))
    for line in prompt_layout_health(config.root, config):
        print(line)
    for line in migration_health(config.root):
        print(line)
        if line.startswith("migration: error"):
            exit_code = 1

    print("== models ==")
    for line in model_health(config):
        print(line)

    print("== beads ==")
    try:
        context = ensure_local_beads_context(config.root)
        print(format_beads_context_status(context))
    except RuntimeError as exc:
        print(f"beads_storage: error ({exc})")
        exit_code = 1
    return exit_code


def dispatch(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        return cmd_init(args)
    if args.command == "planner-intake-spec":
        return cmd_planner_intake_spec(args)
    if args.command == "planner-plan":
        return cmd_planner_plan(args)
    if args.command == "approve-plan":
        return cmd_approve_plan(args)
    if args.command == "exec-build":
        return cmd_exec_build(args)
    if args.command == "exec-build-all":
        return cmd_exec_build_all(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    raise SystemExit(f"Unknown command: {args.command}")


def main() -> None:
    try:
        raise SystemExit(dispatch())
    except SystemExit:
        raise
    except (
        ConfigError,
        FileNotFoundError,
        RuntimeError,
        RoleExecutionError,
        BeadsError,
        GateFailure,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)


def planner_intake_spec_main() -> None:
    raise SystemExit(dispatch(["planner-intake-spec", *sys.argv[1:]]))


def planner_plan_main() -> None:
    raise SystemExit(dispatch(["planner-plan", *sys.argv[1:]]))


def exec_build_main() -> None:
    raise SystemExit(dispatch(["exec-build", *sys.argv[1:]]))


def exec_build_all_main() -> None:
    raise SystemExit(dispatch(["exec-build-all", *sys.argv[1:]]))
