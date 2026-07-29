"""Architecture change classification workflow."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

_CLASSIFICATION_FILE = ".gk/change-classification.json"
_ALLOWED_LABELS = {
    "additive",
    "behavioral-change",
    "contract-change",
    "migration",
    "security-sensitive",
}


@dataclass(frozen=True)
class ChangeClassification:
    summary: str
    labels: list[str]
    rationale: str
    affected_domains: list[str]
    affected_capabilities: list[str]
    compatibility: str
    approvals_required: list[str]
    residual_risk: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _dedupe(items: list[str]) -> list[str]:
    return sorted(dict.fromkeys(item.strip() for item in items if item and item.strip()))


def build_change_classification(
    *,
    summary: str,
    labels: list[str],
    rationale: str,
    affected_domains: list[str],
    affected_capabilities: list[str],
    compatibility: str,
    residual_risk: str,
) -> ChangeClassification:
    chosen_labels = _dedupe(labels)
    invalid = [label for label in chosen_labels if label not in _ALLOWED_LABELS]
    if invalid:
        raise ValueError(f"invalid classification label(s): {', '.join(invalid)}")
    if not summary.strip():
        raise ValueError("summary is required")
    if not rationale.strip():
        raise ValueError("rationale is required")
    if not compatibility.strip():
        raise ValueError("compatibility is required")
    approvals_required = ["normal-issue-approval"]
    for label in chosen_labels:
        if label != "additive":
            approvals_required.append(f"human-review:{label}")
    return ChangeClassification(
        summary=summary.strip(),
        labels=chosen_labels,
        rationale=rationale.strip(),
        affected_domains=_dedupe(affected_domains),
        affected_capabilities=_dedupe(affected_capabilities),
        compatibility=compatibility.strip(),
        approvals_required=approvals_required,
        residual_risk=residual_risk.strip() or "not declared",
    )


def save_change_classification(root: Path, classification: ChangeClassification) -> str:
    root = root.resolve()
    path = root / _CLASSIFICATION_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(classification.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return _CLASSIFICATION_FILE


def load_change_classification(root: Path) -> ChangeClassification | None:
    path = root.resolve() / _CLASSIFICATION_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        return ChangeClassification(
            summary=str(data.get("summary", "")),
            labels=[str(item) for item in data.get("labels", []) if isinstance(item, str)],
            rationale=str(data.get("rationale", "")),
            affected_domains=[
                str(item) for item in data.get("affected_domains", []) if isinstance(item, str)
            ],
            affected_capabilities=[
                str(item)
                for item in data.get("affected_capabilities", [])
                if isinstance(item, str)
            ],
            compatibility=str(data.get("compatibility", "")),
            approvals_required=[
                str(item) for item in data.get("approvals_required", []) if isinstance(item, str)
            ],
            residual_risk=str(data.get("residual_risk", "")),
        )
    except (TypeError, ValueError):
        return None


def format_change_classification(classification: ChangeClassification) -> str:
    lines = ["AI GovernanceKit classify-change"]
    lines.append(f"summary: {classification.summary}")
    lines.append(f"labels: {', '.join(classification.labels) or '(none)'}")
    lines.append(f"compatibility: {classification.compatibility}")
    lines.append(
        f"affected domains: {', '.join(classification.affected_domains) or '(none)'}"
    )
    lines.append(
        "affected capabilities: "
        + (", ".join(classification.affected_capabilities) or "(none)")
    )
    lines.append(
        f"approvals required: {', '.join(classification.approvals_required) or '(none)'}"
    )
    lines.append(f"residual risk: {classification.residual_risk}")
    lines.append(f"rationale: {classification.rationale}")
    return "\n".join(lines)
