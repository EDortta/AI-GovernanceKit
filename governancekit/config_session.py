"""Resumable configuration sessions with explicit approval gates."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .classification import load_change_classification
from .project_config import (
    ProjectConfigPlan,
    apply_project_config_plan,
    build_project_config_plan,
)

_SESSION_FILE = ".gk/config-session.json"


@dataclass(frozen=True)
class ConfigSession:
    status: str
    approvals_required: list[str]
    approvals_granted: list[str]
    plan: dict[str, object]
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _dedupe(items: list[str]) -> list[str]:
    return sorted(dict.fromkeys(item.strip() for item in items if item and item.strip()))


def _session_path(root: Path) -> Path:
    return root.resolve() / _SESSION_FILE


def _required_approvals(root: Path, plan: ProjectConfigPlan) -> list[str]:
    approvals = ["project-config-review"]
    classification = load_change_classification(root)
    if classification is not None:
        approvals.extend(classification.approvals_required)
    if plan.discovery.project_state == "existing":
        approvals.append("existing-project-adoption-review")
    return _dedupe(approvals)


def start_config_session(
    root: Path,
    *,
    project_name: str | None = None,
    domains: list[str] | None = None,
    capabilities: list[str] | None = None,
    agents: list[str] | None = None,
    provider_names: list[str] | None = None,
) -> ConfigSession:
    root = root.resolve()
    plan = build_project_config_plan(
        root,
        project_name=project_name,
        domains=domains,
        capabilities=capabilities,
        agents=agents,
        provider_names=provider_names,
    )
    session = ConfigSession(
        status="pending_approval",
        approvals_required=_required_approvals(root, plan),
        approvals_granted=[],
        plan=plan.as_dict(),
        notes=["session created from current discovery and classification state"],
    )
    path = _session_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return session


def load_config_session(root: Path) -> ConfigSession | None:
    path = _session_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return ConfigSession(
        status=str(data.get("status", "")),
        approvals_required=[
            str(item) for item in data.get("approvals_required", []) if isinstance(item, str)
        ],
        approvals_granted=[
            str(item) for item in data.get("approvals_granted", []) if isinstance(item, str)
        ],
        plan=data.get("plan", {}) if isinstance(data.get("plan"), dict) else {},
        notes=[str(item) for item in data.get("notes", []) if isinstance(item, str)],
    )


def grant_config_approval(root: Path, approval: str) -> ConfigSession:
    session = load_config_session(root)
    if session is None:
        raise RuntimeError("no configuration session found")
    granted = _dedupe([*session.approvals_granted, approval])
    status = "approved" if all(req in granted for req in session.approvals_required) else "pending_approval"
    updated = ConfigSession(
        status=status,
        approvals_required=session.approvals_required,
        approvals_granted=granted,
        plan=session.plan,
        notes=session.notes,
    )
    _session_path(root).write_text(
        json.dumps(updated.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return updated


def apply_config_session(root: Path) -> list[str]:
    root = root.resolve()
    session = load_config_session(root)
    if session is None:
        raise RuntimeError("no configuration session found")
    if session.status != "approved":
        missing = [req for req in session.approvals_required if req not in session.approvals_granted]
        raise RuntimeError(
            "configuration session is not approved; missing: " + ", ".join(missing)
        )
    plan = build_project_config_plan(root)
    written = apply_project_config_plan(plan)
    updated = ConfigSession(
        status="applied",
        approvals_required=session.approvals_required,
        approvals_granted=session.approvals_granted,
        plan=plan.as_dict(),
        notes=[*session.notes, "session applied to disk"],
    )
    _session_path(root).write_text(
        json.dumps(updated.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return written


def format_config_session(session: ConfigSession) -> str:
    lines = ["AI GovernanceKit config-session"]
    lines.append(f"status: {session.status}")
    lines.append(
        "approvals required: " + (", ".join(session.approvals_required) or "(none)")
    )
    lines.append(
        "approvals granted: " + (", ".join(session.approvals_granted) or "(none)")
    )
    if session.notes:
        lines.append("notes:")
        for note in session.notes:
            lines.append(f"  - {note}")
    return "\n".join(lines)
