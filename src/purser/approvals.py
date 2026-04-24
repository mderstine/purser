from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
from datetime import datetime, timezone


APPROVALS_DIR = Path(".purser/state/plan-approvals")


@dataclass(frozen=True, slots=True)
class PlanApproval:
    spec_path: Path
    approval_path: Path


def approval_path_for_spec(root: Path, spec_path: Path) -> Path:
    key = sha256(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:16]
    return root / APPROVALS_DIR / f"{key}.json"


def approve_spec(root: Path, spec_path: Path) -> PlanApproval:
    approval_path = approval_path_for_spec(root, spec_path)
    approval_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "spec_path": str(spec_path.resolve()),
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }
    approval_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return PlanApproval(spec_path=spec_path.resolve(), approval_path=approval_path)


def is_spec_approved(root: Path, spec_path: Path) -> bool:
    approval_path = approval_path_for_spec(root, spec_path)
    if not approval_path.exists():
        return False
    try:
        raw = json.loads(approval_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return raw.get("spec_path") == str(spec_path.resolve())
