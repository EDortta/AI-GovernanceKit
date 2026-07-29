from __future__ import annotations

import json
from pathlib import Path

from governancekit.integration import inspect_integration_contract


def write_contract(
    root: Path,
    *,
    version_range: str = ">=0.2.2,<0.3.0",
    repo: str = "EDortta/AI-Agents",
) -> None:
    path = root / ".docs" / "governancekit-integration.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "ai_agents": {"repo": repo, "ref": "v1.1.6"},
                "governancekit": {
                    "version_range": version_range,
                    "required_features": ["version-reporting", "doctor-advisory"],
                },
            }
        ),
        encoding="utf-8",
    )


def test_reports_missing_contract(tmp_path: Path) -> None:
    result = inspect_integration_contract(tmp_path)
    assert result.status == "missing"


def test_reports_compatible_contract(tmp_path: Path) -> None:
    write_contract(tmp_path)
    result = inspect_integration_contract(tmp_path)
    assert result.status == "ok"
    assert "compatible" in result.message


def test_reports_incompatible_contract(tmp_path: Path) -> None:
    write_contract(tmp_path, version_range=">=9.0.0,<10.0.0")
    result = inspect_integration_contract(tmp_path)
    assert result.status == "incompatible"
    assert "requires GovernanceKit" in result.message


def test_custom_repo_contract_is_advisory(tmp_path: Path) -> None:
    write_contract(tmp_path, repo="example/custom-agents")
    result = inspect_integration_contract(tmp_path)
    assert result.status == "custom-repo"
