"""Evidence-based, review-first project adoption used by ``install-agents``."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .discover import run_discover


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


def build_adoption_proposal(root: Path) -> AdoptionProposal:
    root = root.resolve()
    discovery = run_discover(root)
    evidence = [*discovery.governance_files, *discovery.frameworks, *discovery.package_managers]
    stack = ", ".join([*discovery.frameworks, *discovery.languages]) or "not detected"
    commands = ", ".join(discovery.automation_commands) or "not detected"
    overview = "\n".join((
        "# Software Overview", "", "## Metadata", "", "- project_context_ready: yes", "",
        "## Evidence-based proposal", "", f"- Project: {root.name}", f"- Detected stack: {stack}",
        f"- Automation: {commands}", "", "## Known unknowns", "", "- Deployment target was not inferred; review before treating this as binding policy.", "",
    ))
    limits = "\n".join((
        "# Agent Operational Limits", "", "## Metadata", "", "- limits_ready: yes", "",
        "## Accepted baseline", "", "- Never commit credentials, tokens, or local runtime state.",
        "- Preserve existing project-authored documentation during upgrades.",
        "- Review database, deployment, and compatibility changes before application.", "",
        "## Detected recommendations", "", f"- Validate with: {commands}.", "",
    ))
    return AdoptionProposal(root, overview, limits, evidence, ["deployment target"])


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


def format_adoption_proposal(proposal: AdoptionProposal) -> str:
    return "\n".join(["Project adoption proposal", f"Project: {proposal.root.name}", "Evidence: " + (", ".join(proposal.evidence) or "none"), "Unresolved: " + ", ".join(proposal.unresolved), "Apply generated overview and limits?"])
