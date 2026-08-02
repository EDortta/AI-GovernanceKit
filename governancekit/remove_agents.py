"""Conservative de-adoption planning for an installed AI-Agents kit.

The planner intentionally makes no semantic deletion decisions.  A manifest hash
is the only current automatic-removal authority; every other candidate is kept
and surfaced for review.  This gives a legacy project a useful inventory without
pretending that an LLM can prove authorship.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .path_safety import UnsafePathError, safe_path, safe_regular_file

PLAN_RELATIVE_PATH = ".gk/remove-agents-plan.json"
PLAN_VERSION = 1
_ROOT_RULE_FILES = ("AGENTS.md", ".cursorrules", "CLAUDE.md", ".windsurfrules", "GEMINI.md")


@dataclass(frozen=True)
class RemovalItem:
    path: str
    classification: str
    confidence: float
    action: str
    evidence: list[str] = field(default_factory=list)
    requires_operator_review: bool = False
    referenced: bool = False


@dataclass(frozen=True)
class RemovalPlan:
    schema_version: int
    root: str
    created_at: str
    items: list[RemovalItem]
    provider: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ApplyResult:
    backup_dir: Path
    removed: list[str]
    preserved: list[str]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_files(root: Path) -> dict[str, str]:
    path = root / ".gk/manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    files = data.get("files", {})
    return {str(key): str(value) for key, value in files.items() if isinstance(value, str)}


def _candidate_paths(root: Path, manifest: dict[str, str]) -> list[str]:
    candidates = set(manifest)
    for name in _ROOT_RULE_FILES:
        if (root / name).exists():
            candidates.add(name)
    for directory in (".docs", ".amazonq/rules", ".github/copilot-instructions.md", "scripts"):
        target = root / directory
        if target.is_file():
            candidates.add(directory)
        elif target.is_dir() and not target.is_symlink():
            for child in target.rglob("*"):
                if child.is_file() and not child.is_symlink():
                    candidates.add(child.relative_to(root).as_posix())
    return sorted(candidates)


def _referenced(root: Path, rel: str) -> bool:
    """A deliberately small, non-authoritative reference warning.

    We look for a path literal in ordinary text files; binary files, symlinks and
    the candidate itself are never read.  A hit only prevents automatic deletion.
    """
    needle = rel.encode("utf-8")
    for path in root.rglob("*"):
        if path.is_dir() or path.is_symlink() or path.relative_to(root).as_posix() == rel:
            continue
        relative_parts = path.relative_to(root).parts
        if ".git" in relative_parts or ".gk" in relative_parts or not safe_regular_file(root, path):
            continue
        try:
            if needle in path.read_bytes():
                return True
        except OSError:
            continue
    return False


def build_removal_plan(root: Path) -> RemovalPlan:
    root = root.resolve()
    manifest = _manifest_files(root)
    items: list[RemovalItem] = []
    for rel in _candidate_paths(root, manifest):
        path = root / rel
        if not safe_regular_file(root, path):
            # Symlinks and directories are always preserved, including malformed
            # manifest entries.  They are never followed by this command.
            items.append(RemovalItem(rel, "unknown", 0.0, "preserve", ["not a safe regular file"], True))
            continue
        referenced = _referenced(root, rel)
        expected = manifest.get(rel)
        if expected and _sha256(path) == expected and not referenced:
            items.append(RemovalItem(rel, "kit-owned-unchanged", 1.0, "remove", ["manifest hash matches current file"], False))
        elif expected:
            evidence = ["manifest records this path", "current hash differs from recorded install hash"]
            if referenced:
                evidence.append("path is referenced elsewhere in the project")
            items.append(RemovalItem(rel, "kit-owned-modified", 1.0, "preserve", evidence, True, referenced))
        else:
            evidence = ["not present in trusted installation manifest"]
            if referenced:
                evidence.append("path is referenced elsewhere in the project")
            items.append(RemovalItem(rel, "unknown", 0.0, "preserve", evidence, True, referenced))
    return RemovalPlan(
        schema_version=PLAN_VERSION,
        root=str(root),
        created_at=datetime.now(timezone.utc).isoformat(),
        items=items,
        provider={"status": "not-invoked", "reason": "no unresolved item is eligible for automatic removal"},
    )


def write_removal_plan(root: Path, plan: RemovalPlan, output: Path | None = None) -> Path:
    root = root.resolve()
    destination = output or root / PLAN_RELATIVE_PATH
    destination = safe_path(root, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(plan.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def load_removal_plan(root: Path, plan_path: Path | None = None) -> RemovalPlan:
    root = root.resolve()
    path = safe_path(root, plan_path or root / PLAN_RELATIVE_PATH)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != PLAN_VERSION or Path(data.get("root", "")).resolve() != root:
        raise ValueError("plan is not compatible with this project root")
    items = [RemovalItem(**item) for item in data.get("items", [])]
    return RemovalPlan(data["schema_version"], data["root"], data["created_at"], items, data.get("provider", {}))


def apply_removal_plan(root: Path, plan: RemovalPlan) -> ApplyResult:
    root = root.resolve()
    backup_dir = root / ".gk/remove-agents-backup" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    removable = [item for item in plan.items if item.classification == "kit-owned-unchanged" and item.action == "remove"]
    # Validate every target before the first write, eliminating a partial action
    # caused by a newly introduced symlink.
    targets: list[tuple[RemovalItem, Path]] = []
    for item in removable:
        path = safe_path(root, root / item.path)
        if not safe_regular_file(root, path):
            raise UnsafePathError(f"refusing to remove changed or unsafe path: {item.path}")
        targets.append((item, path))
    backup_dir.mkdir(parents=True, exist_ok=False)
    copied: list[str] = []
    try:
        for item, path in targets:
            copy_to = safe_path(root, backup_dir / item.path)
            copy_to.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, copy_to)
            copied.append(item.path)
        (backup_dir / "restore-manifest.json").write_text(
            json.dumps({"root": str(root), "files": copied}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        for _, path in targets:
            path.unlink()
    except Exception:
        # No original is destroyed before its backup has been written.  A caller can
        # restore the recorded copies after any unexpected application failure.
        raise
    return ApplyResult(backup_dir, [item.path for item, _ in targets], [item.path for item in plan.items if item.action != "remove"])


def format_removal_plan(plan: RemovalPlan) -> str:
    lines = ["AI GovernanceKit remove-agents plan"]
    for item in plan.items:
        review = " (review required)" if item.requires_operator_review else ""
        lines.append(f"  {item.action}: {item.path} [{item.classification}]{review}")
    lines.append("Only manifest-verified, unreferenced files are eligible for removal.")
    return "\n".join(lines)
