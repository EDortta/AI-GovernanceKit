from __future__ import annotations

import json
from pathlib import Path

from governancekit import __version__
from governancekit.install_agents import DEFAULT_REF, REPO
from governancekit.version import format_version, get_version_info


def write_manifest(root: Path, ref: str, repo: str = REPO) -> None:
    path = root / ".gk/manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"repo": repo, "ref": ref}), encoding="utf-8")


def test_reports_runtime_and_default_without_project(tmp_path: Path) -> None:
    info = get_version_info(tmp_path)
    assert info.governancekit == __version__
    assert info.agents_default == DEFAULT_REF
    assert info.agents_project is None
    assert "not detected" in info.status


def test_finds_project_manifest_from_nested_directory(tmp_path: Path) -> None:
    write_manifest(tmp_path, DEFAULT_REF)
    nested = tmp_path / "src/module"
    nested.mkdir(parents=True)
    info = get_version_info(nested)
    assert info.project_root == tmp_path
    assert info.agents_project == DEFAULT_REF
    assert info.status == "up to date"


def test_reports_upgrade_when_project_ref_is_older(tmp_path: Path) -> None:
    write_manifest(tmp_path, "v1.0.0")
    info = get_version_info(tmp_path)
    assert info.status == f"upgrade available: v1.0.0 -> {DEFAULT_REF}"


def test_custom_repository_is_not_compared_as_an_upgrade(tmp_path: Path) -> None:
    write_manifest(tmp_path, "v9.0.0", "example/custom-agents")
    info = get_version_info(tmp_path)
    assert info.status == "custom AI-Agents repository in use (example/custom-agents)"


def test_human_format_contains_all_versions(tmp_path: Path) -> None:
    write_manifest(tmp_path, DEFAULT_REF)
    output = format_version(get_version_info(tmp_path))
    assert f"AI-GovernanceKit: {__version__}" in output
    assert f"AI-Agents default: {DEFAULT_REF}" in output
    assert f"AI-Agents project: {DEFAULT_REF}" in output
