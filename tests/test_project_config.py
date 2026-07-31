from __future__ import annotations

import json
from pathlib import Path

from governancekit import cli
from governancekit.project_config import (
    _PROJECT_CONFIG_FILE,
    ProviderConfig,
    apply_project_config_plan,
    build_project_config_plan,
    load_project_config,
    parse_provider_specs,
)


def _seed_contract(root: Path) -> None:
    path = root / ".docs" / "governancekit-integration.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "ai_agents": {"repo": "EDortta/AI-Agents", "ref": "v1.1.6"},
                "governancekit": {
                    "version_range": ">=0.2.2,<0.3.0",
                    "required_features": ["version-reporting"],
                },
            }
        ),
        encoding="utf-8",
    )


def test_build_plan_uses_discovery_defaults(tmp_path: Path) -> None:
    _seed_contract(tmp_path)
    (tmp_path / "AGENTS.md").write_text("kit\n", encoding="utf-8")
    (tmp_path / ".docs" / "agents").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".docs" / "agents" / "programmer.md").write_text("# programmer\n", encoding="utf-8")
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"react": "^19.0.0"}, "scripts": {"test": "vitest"}}),
        encoding="utf-8",
    )
    (tmp_path / "src.ts").write_text("export const x = 1;\n", encoding="utf-8")

    plan = build_project_config_plan(tmp_path)

    assert plan.config.project_state == "existing"
    assert "react" in plan.config.domains
    assert "react-runtime" in plan.config.capabilities
    assert "openai-agents" in plan.config.agents
    assert any(action.target == _PROJECT_CONFIG_FILE for action in plan.actions)


def test_apply_writes_shareable_files(tmp_path: Path) -> None:
    _seed_contract(tmp_path)
    plan = build_project_config_plan(tmp_path, project_name="Demo")

    written = apply_project_config_plan(plan)

    assert _PROJECT_CONFIG_FILE in written
    assert "docs/project-configuration.md" in written
    loaded = load_project_config(tmp_path)
    assert loaded is not None
    assert loaded.project_name == "Demo"


def test_parse_provider_specs_supports_modes_and_refs() -> None:
    providers = parse_provider_specs(
        ["openai:env:OPENAI_API_KEY:primary", "anthropic:file-ref:.credentials/anthropic.key:fallback", "manual"]
    )

    assert providers[0].name == "openai"
    assert providers[0].mode == "env"
    assert providers[0].credential_ref == "OPENAI_API_KEY"
    assert providers[0].role == "primary"
    assert providers[1].mode == "file-ref"
    assert providers[1].role == "fallback"
    assert providers[2].name == "manual"
    assert providers[2].mode == "manual"


def test_guided_provider_purpose_persists_without_a_secret(tmp_path: Path) -> None:
    _seed_contract(tmp_path)
    plan = build_project_config_plan(
        tmp_path,
        provider_configs=[
            ProviderConfig(
                name="openai",
                purpose="general",
                mode="env",
                credential_ref="OPENAI_API_KEY",
                validation="reference-required",
                role="primary",
            )
        ],
    )

    apply_project_config_plan(plan)

    saved = json.loads((tmp_path / _PROJECT_CONFIG_FILE).read_text(encoding="utf-8"))
    assert saved["providers"] == [{
        "name": "openai", "purpose": "general", "base_url": None, "model": None, "mode": "env",
        "credential_ref": "OPENAI_API_KEY", "validation": "reference-required", "role": "primary",
    }]


def test_cli_plan_and_apply_roundtrip(tmp_path: Path, capsys) -> None:
    _seed_contract(tmp_path)
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")

    code = cli.main(
        [
            "--root",
            str(tmp_path),
            "configure-project",
            "plan",
            "--project-name",
            "Sample",
            "--domain",
            "backend",
            "--capability",
            "api",
            "--provider",
            "openai:env:OPENAI_API_KEY",
        ]
    )
    assert code == 0
    output = capsys.readouterr().out
    assert "configure-project plan" in output
    assert "backend" in output

    code = cli.main(
        [
            "--root",
            str(tmp_path),
            "configure-project",
            "apply",
            "--project-name",
            "Sample",
            "--domain",
            "backend",
            "--capability",
            "api",
            "--provider",
            "openai:env:OPENAI_API_KEY",
        ]
    )
    assert code == 0
    capsys.readouterr()

    code = cli.main(["--root", str(tmp_path), "configure-project", "show", "--json"])
    assert code == 0
    current = json.loads(capsys.readouterr().out)
    assert current["project_name"] == "Sample"
    assert current["domains"] == ["backend"]
    assert current["providers"][0]["credential_ref"] == "OPENAI_API_KEY"
