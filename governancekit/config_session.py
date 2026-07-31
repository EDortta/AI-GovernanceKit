"""Resumable configuration sessions with explicit approval gates."""

from __future__ import annotations

import json
import shlex
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .classification import load_change_classification
from .project_config import (
    ProviderConfig,
    ProjectConfigPlan,
    _config_from_existing,
    apply_project_config,
    build_project_config_plan,
    provider_warnings,
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
    provider_configs: list[ProviderConfig] | None = None,
    selected_agent: str | None = None,
    capability_domains: dict[str, str] | None = None,
    required_reading: list[str] | None = None,
    scope_summary: str | None = None,
) -> ConfigSession:
    root = root.resolve()
    plan = build_project_config_plan(
        root,
        project_name=project_name,
        domains=domains,
        capabilities=capabilities,
        agents=agents,
        provider_names=provider_names,
        provider_configs=provider_configs,
        selected_agent=selected_agent,
        capability_domains=capability_domains,
        required_reading=required_reading,
        scope_summary=scope_summary,
    )
    warnings = provider_warnings(plan.config.providers)
    if warnings:
        raise ValueError("configuration session cannot start: " + "; ".join(warnings))
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
    config_raw = session.plan.get("config")
    config = _config_from_existing(config_raw) if isinstance(config_raw, dict) else None
    if config is None:
        raise RuntimeError("configuration session has an invalid saved plan")
    written = apply_project_config(root, config)
    updated = ConfigSession(
        status="applied",
        approvals_required=session.approvals_required,
        approvals_granted=session.approvals_granted,
        plan=session.plan,
        notes=[*session.notes, "session applied to disk"],
    )
    _session_path(root).write_text(
        json.dumps(updated.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return written


def format_config_session(session: ConfigSession, root: Path | None = None) -> str:
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
    if session.status == "pending_approval":
        prefix = f"governancekit --root {shlex.quote(str(root.resolve()))} config-session" if root else "governancekit config-session"
        missing = [approval for approval in session.approvals_required if approval not in session.approvals_granted]
        lines.extend(
            [
                "",
                "meaning: the configuration plan is saved but has not been applied.",
                "These are local acknowledgements, not independent authorization or access control.",
                "approvals still needed:",
            ]
        )
        for approval in missing:
            if approval == "existing-project-adoption-review":
                lines.append("  - existing-project-adoption-review: inspect the existing project before adoption.")
            elif approval == "project-config-review":
                lines.append("  - project-config-review: review the domains, capabilities, agents, and providers in the plan.")
            else:
                lines.append(f"  - {approval}: review the change required by this approval token.")
            lines.append(f"    acknowledge: {prefix} approve --approval {approval}")
        lines.extend(
            [
                "",
                "After every required local acknowledgement is recorded:",
                f"  {prefix} show",
                f"  {prefix} apply",
                "The approved configuration will be written to .gk/project-config.json and docs/project-configuration.md.",
            ]
        )
    elif session.status == "approved":
        prefix = f"governancekit --root {shlex.quote(str(root.resolve()))} config-session" if root else "governancekit config-session"
        lines.extend(
            [
                "",
                "meaning: all required local acknowledgements are recorded; the plan is ready to apply.",
                f"apply: {prefix} apply",
            ]
        )
    elif session.status == "applied":
        lines.extend(
            [
                "",
                "meaning: the locally acknowledged configuration has been written to the project.",
                f"inspect: governancekit --root {shlex.quote(str(root.resolve()))} configure-project show" if root else "inspect: governancekit configure-project show",
            ]
        )
    return "\n".join(lines)
