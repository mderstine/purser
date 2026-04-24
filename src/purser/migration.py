from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json


LEGACY_ROLE_PROMPTS = {
    "planner": (
        Path(".purser/prompts/planner.md"),
        Path(".purser/prompts/roles/planner-role.md"),
    ),
    "executor": (
        Path(".purser/prompts/executor.md"),
        Path(".purser/prompts/roles/executor-role.md"),
    ),
    "reviewer": (
        Path(".purser/prompts/reviewer.md"),
        Path(".purser/prompts/roles/reviewer-role.md"),
    ),
}

LEGACY_PI_PROMPTS_DIR = "../.purser/prompts"
CANONICAL_PI_PROMPTS_DIR = "../.purser/prompts/workflows"


@dataclass(slots=True)
class MigrationReport:
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class LegacyLayoutState:
    role: str
    legacy_path: Path
    canonical_path: Path
    legacy_exists: bool
    canonical_exists: bool
    conflicts: bool
    config_uses_legacy_path: bool


def migrate_legacy_layout(root: Path) -> MigrationReport:
    report = MigrationReport()
    config_path = root / ".purser.toml"
    config_text = (
        config_path.read_text(encoding="utf-8") if config_path.exists() else None
    )

    for state in detect_legacy_layout(root, config_text=config_text):
        if not state.legacy_exists:
            continue
        if state.conflicts:
            report.errors.append(
                "legacy prompt migration is unsafe for "
                f"{state.role}: {state.legacy_path} conflicts with existing {state.canonical_path}; "
                "move/copy the wanted content manually, then update .purser.toml"
            )
            continue
        if not state.canonical_exists:
            state.canonical_path.parent.mkdir(parents=True, exist_ok=True)
            state.canonical_path.write_text(
                state.legacy_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
            report.changes.append(
                f"migrated legacy {state.role} prompt to {state.canonical_path}"
            )

    if report.errors:
        return report

    if config_text is not None:
        updated = config_text
        for _, (legacy_rel, canonical_rel) in LEGACY_ROLE_PROMPTS.items():
            updated = updated.replace(str(legacy_rel), str(canonical_rel))
        if updated != config_text:
            config_path.write_text(updated, encoding="utf-8")
            report.changes.append(
                f"updated legacy prompt paths in {config_path} to the canonical roles layout"
            )

    settings_path = root / ".pi/settings.json"
    if settings_path.exists():
        original = settings_path.read_text(encoding="utf-8")
        if original.strip():
            loaded = json.loads(original)
            if not isinstance(loaded, dict):
                raise ValueError(f"Expected JSON object in {settings_path}")
            prompts = loaded.get("prompts")
            if prompts is not None and not isinstance(prompts, list):
                raise ValueError(
                    f"Expected 'prompts' to be a JSON array in {settings_path}"
                )
            if isinstance(prompts, list):
                updated_prompts: list[str] = []
                changed = False
                for item in prompts:
                    if not isinstance(item, str):
                        updated_prompts.append(item)
                        continue
                    if item == LEGACY_PI_PROMPTS_DIR:
                        item = CANONICAL_PI_PROMPTS_DIR
                        changed = True
                    if item not in updated_prompts:
                        updated_prompts.append(item)
                if changed:
                    loaded["prompts"] = updated_prompts
                    settings_path.write_text(
                        json.dumps(loaded, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    report.changes.append(
                        f"updated {settings_path} prompts from {LEGACY_PI_PROMPTS_DIR} to {CANONICAL_PI_PROMPTS_DIR}"
                    )
    return report


def detect_legacy_layout(
    root: Path, *, config_text: str | None = None
) -> list[LegacyLayoutState]:
    if config_text is None:
        config_path = root / ".purser.toml"
        config_text = (
            config_path.read_text(encoding="utf-8") if config_path.exists() else None
        )
    states: list[LegacyLayoutState] = []
    for role, (legacy_rel, canonical_rel) in LEGACY_ROLE_PROMPTS.items():
        legacy_path = root / legacy_rel
        canonical_path = root / canonical_rel
        legacy_exists = legacy_path.exists()
        canonical_exists = canonical_path.exists()
        conflicts = False
        if legacy_exists and canonical_exists:
            conflicts = legacy_path.read_text(
                encoding="utf-8"
            ) != canonical_path.read_text(encoding="utf-8")
        states.append(
            LegacyLayoutState(
                role=role,
                legacy_path=legacy_path,
                canonical_path=canonical_path,
                legacy_exists=legacy_exists,
                canonical_exists=canonical_exists,
                conflicts=conflicts,
                config_uses_legacy_path=(config_text or "").find(str(legacy_rel)) >= 0,
            )
        )
    return states


def migration_health(root: Path) -> list[str]:
    messages: list[str] = []
    config_path = root / ".purser.toml"
    config_text = (
        config_path.read_text(encoding="utf-8") if config_path.exists() else None
    )
    states = detect_legacy_layout(root, config_text=config_text)
    for state in states:
        if state.conflicts:
            messages.append(
                "migration: error "
                f"(legacy {state.role} prompt at {state.legacy_path} conflicts with canonical {state.canonical_path}; "
                "keep the desired file, then update .purser.toml manually)"
            )
        elif state.legacy_exists and not state.canonical_exists:
            messages.append(
                "migration: warning "
                f"(legacy {state.role} prompt detected at {state.legacy_path}; run `purser init` to copy it into {state.canonical_path} and update config)"
            )
        elif state.legacy_exists and state.config_uses_legacy_path:
            messages.append(
                "migration: warning "
                f"(.purser.toml still points at legacy {state.role} prompt path {state.legacy_path}; prefer {state.canonical_path})"
            )
    settings_path = root / ".pi/settings.json"
    if settings_path.exists():
        try:
            raw = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            messages.append(
                f"migration: warning (cannot inspect legacy Pi prompt wiring in {settings_path}: {exc})"
            )
        else:
            prompts = raw.get("prompts")
            if isinstance(prompts, list) and LEGACY_PI_PROMPTS_DIR in prompts:
                messages.append(
                    "migration: warning "
                    f"({settings_path} still points at legacy Pi prompt dir {LEGACY_PI_PROMPTS_DIR}; run `purser init` to switch to {CANONICAL_PI_PROMPTS_DIR})"
                )
    return messages
