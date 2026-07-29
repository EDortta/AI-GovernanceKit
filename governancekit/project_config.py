"""Project adoption/configuration state for AI-GovernanceKit."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .discover import DiscoveryReport, run_discover
from .integration import inspect_integration_contract

_PROJECT_CONFIG_FILE = ".gk/project-config.json"
_CONFIG_VERSION = 1


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    mode: str = "manual"
    credential_ref: str | None = None


@dataclass(frozen=True)
class ProjectConfig:
    config_version: int
    project_name: str
    project_state: str
    languages: list[str]
    frameworks: list[str]
    package_managers: list[str]
    automation_commands: list[str]
    domains: list[str]
    capabilities: list[str]
    agents: list[str]
    providers: list[ProviderConfig]
    governance_files: list[str]
    integration_status: str
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["providers"] = [asdict(provider) for provider in self.providers]
        return data


@dataclass(frozen=True)
class PlanAction:
    kind: str
    target: str
    detail: str


@dataclass(frozen=True)
class ProjectConfigPlan:
    root: Path
    config: ProjectConfig
    actions: list[PlanAction]
    discovery: DiscoveryReport

    def as_dict(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "config": self.config.as_dict(),
            "actions": [asdict(action) for action in self.actions],
            "discovery": self.discovery.as_dict(),
        }


def _dedupe(items: list[str]) -> list[str]:
    return sorted(dict.fromkeys(item.strip() for item in items if item and item.strip()))


def _default_domains(root: Path, discovery: DiscoveryReport) -> list[str]:
    if discovery.frameworks:
        return [discovery.frameworks[0]]
    if discovery.languages:
        return [next(iter(discovery.languages))]
    return [root.name.lower().replace(" ", "-")]


def _default_capabilities(discovery: DiscoveryReport) -> list[str]:
    capabilities: list[str] = []
    if discovery.project_state == "existing":
        capabilities.append("adopt-existing-project")
    else:
        capabilities.append("bootstrap-new-project")
    if discovery.frameworks:
        capabilities.append(f"{discovery.frameworks[0]}-runtime")
    if discovery.package_managers:
        capabilities.append("dependency-management")
    if discovery.automation_commands:
        capabilities.append("automation-validation")
    return _dedupe(capabilities)


def _default_agents() -> list[str]:
    return ["programmer", "reviewer"]


def _default_providers(existing: ProjectConfig | None) -> list[ProviderConfig]:
    if existing and existing.providers:
        return existing.providers
    return [ProviderConfig(name="manual", mode="manual")]


def _config_from_existing(data: dict) -> ProjectConfig | None:
    if not isinstance(data, dict):
        return None
    providers_raw = data.get("providers")
    providers: list[ProviderConfig] = []
    if isinstance(providers_raw, list):
        for provider in providers_raw:
            if not isinstance(provider, dict):
                continue
            name = provider.get("name")
            mode = provider.get("mode", "manual")
            credential_ref = provider.get("credential_ref")
            if isinstance(name, str) and name:
                providers.append(
                    ProviderConfig(
                        name=name,
                        mode=str(mode) if mode else "manual",
                        credential_ref=str(credential_ref) if credential_ref else None,
                    )
                )
    try:
        return ProjectConfig(
            config_version=int(data.get("config_version", _CONFIG_VERSION)),
            project_name=str(data.get("project_name", "")),
            project_state=str(data.get("project_state", "")),
            languages=[str(item) for item in data.get("languages", []) if isinstance(item, str)],
            frameworks=[str(item) for item in data.get("frameworks", []) if isinstance(item, str)],
            package_managers=[
                str(item) for item in data.get("package_managers", []) if isinstance(item, str)
            ],
            automation_commands=[
                str(item) for item in data.get("automation_commands", []) if isinstance(item, str)
            ],
            domains=[str(item) for item in data.get("domains", []) if isinstance(item, str)],
            capabilities=[
                str(item) for item in data.get("capabilities", []) if isinstance(item, str)
            ],
            agents=[str(item) for item in data.get("agents", []) if isinstance(item, str)],
            providers=providers,
            governance_files=[
                str(item) for item in data.get("governance_files", []) if isinstance(item, str)
            ],
            integration_status=str(data.get("integration_status", "")),
            notes=[str(item) for item in data.get("notes", []) if isinstance(item, str)],
        )
    except (TypeError, ValueError):
        return None


def load_project_config(root: Path) -> ProjectConfig | None:
    path = root.resolve() / _PROJECT_CONFIG_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _config_from_existing(data)


def build_project_config_plan(
    root: Path,
    *,
    project_name: str | None = None,
    domains: list[str] | None = None,
    capabilities: list[str] | None = None,
    agents: list[str] | None = None,
    provider_names: list[str] | None = None,
) -> ProjectConfigPlan:
    root = root.resolve()
    discovery = run_discover(root)
    integration = inspect_integration_contract(root)
    existing = load_project_config(root)

    existing_domains = existing.domains if existing else []
    existing_capabilities = existing.capabilities if existing else []
    existing_agents = existing.agents if existing else []

    selected_domains = _dedupe(domains if domains else existing_domains) or _default_domains(
        root, discovery
    )
    selected_capabilities = _dedupe(
        capabilities if capabilities else existing_capabilities
    ) or _default_capabilities(discovery)
    selected_agents = _dedupe(agents if agents else existing_agents) or _default_agents()

    providers: list[ProviderConfig]
    if provider_names:
        providers = [ProviderConfig(name=name, mode="manual") for name in _dedupe(provider_names)]
    else:
        providers = _default_providers(existing)

    config = ProjectConfig(
        config_version=_CONFIG_VERSION,
        project_name=project_name or (existing.project_name if existing else root.name),
        project_state=discovery.project_state,
        languages=list(discovery.languages.keys()),
        frameworks=discovery.frameworks,
        package_managers=discovery.package_managers,
        automation_commands=discovery.automation_commands,
        domains=selected_domains,
        capabilities=selected_capabilities,
        agents=selected_agents,
        providers=providers,
        governance_files=discovery.governance_files,
        integration_status=integration.status,
        notes=[
            *discovery.notes,
            "provider credentials stay outside project-config.json; use credential_ref only",
        ],
    )

    actions: list[PlanAction] = [
        PlanAction("write", _PROJECT_CONFIG_FILE, "persist shareable project configuration"),
    ]
    if existing is None:
        actions.append(
            PlanAction("create", "docs/project-configuration.md", "seed project configuration summary")
        )
    else:
        actions.append(
            PlanAction("update", "docs/project-configuration.md", "refresh project configuration summary")
        )
    if discovery.project_state == "existing":
        actions.append(
            PlanAction(
                "review",
                "existing source tree",
                "inspect discovered project files before any destructive migration",
            )
        )
    if integration.status != "ok":
        actions.append(
            PlanAction(
                "review",
                ".docs/governancekit-integration.json",
                f"resolve integration status before relying on automated adoption ({integration.status})",
            )
        )
    return ProjectConfigPlan(root=root, config=config, actions=actions, discovery=discovery)


def render_project_config_markdown(config: ProjectConfig) -> str:
    lines = [
        "# Project Configuration",
        "",
        f"- project_name: {config.project_name}",
        f"- project_state: {config.project_state}",
        f"- languages: {', '.join(config.languages) or '(none)'}",
        f"- frameworks: {', '.join(config.frameworks) or '(none)'}",
        f"- package_managers: {', '.join(config.package_managers) or '(none)'}",
        f"- automation_commands: {', '.join(config.automation_commands) or '(none)'}",
        f"- domains: {', '.join(config.domains) or '(none)'}",
        f"- capabilities: {', '.join(config.capabilities) or '(none)'}",
        f"- agents: {', '.join(config.agents) or '(none)'}",
        f"- integration_status: {config.integration_status}",
        "",
        "## Providers",
        "",
    ]
    if config.providers:
        for provider in config.providers:
            lines.append(
                f"- {provider.name}: mode={provider.mode}, credential_ref={provider.credential_ref or '(unset)'}"
            )
    else:
        lines.append("- (none)")
    lines.extend(["", "## Notes", ""])
    if config.notes:
        for note in config.notes:
            lines.append(f"- {note}")
    else:
        lines.append("- (none)")
    return "\n".join(lines) + "\n"


def apply_project_config_plan(plan: ProjectConfigPlan) -> list[str]:
    root = plan.root
    state_dir = root / ".gk"
    docs_dir = root / "docs"
    state_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    config_path = root / _PROJECT_CONFIG_FILE
    config_path.write_text(
        json.dumps(plan.config.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written.append(_PROJECT_CONFIG_FILE)

    summary_path = docs_dir / "project-configuration.md"
    summary_path.write_text(render_project_config_markdown(plan.config), encoding="utf-8")
    written.append("docs/project-configuration.md")
    return written


def format_project_config_plan(plan: ProjectConfigPlan) -> str:
    lines = ["AI GovernanceKit configure-project plan"]
    lines.append(f"root: {plan.root}")
    lines.append(f"project: {plan.config.project_name}")
    lines.append(f"state: {plan.config.project_state}")
    lines.append("domains: " + (", ".join(plan.config.domains) or "(none)"))
    lines.append("capabilities: " + (", ".join(plan.config.capabilities) or "(none)"))
    lines.append("agents: " + (", ".join(plan.config.agents) or "(none)"))
    lines.append(
        "providers: "
        + (", ".join(provider.name for provider in plan.config.providers) or "(none)")
    )
    lines.append("actions:")
    for action in plan.actions:
        lines.append(f"  - {action.kind} {action.target}: {action.detail}")
    return "\n".join(lines)
