from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tomllib


DEFAULT_CONFIG_PATH = ".purser.toml"
DEFAULT_VALIDATION_LOG = "VALIDATION.md"
DEFAULT_SPEC_OUTPUT_DIR = ".purser/specs"
DEFAULT_PROMPTS_DIR = ".purser/prompts"


@dataclass(slots=True)
class ProjectConfig:
    name: str = "project"
    language: str = "unknown"


@dataclass(slots=True)
class GatesConfig:
    lint: str | None = None
    types: str | None = None
    tests: str | None = None
    timeout_seconds: int = 600

    def commands(self) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        if self.lint:
            result.append(("lint", self.lint))
        if self.types:
            result.append(("types", self.types))
        if self.tests:
            result.append(("tests", self.tests))
        return result


@dataclass(slots=True)
class LoopConfig:
    max_iterations_per_bead: int = 5
    validation_log: str = DEFAULT_VALIDATION_LOG
    human_approve_plan: bool = True


@dataclass(slots=True)
class RolesModelsConfig:
    planner: str = "anthropic/claude-opus-4-7"
    executor: str = "groq/llama-3.3-70b"
    reviewer: str = "anthropic/claude-opus-4-7"


@dataclass(slots=True)
class RolesConfig:
    planner_prompt: str | None = None
    executor_prompt: str | None = None
    reviewer_prompt: str | None = None
    timeout_seconds: int = 600
    models: RolesModelsConfig = field(default_factory=RolesModelsConfig)


@dataclass(slots=True)
class CompletionConfig:
    require_empty_ready: bool = True
    forbid_open_statuses: list[str] = field(
        default_factory=lambda: ["open", "in-progress", "in_review", "in-review"]
    )


@dataclass(slots=True)
class PlannerConfig:
    spec_output_dir: str = DEFAULT_SPEC_OUTPUT_DIR


@dataclass(slots=True)
class BeadsConfig:
    auto_commit: str = "on"


@dataclass(slots=True)
class PurserConfig:
    root: Path
    project: ProjectConfig = field(default_factory=ProjectConfig)
    gates: GatesConfig = field(default_factory=GatesConfig)
    loop: LoopConfig = field(default_factory=LoopConfig)
    roles: RolesConfig = field(default_factory=RolesConfig)
    completion: CompletionConfig = field(default_factory=CompletionConfig)
    planner: PlannerConfig = field(default_factory=PlannerConfig)
    beads: BeadsConfig = field(default_factory=BeadsConfig)

    @property
    def validation_log_path(self) -> Path:
        return self.root / self.loop.validation_log

    @property
    def spec_output_dir_path(self) -> Path:
        return self.root / self.planner.spec_output_dir

    def prompt_path(self, role: str) -> Path | None:
        value = getattr(self.roles, f"{role}_prompt")
        return None if value is None else self.root / value


class ConfigError(RuntimeError):
    pass


def load_config(
    root: Path | None = None, config_path: str = DEFAULT_CONFIG_PATH
) -> PurserConfig:
    resolved_root = (root or Path.cwd()).resolve()
    path = resolved_root / config_path
    if not path.exists():
        raise ConfigError(f"Missing config file: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    project = raw.get("project", {})
    gates = raw.get("gates", {})
    loop = raw.get("loop", {})
    roles = raw.get("roles", {})
    roles_models = roles.get("models", {})
    completion = raw.get("completion", {})
    planner = raw.get("planner", {})
    beads = raw.get("beads", {})

    config = PurserConfig(
        root=resolved_root,
        project=ProjectConfig(
            name=project.get("name", "project"),
            language=project.get("language", "unknown"),
        ),
        gates=GatesConfig(
            lint=gates.get("lint"),
            types=gates.get("types"),
            tests=gates.get("tests"),
            timeout_seconds=int(gates.get("timeout_seconds", 600)),
        ),
        loop=LoopConfig(
            max_iterations_per_bead=int(loop.get("max_iterations_per_bead", 5)),
            validation_log=loop.get("validation_log", DEFAULT_VALIDATION_LOG),
            human_approve_plan=bool(loop.get("human_approve_plan", True)),
        ),
        roles=RolesConfig(
            planner_prompt=roles.get("planner_prompt"),
            executor_prompt=roles.get("executor_prompt"),
            reviewer_prompt=roles.get("reviewer_prompt"),
            timeout_seconds=int(roles.get("timeout_seconds", 600)),
            models=RolesModelsConfig(
                planner=roles_models.get("planner", "anthropic/claude-opus-4-7"),
                executor=roles_models.get("executor", "groq/llama-3.3-70b"),
                reviewer=roles_models.get("reviewer", "anthropic/claude-opus-4-7"),
            ),
        ),
        completion=CompletionConfig(
            require_empty_ready=bool(completion.get("require_empty_ready", True)),
            forbid_open_statuses=list(
                completion.get("forbid_open_statuses", ["open", "in-review"])
            ),
        ),
        planner=PlannerConfig(
            spec_output_dir=planner.get("spec_output_dir", DEFAULT_SPEC_OUTPUT_DIR),
        ),
        beads=BeadsConfig(
            auto_commit=str(beads.get("auto_commit", "on")),
        ),
    )
    validate_config(config)
    return config


def validate_config(config: PurserConfig) -> None:
    if config.loop.max_iterations_per_bead < 1:
        raise ConfigError("loop.max_iterations_per_bead must be >= 1")
    if config.gates.timeout_seconds < 1:
        raise ConfigError("gates.timeout_seconds must be >= 1")
    if config.roles.timeout_seconds < 1:
        raise ConfigError("roles.timeout_seconds must be >= 1")
    if config.beads.auto_commit not in {"off", "on", "batch"}:
        raise ConfigError("beads.auto_commit must be one of: off, on, batch")
