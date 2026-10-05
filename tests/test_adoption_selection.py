from __future__ import annotations

import json
from pathlib import Path

import yaml

from governancekit import cli
from governancekit.adoption_selection import (
    KitCandidate,
    _parse,
    build_kit_catalog,
    format_adoption_selection_plan,
    AdoptionSelectionPlan,
    SelectionDecision,
)


def test_catalog_collects_agents_workflows_and_profiles(tmp_path: Path) -> None:
    (tmp_path / ".docs/agents").mkdir(parents=True)
    (tmp_path / ".docs/workflows").mkdir(parents=True)
    (tmp_path / "AGENTS.md").write_text("# Core\nbase contract\n", encoding="utf-8")
    (tmp_path / ".docs/agents/programmer.md").write_text("# Programmer\nimplementation rules\n", encoding="utf-8")
    (tmp_path / ".docs/workflows/git.md").write_text("# Delivery\ngit rules\n", encoding="utf-8")
    manifest = {
        "base": {"required": ["AGENTS.md"]},
        "tasks": {
            "implementation": {"include": [".docs/agents/programmer.md"]},
            "delivery": {"include": [".docs/workflows/git.md"]},
        },
    }
    (tmp_path / ".docs/context-manifest.yaml").write_text(
        yaml.safe_dump(manifest), encoding="utf-8"
    )

    catalog = build_kit_catalog(tmp_path)
    by_path = {item.path: item for item in catalog}

    assert set(by_path) == {
        "AGENTS.md",
        ".docs/agents/programmer.md",
        ".docs/workflows/git.md",
    }
    assert by_path["AGENTS.md"].profiles == ("base",)
    assert by_path[".docs/agents/programmer.md"].profiles == ("implementation",)


def test_selection_parser_requires_exactly_one_decision_per_catalog_path() -> None:
    catalog = [
        KitCandidate("AGENTS.md", "Core", "base", ("base",)),
        KitCandidate(".docs/agents/programmer.md", "Programmer", "rules", ("implementation",)),
    ]
    raw = json.dumps({
        "decisions": [
            {"path": "AGENTS.md", "action": "include", "reason": "core contract", "condition": None},
            {
                "path": ".docs/agents/programmer.md",
                "action": "conditional",
                "reason": "needed for implementation",
                "condition": "when implementing code",
            },
        ]
    })

    decisions = _parse(raw, catalog)

    assert [item.action for item in decisions] == ["include", "conditional"]


def test_selection_parser_rejects_invented_paths() -> None:
    catalog = [KitCandidate("AGENTS.md", "Core", "base", ("base",))]
    raw = json.dumps({
        "decisions": [
            {"path": "invented.md", "action": "include", "reason": "guess", "condition": None}
        ]
    })

    try:
        _parse(raw, catalog)
    except RuntimeError as exc:
        assert "unknown or duplicate" in str(exc)
    else:
        raise AssertionError("invented catalog paths must be rejected")


def test_human_plan_separates_include_conditional_and_exclude(tmp_path: Path) -> None:
    plan = AdoptionSelectionPlan(
        root=tmp_path,
        ai_agents_ref="feature/v2-change-governance",
        provider="test / model",
        project_sources=("README.md",),
        decisions=(
            SelectionDecision("AGENTS.md", "include", "core"),
            SelectionDecision("review.md", "conditional", "review only", "when reviewing"),
            SelectionDecision("email.md", "exclude", "not used"),
        ),
    )

    output = format_adoption_selection_plan(plan)

    assert "INCLUDE (1)" in output
    assert "CONDITIONAL (1)" in output
    assert "EXCLUDE (1)" in output


def test_llm_show_reports_reference_without_reading_secret(tmp_path: Path, capsys) -> None:
    state = tmp_path / ".gk"
    state.mkdir()
    credential = tmp_path / ".credentials/llm/openai.key"
    credential.parent.mkdir(parents=True)
    credential.write_text("super-secret-value\n", encoding="utf-8")
    (state / "project-config.json").write_text(
        json.dumps({
            "providers": [{
                "name": "openai",
                "purpose": "governance-adoption",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-test",
                "mode": "file-ref",
                "credential_ref": ".credentials/llm/openai.key",
                "validation": "reference-required",
                "role": "primary",
            }]
        }),
        encoding="utf-8",
    )

    code = cli.main(["--root", str(tmp_path), "llm", "show"])
    output = capsys.readouterr().out

    assert code == 0
    assert ".credentials/llm/openai.key" in output
    assert "super-secret-value" not in output


def test_adoption_plan_uses_configured_provider_and_never_writes_project(tmp_path: Path, monkeypatch) -> None:
    from governancekit.adoption_selection import build_adoption_selection_plan

    (tmp_path / "README.md").write_text("# Demo\nPython automation project.\n", encoding="utf-8")
    state = tmp_path / ".gk"
    state.mkdir()
    (state / "project-config.json").write_text(
        json.dumps({
            "providers": [{
                "name": "test",
                "purpose": "governance-adoption",
                "base_url": "https://example.invalid/v1",
                "model": "model",
                "mode": "env",
                "credential_ref": "TEST_KEY",
                "validation": "reference-required",
                "role": "primary",
            }]
        }),
        encoding="utf-8",
    )

    kit = tmp_path / "kit"
    (kit / ".docs/agents").mkdir(parents=True)
    (kit / "AGENTS.md").write_text("# Core\ncore rules\n", encoding="utf-8")
    (kit / ".docs/agents/programmer.md").write_text("# Programmer\nprogramming rules\n", encoding="utf-8")

    monkeypatch.setattr("governancekit.adoption_selection._download", lambda *_args, **_kwargs: kit)

    def fake_completion(*_args, **_kwargs):
        return json.dumps({
            "decisions": [
                {"path": "AGENTS.md", "action": "include", "reason": "core governance", "condition": None},
                {
                    "path": ".docs/agents/programmer.md",
                    "action": "conditional",
                    "reason": "only during implementation",
                    "condition": "when changing code",
                },
            ]
        })

    monkeypatch.setattr("governancekit.adoption_selection.request_completion", fake_completion)

    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    plan = build_adoption_selection_plan(tmp_path, development=True)
    after = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))

    assert before == after
    assert plan.ai_agents_ref == "feature/v2-change-governance"
    assert plan.provider == "test / model"
    assert len(plan.decisions) == 2
