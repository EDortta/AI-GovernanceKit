"""Version reporting for GovernanceKit and its installed AI-Agents policy pack."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .install_agents import DEFAULT_REF, REPO


@dataclass(frozen=True)
class VersionInfo:
    governancekit: str
    agents_default: str
    agents_project: str | None
    agents_repo: str | None
    project_root: Path | None
    status: str


def _version_tuple(ref: str) -> tuple[int, ...] | None:
    match = re.fullmatch(r"v?(\d+)(?:\.(\d+))(?:\.(\d+))", ref)
    return tuple(int(part) for part in match.groups()) if match else None


def _find_manifest(start: Path) -> tuple[Path, Path] | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        manifest = candidate / ".gk/manifest.json"
        if manifest.is_file():
            return candidate, manifest
    return None


def get_version_info(root: Path) -> VersionInfo:
    found = _find_manifest(root)
    if found is None:
        return VersionInfo(
            governancekit=__version__,
            agents_default=DEFAULT_REF,
            agents_project=None,
            agents_repo=None,
            project_root=None,
            status="AI-Agents installation not detected",
        )
    project_root, manifest_path = found
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return VersionInfo(
            governancekit=__version__,
            agents_default=DEFAULT_REF,
            agents_project=None,
            agents_repo=None,
            project_root=project_root,
            status="AI-Agents manifest is unreadable",
        )
    project_ref = manifest.get("ref") if isinstance(manifest.get("ref"), str) else None
    project_repo = manifest.get("repo") if isinstance(manifest.get("repo"), str) else None
    if not project_ref:
        status = "AI-Agents manifest has no installed ref"
    elif project_repo and project_repo != REPO:
        status = f"custom AI-Agents repository in use ({project_repo})"
    elif project_ref == DEFAULT_REF:
        status = "up to date"
    else:
        installed = _version_tuple(project_ref)
        available = _version_tuple(DEFAULT_REF)
        if installed and available and installed < available:
            status = f"upgrade available: {project_ref} -> {DEFAULT_REF}"
        elif installed and available and installed > available:
            status = f"project is newer than this GovernanceKit default ({DEFAULT_REF})"
        else:
            status = f"project ref differs from default: {project_ref} != {DEFAULT_REF}"
    return VersionInfo(
        governancekit=__version__,
        agents_default=DEFAULT_REF,
        agents_project=project_ref,
        agents_repo=project_repo,
        project_root=project_root,
        status=status,
    )


def format_version(info: VersionInfo) -> str:
    project = info.agents_project or "(not detected)"
    lines = [
        f"AI-GovernanceKit: {info.governancekit}",
        f"AI-Agents default: {info.agents_default}",
        f"AI-Agents project: {project}",
    ]
    if info.project_root:
        lines.append(f"Project root: {info.project_root}")
    lines.append(f"Status: {info.status}")
    return "\n".join(lines)
