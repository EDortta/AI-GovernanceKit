"""Evidence-based, review-first project adoption used by ``install-agents``."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .discover import run_discover
from .project_config import ProviderConfig, load_project_config


@dataclass(frozen=True)
class AdoptionProposal:
    root: Path
    overview: str
    limits: str
    evidence: list[str]
    unresolved: list[str]

    def as_dict(self) -> dict[str, object]:
        return {"root": str(self.root), "overview": self.overview, "limits": self.limits, "evidence": self.evidence, "unresolved": self.unresolved}


def _replace_ready(text: str, marker: str) -> str:
    return text.replace(f"{marker}: no", f"{marker}: yes")


def _primary_provider(root: Path) -> ProviderConfig | None:
    config = load_project_config(root)
    if config is None:
        return None
    for provider in config.providers:
        if provider.role == "primary" and provider.mode in {"env", "file-ref"} and provider.base_url and provider.model and provider.credential_ref:
            return provider
    return None


def build_adoption_proposal(root: Path) -> AdoptionProposal:
    root = root.resolve()
    discovery = run_discover(root)
    evidence = [*discovery.governance_files, *discovery.frameworks, *discovery.package_managers]
    stack = ", ".join([*discovery.frameworks, *discovery.languages]) or "not detected"
    commands = ", ".join(discovery.automation_commands) or "not detected"
    unresolved = ["deployment target"]
    llm_summary = ""
    provider = _primary_provider(root)
    if provider:
        # Reuse the hardened scope adapter: it confines sources, treats content as
        # data, validates returned JSON, and never persists credentials.
        from .agent_scope import propose_project_scope
        from .scope_conversation import load_required_reading
        sources, missing = load_required_reading(root)
        try:
            proposed = propose_project_scope(root, "llm-api", sources, provider=provider)
            llm_summary = proposed.summary
            evidence.extend(item for domain in proposed.domains for item in domain.evidence)
            unresolved.extend(proposed.questions)
        except RuntimeError as exc:
            unresolved.append(f"configured provider could not enrich proposal: {exc}")
        unresolved.extend(missing)
    overview = "\n".join((
        "# Software Overview", "", "## Metadata", "", "- project_context_ready: yes", "",
        "## Evidence-based proposal", "", f"- Project: {root.name}", f"- Detected stack: {stack}",
        f"- Automation: {commands}", *( ("- LLM scope proposal: " + llm_summary,) if llm_summary else ()), "", "## Known unknowns", "", *[f"- {item}" for item in unresolved], "",
    ))
    limits = "\n".join((
        "# Agent Operational Limits", "", "## Metadata", "", "- limits_ready: yes", "",
        "## Accepted baseline", "", "- Never commit credentials, tokens, or local runtime state.",
        "- Preserve existing project-authored documentation during upgrades.",
        "- Review database, deployment, and compatibility changes before application.", "",
        "## Detected recommendations", "", f"- Validate with: {commands}.", "",
    ))
    return AdoptionProposal(root, overview, limits, evidence, unresolved)


def apply_adoption_proposal(proposal: AdoptionProposal) -> list[str]:
    written: list[str] = []
    for rel, content, marker in ((".docs/software-overview.md", proposal.overview, "project_context_ready"), (".docs/limits.md", proposal.limits, "limits_ready")):
        path = proposal.root / rel
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        if old and marker in old and f"{marker}: yes" in old:
            continue
        if old and marker not in old:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(rel)
    return written


def detect_project_drift(root: Path) -> list[str]:
    """Report new observable project facts without rewriting accepted policy."""
    root = root.resolve()
    accepted = load_project_config(root)
    if accepted is None:
        return []
    discovered = run_discover(root)
    drift: list[str] = []
    for label, current, recorded in (
        ("framework", set(discovered.frameworks), set(accepted.frameworks)),
        ("language", set(discovered.languages), set(accepted.languages)),
        ("package manager", set(discovered.package_managers), set(accepted.package_managers)),
    ):
        for value in sorted(current - recorded):
            drift.append(f"new {label} detected: {value}")
    return drift


def format_adoption_proposal(proposal: AdoptionProposal) -> str:
    return "\n".join(["Project adoption proposal", f"Project: {proposal.root.name}", "Evidence: " + (", ".join(proposal.evidence) or "none"), "Unresolved: " + ", ".join(proposal.unresolved), "Apply generated overview and limits?"])
