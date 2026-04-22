from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

from .config import DEFAULT_CONFIG_PATH, DEFAULT_PROMPTS_DIR, PurserConfig, load_config
from .loop import PurserLoop
from .planner import PlannerService
from .resources import write_default_prompts
from .runtime import collect_binary_statuses, format_binary_status, prompt_health


DEFAULT_CONFIG_TEMPLATE = """[project]
name = \"{project_name}\"
language = \"python\"

[gates]
lint = \"ruff check . && ruff format --check .\"
types = \"python3 -m pyright\"
tests = \"python3 -m pytest -x --tb=short\"
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
planner_prompt = \".purser/prompts/planner.md\"
executor_prompt = \".purser/prompts/executor.md\"
reviewer_prompt = \".purser/prompts/reviewer.md\"

[roles.models]
planner = \"anthropic/claude-opus-4-7\"
executor = \"groq/llama-3.3-70b\"
reviewer = \"anthropic/claude-opus-4-7\"

[completion]
require_empty_ready = true
forbid_open_statuses = [\"open\", \"in-review\"]
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="purser")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="write starter config and prompt files")
    init.add_argument("--force", action="store_true")

    intake = subparsers.add_parser("planner-intake-spec", help="read a spec and optionally synthesize an improved markdown version")
    intake.add_argument("spec", type=Path)
    intake.add_argument("--synthesize", choices=["true", "false"], default="false")
    intake.add_argument("--output", type=Path)

    plan = subparsers.add_parser("planner-plan", help="decompose a spec into beads and dependencies")
    plan.add_argument("spec", type=Path)

    build = subparsers.add_parser("exec-build", help="execute one bead, then review it")
    build.add_argument("bead_id", nargs="?")

    build_all = subparsers.add_parser("exec-build-all", help="run the executor/reviewer loop until completion")

    subparsers.add_parser("doctor", help="check local purser, Beads, Dolt, Pi, and config health")

    return parser


def ensure_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"Missing required binary on PATH: {name}")


def load_runtime_config() -> PurserConfig:
    ensure_binary("bd")
    ensure_binary("dolt")
    ensure_binary("pi")
    return load_config(Path.cwd())


def cmd_init(args: argparse.Namespace) -> int:
    root = Path.cwd()
    config_path = root / DEFAULT_CONFIG_PATH
    prompts_dir = root / DEFAULT_PROMPTS_DIR
    if config_path.exists() and not args.force:
        raise SystemExit(f"Refusing to overwrite existing config: {config_path} (use --force)")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(DEFAULT_CONFIG_TEMPLATE.format(project_name=root.name), encoding="utf-8")
    written = write_default_prompts(prompts_dir)
    print(f"wrote {config_path}")
    for path in written:
        print(f"wrote {path}")
    print("next: edit .purser.toml for your project's gates and models")
    return 0


def cmd_planner_intake_spec(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    service = PlannerService(config)
    result = service.intake_spec(args.spec, synthesize=args.synthesize == "true", output_path=args.output)
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
    for status in collect_binary_statuses():
        print(format_binary_status(status))

    try:
        config = load_config(Path.cwd())
    except Exception as exc:
        print(f"config: error ({exc})")
        return 1

    print(f"config: ok ({config.root / DEFAULT_CONFIG_PATH})")
    print(f"validation_log: {config.validation_log_path}")
    for line in prompt_health(config.root, config):
        print(line)

    try:
        completed = subprocess.run(["bd", "context"], cwd=config.root, text=True, capture_output=True, check=False)
        output = completed.stdout.strip() or completed.stderr.strip()
        print(f"bd_context: {'ok' if completed.returncode == 0 else 'error'}" + (f" ({output.splitlines()[0]})" if output else ""))
    except OSError as exc:
        print(f"bd_context: error ({exc})")
        return 1
    return 0


def dispatch(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        return cmd_init(args)
    if args.command == "planner-intake-spec":
        return cmd_planner_intake_spec(args)
    if args.command == "planner-plan":
        return cmd_planner_plan(args)
    if args.command == "exec-build":
        return cmd_exec_build(args)
    if args.command == "exec-build-all":
        return cmd_exec_build_all(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    raise SystemExit(f"Unknown command: {args.command}")


def main() -> None:
    raise SystemExit(dispatch())


def planner_intake_spec_main() -> None:
    raise SystemExit(dispatch(["planner-intake-spec", *sys.argv[1:]]))


def planner_plan_main() -> None:
    raise SystemExit(dispatch(["planner-plan", *sys.argv[1:]]))


def exec_build_main() -> None:
    raise SystemExit(dispatch(["exec-build", *sys.argv[1:]]))


def exec_build_all_main() -> None:
    raise SystemExit(dispatch(["exec-build-all", *sys.argv[1:]]))
