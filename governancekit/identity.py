"""Per-host / per-instance programmer identity.

Local-first, gitignored state that individualizes each host operating a governed
project. Field names are aligned with the AI-Agents policy contract
(``mandate-per-host-programmer-identity``):

    operator_name, host_id, instance_path, sibling_path,
    assigned_ports, branch_ownership

The identity file is per instance and MUST NOT be tracked in git (it would leak
one host's ports/paths onto another). It never contains secrets.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Local, gitignored, per-instance identity file. Lives at the repo root.
IDENTITY_FILENAME = ".governancekit-identity.json"

# Fields that MUST be present for identity to be considered complete.
REQUIRED_FIELDS: tuple[str, ...] = ("operator_name", "host_id", "instance_path")

# Optional individualization fields (shared-branch coordination).
OPTIONAL_FIELDS: tuple[str, ...] = ("sibling_path", "assigned_ports", "branch_ownership")

ALL_FIELDS: tuple[str, ...] = REQUIRED_FIELDS + OPTIONAL_FIELDS

_FIELD_DESCRIPTIONS: dict[str, str] = {
    "operator_name": "human operator name (also used as message prefix)",
    "host_id": "identifier of this machine/instance",
    "instance_path": "absolute path of this instance's checkout",
    "sibling_path": "path(s) of sibling instance(s), if any (comma-separated)",
    "assigned_ports": "ports reserved by this instance (comma-separated)",
    "branch_ownership": "which branch(es) this instance owns on shared-branch projects",
}


@dataclass
class Identity:
    operator_name: str = ""
    host_id: str = ""
    instance_path: str = ""
    sibling_path: str = ""
    assigned_ports: list[str] = field(default_factory=list)
    branch_ownership: str = ""

    def missing_required(self) -> list[str]:
        return [f for f in REQUIRED_FIELDS if not str(getattr(self, f)).strip()]

    @property
    def complete(self) -> bool:
        return not self.missing_required()

    def to_dict(self) -> dict[str, object]:
        return {
            "operator_name": self.operator_name,
            "host_id": self.host_id,
            "instance_path": self.instance_path,
            "sibling_path": self.sibling_path,
            "assigned_ports": list(self.assigned_ports),
            "branch_ownership": self.branch_ownership,
        }


def identity_path(root: Path) -> Path:
    return root.resolve() / IDENTITY_FILENAME


def _coerce_ports(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [p.strip() for p in str(value).split(",") if p.strip()]


def load_identity(root: Path) -> Identity | None:
    """Return the persisted Identity, or None when the file is absent/unreadable."""
    path = identity_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return Identity(
        operator_name=str(data.get("operator_name", "") or ""),
        host_id=str(data.get("host_id", "") or ""),
        instance_path=str(data.get("instance_path", "") or ""),
        sibling_path=str(data.get("sibling_path", "") or ""),
        assigned_ports=_coerce_ports(data.get("assigned_ports")),
        branch_ownership=str(data.get("branch_ownership", "") or ""),
    )


def identity_from_values(values: dict[str, str]) -> Identity:
    """Build an Identity from a flat string mapping (e.g. CLI flags)."""
    return Identity(
        operator_name=str(values.get("operator_name", "") or "").strip(),
        host_id=str(values.get("host_id", "") or "").strip(),
        instance_path=str(values.get("instance_path", "") or "").strip(),
        sibling_path=str(values.get("sibling_path", "") or "").strip(),
        assigned_ports=_coerce_ports(values.get("assigned_ports")),
        branch_ownership=str(values.get("branch_ownership", "") or "").strip(),
    )


def save_identity(root: Path, identity: Identity) -> Path:
    """Persist *identity* to the local gitignored file and return its path."""
    path = identity_path(root)
    path.write_text(
        json.dumps(identity.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    ensure_gitignored(root)
    return path


def ensure_gitignored(root: Path) -> bool:
    """Ensure the identity file is listed in .gitignore. Returns True if changed."""
    gitignore = root.resolve() / ".gitignore"
    entry = IDENTITY_FILENAME
    existing = ""
    if gitignore.is_file():
        existing = gitignore.read_text(encoding="utf-8", errors="replace")
        lines = {ln.strip() for ln in existing.splitlines()}
        if entry in lines:
            return False
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    block = f"{prefix}\n# Per-instance host identity (never tracked)\n{entry}\n"
    with gitignore.open("a", encoding="utf-8") as handle:
        handle.write(block)
    return True


def current_branch(root: Path) -> str:
    """Return the current git branch, or '' when unavailable."""
    if not (root / ".git").exists():
        return ""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return completed.stdout.strip()


def sibling_branch_conflict(identity: Identity, branch: str) -> str:
    """Return a warning if the current branch matches the instance's declared
    ``branch_ownership`` combined with a declared sibling path, i.e. a shared
    branch that a sibling instance may also be operating. Empty string if none.
    """
    if not branch or not identity.sibling_path.strip():
        return ""
    owned = {b.strip() for b in identity.branch_ownership.split(",") if b.strip()}
    if owned and branch not in owned:
        return (
            f"current branch '{branch}' is not owned by this instance "
            f"(owns: {', '.join(sorted(owned))}); sibling '{identity.sibling_path}' "
            f"may operate it — align before committing."
        )
    if not owned:
        return (
            f"current branch '{branch}' has no declared branch_ownership while a "
            f"sibling '{identity.sibling_path}' exists — risk of same-branch collision."
        )
    return ""
