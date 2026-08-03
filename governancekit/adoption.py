"""Evidence-based, review-first project adoption used by ``install-agents``."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .discover import run_discover
from .project_config import ProviderConfig, load_project_config


@dataclass(frozen=True)
class AdoptionProposal:
    root: Path
    overview: str
    limits: str
    evidence: list[str]
    unresolved: list[str]
    llm_warning: "LlmEnrichmentWarning | None" = None

    def as_dict(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "overview": self.overview,
            "limits": self.limits,
            "evidence": self.evidence,
            "unresolved": self.unresolved,
            "llm_warning": self.llm_warning.as_dict() if self.llm_warning else None,
        }


@dataclass(frozen=True)
class LlmEnrichmentWarning:
    provider: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {"provider": self.provider, "reason": self.reason}


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


def configured_adoption_provider(root: Path) -> ProviderConfig | None:
    """Return the eligible primary provider without invoking it."""
    return _primary_provider(root.resolve())


def provider_label(provider: ProviderConfig) -> str:
    """Render only the non-secret provider identity shown to an operator."""
    return f"{provider.name} / {provider.model}"


def _llm_failure_reason(error: RuntimeError) -> str:
    message = str(error)
    if message == "selected agent returned invalid evidence":
        return (
            "the response's evidence is not a valid non-empty list of unique text entries"
        )
    if message == "selected agent returned evidence outside the selected sources":
        return (
            "the response cited a file that was not among the approved project sources"
        )
    return message


def build_adoption_proposal(
    root: Path,
    *,
    enrich_with_llm: bool = False,
    on_top_level_directory: Callable[[Path], None] | None = None,
) -> AdoptionProposal:
    root = root.resolve()
    discovery = run_discover(root, on_top_level_directory)
    evidence = [*discovery.governance_files, *discovery.frameworks, *discovery.package_managers]
    stack = ", ".join([*discovery.frameworks, *discovery.languages]) or "not detected"
    commands = ", ".join(discovery.automation_commands) or "not detected"
    unresolved = ["deployment target"]
    llm_summary = ""
    llm_warning: LlmEnrichmentWarning | None = None
    provider = configured_adoption_provider(root)
    if provider and enrich_with_llm:
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
            llm_warning = LlmEnrichmentWarning(
                provider=provider_label(provider), reason=_llm_failure_reason(exc)
            )
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
    return AdoptionProposal(root, overview, limits, evidence, unresolved, llm_warning)


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


def detect_project_drift(
    root: Path, *, on_top_level_directory: Callable[[Path], None] | None = None
) -> list[str]:
    """Report new observable project facts without rewriting accepted policy."""
    root = root.resolve()
    accepted = load_project_config(root)
    if accepted is None:
        return []
    discovered = run_discover(root, on_top_level_directory)
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
    lines = [
        "Project adoption proposal",
        f"Project: {proposal.root.name}",
        "Evidence: " + (", ".join(proposal.evidence) or "none"),
    ]
    if proposal.unresolved:
        lines.extend(["Open items:", *(f"  - {item}" for item in proposal.unresolved)])
    if proposal.llm_warning:
        lines.extend(
            [
                "",
                "[WARNING] LLM enrichment was skipped; no LLM result will be applied.",
                f"  Provider/model: {proposal.llm_warning.provider}",
                f"  Reason: {proposal.llm_warning.reason}.",
                "  Expected: each domain must cite selected sources as 'path: reason'.",
                "  How to proceed:",
                "    1. Review the deterministic proposal above; it remains safe to use.",
                "    2. Enter n at the next prompt to leave overview and limits unchanged.",
                "    3. Retry later; if it repeats, correct the configured primary provider/model before retrying.",
            ]
        )
    lines.append("Apply generated overview and limits?")
    return "\n".join(lines)
