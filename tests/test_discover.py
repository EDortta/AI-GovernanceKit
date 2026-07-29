from __future__ import annotations

import json
from pathlib import Path

from governancekit.discover import format_discovery, run_discover


def test_reports_new_project_when_only_governance_files_exist(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("kit\n", encoding="utf-8")
    (tmp_path / ".docs").mkdir()
    (tmp_path / ".docs" / "software-overview.md").write_text(
        "- project_context_ready: no\n",
        encoding="utf-8",
    )

    report = run_discover(tmp_path)

    assert report.project_state == "new"
    assert "AGENTS.md" in report.governance_files


def test_reports_existing_python_project(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='demo'\n[tool.pytest.ini_options]\n", encoding="utf-8"
    )
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")

    report = run_discover(tmp_path)

    assert report.project_state == "existing"
    assert report.languages["python"] == 1
    assert "pip/pyproject" in report.package_managers
    assert "python3 -m pytest" in report.automation_commands


def test_detects_node_frameworks_and_scripts(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "dependencies": {"react": "^19.0.0", "next": "^16.0.0"},
                "scripts": {"build": "next build", "test": "vitest"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "src.ts").write_text("export const ok = true;\n", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")

    report = run_discover(tmp_path)

    assert "react" in report.frameworks
    assert "nextjs" in report.frameworks
    assert "npm" in report.package_managers
    assert "npm run build" in report.automation_commands
    assert report.languages["typescript"] == 1


def test_detects_available_agents(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("kit\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("claude\n", encoding="utf-8")
    (tmp_path / ".docs" / "agents").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".docs" / "agents" / "programmer.md").write_text("# programmer\n", encoding="utf-8")
    (tmp_path / ".docs" / "agents" / "reviewer.md").write_text("# reviewer\n", encoding="utf-8")

    report = run_discover(tmp_path)

    assert "openai-agents" in report.agents
    assert "claude" in report.agents
    assert "policy:programmer" in report.agents
    assert "policy:reviewer" in report.agents


def test_human_format_is_stable(tmp_path: Path) -> None:
    (tmp_path / "main.go").write_text("package main\n", encoding="utf-8")

    output = format_discovery(run_discover(tmp_path))

    assert "AI GovernanceKit discover" in output
    assert "project state: existing" in output
    assert "languages: go (1)" in output
