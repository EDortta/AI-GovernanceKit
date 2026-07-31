from __future__ import annotations

from pathlib import Path

from governancekit.classification import build_change_classification, save_change_classification
from governancekit.issue_bootstrap import bootstrap_issue
from governancekit.project_config import build_project_config_plan, apply_project_config_plan


def _seed_templates(root: Path) -> None:
    templates = root / ".docs" / "issues" / "templates"
    templates.mkdir(parents=True, exist_ok=True)
    (templates / "README.template.md").write_text(
        "# <EPIC_TITLE>\n\n- work_id: WK-YYYYMMDD-<short-slug>\n- related_commit: <planned-or-hash>\n"
        "- objective: <objective>\n",
        encoding="utf-8",
    )
    (templates / "epic.template.md").write_text(
        "# Epic: <EPIC_TITLE>\n\n- work_id: WK-YYYYMMDD-<short-slug>\n"
        "## Context\n<business and technical context>\n\n## Problem Statement\n<problem>\n",
        encoding="utf-8",
    )
    (templates / "task.template.md").write_text(
        "# Task: <TASK_TITLE>\n\n- work_id: WK-YYYYMMDD-<short-slug>\n"
        "- parent: <NNN-epic-slug>\n- objective: <objective>\n",
        encoding="utf-8",
    )


def test_bootstrap_issue_uses_project_config_and_classification(tmp_path: Path) -> None:
    _seed_templates(tmp_path)
    (tmp_path / ".docs" / "governancekit-integration.json").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".docs" / "governancekit-integration.json").write_text(
        '{"schema_version":1,"ai_agents":{"repo":"EDortta/AI-Agents","ref":"v1.1.6"},'
        '"governancekit":{"version_range":">=0.2.2,<0.3.0","required_features":["version-reporting"]}}',
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    plan = build_project_config_plan(
        tmp_path,
        project_name="Demo",
        domains=["backend"],
        capabilities=["api"],
    )
    apply_project_config_plan(plan)
    save_change_classification(
        tmp_path,
        build_change_classification(
            summary="Move auth boundary",
            labels=["contract-change"],
            rationale="Existing callers must adapt.",
            affected_domains=["backend"],
            affected_capabilities=["api"],
            compatibility="unsafe in any order",
            residual_risk="medium",
        ),
    )

    result = bootstrap_issue(
        tmp_path,
        epic_number="010",
        epic_title="Adopt New Auth Boundary",
        task_title="Create migration task",
        owner="Ann",
    )

    assert result.epic_dir == "docs/issues/010-adopt-new-auth-boundary-[draft]"
    epic_text = (tmp_path / result.files[1]).read_text(encoding="utf-8")
    task_text = (tmp_path / result.files[2]).read_text(encoding="utf-8")
    assert "domains: backend; capabilities: api" in epic_text
    assert "Move auth boundary. labels: contract-change" in epic_text
    assert "010-adopt-new-auth-boundary" in task_text


def test_bootstrap_issue_normalizes_unicode_titles(tmp_path: Path) -> None:
    _seed_templates(tmp_path)

    result = bootstrap_issue(
        tmp_path,
        epic_number="011",
        epic_title="Adoção e configuración",
        task_title="Revisão",
    )

    assert result.epic_dir == "docs/issues/011-adocao-e-configuracion-[draft]"
    assert result.files[-1].endswith("011-revisao-[draft].md")
