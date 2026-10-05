from __future__ import annotations

import json
from pathlib import Path

from governancekit.adoption_flow import (
    MANIFEST_FILE,
    PLAN_FILE,
    SOURCES_FILE,
    analyze_adoption,
    apply_adoption,
    discover_documentation,
    parse_source_selection,
    save_selected_sources,
    _parse_json_object,
    DESCRIPTION_PROPOSAL_FILE,
    PROJECT_DESCRIPTION_FILE,
    accept_description_proposal,
    build_description_proposal,
    reject_description_proposal,
)



def _seed_kit_runtime(kit: Path) -> None:
    import yaml
    (kit / ".docs/schemas").mkdir(parents=True, exist_ok=True)
    (kit / ".docs/schemas/context-manifest.schema.json").write_text(
        json.dumps({
            "type": "object",
            "required": ["$schema", "version", "base", "tasks", "budgets", "retrieval", "telemetry"],
            "properties": {}
        }),
        encoding="utf-8",
    )
    (kit / ".docs/context-manifest.yaml").write_text(
        yaml.safe_dump({
            "$schema": "schemas/context-manifest.schema.json",
            "version": 1,
            "base": {"required": [{"path": "AGENTS.md", "mode": "full"}]},
            "project": {"include": [{"path": "docs/project-rules.md", "mode": "full"}]},
            "tasks": {"implementation": {"include": [{"path": ".docs/agents/security.md", "mode": "full", "required": True}]}},
            "risks": {},
            "budgets": {"total_input_tokens": 22000, "categories": {
                "base_contracts": 8000, "task_contracts": 8500, "risk_contracts": 4500,
                "project_context": 1000, "active_work": 3500, "retrieved_evidence": 1000, "reserve": 1000
            }},
            "retrieval": {"max_sections": 4, "max_section_tokens": 500},
            "telemetry": {"path": ".gk/context-telemetry.jsonl", "retention_days": 30, "content_capture": False},
        }, sort_keys=False),
        encoding="utf-8",
    )


def test_discover_documentation_finds_common_doc_roots(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "architecture.md").write_text("# Architecture\nSystem definition\n", encoding="utf-8")
    debates = docs / "agents"
    debates.mkdir()
    (debates / "debate.md").write_text("history\n", encoding="utf-8")

    found = discover_documentation(tmp_path)
    paths = {item.path for item in found}

    assert "README.md" in paths
    assert "docs/" in paths


def test_selected_sources_expand_directories_and_are_repeatable(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("a\n", encoding="utf-8")
    (docs / "b.md").write_text("b\n", encoding="utf-8")

    selected = save_selected_sources(tmp_path, ["docs/"])
    selected_again = save_selected_sources(tmp_path, ["docs/"])

    assert selected == ["docs/a.md", "docs/b.md"]
    assert selected_again == selected
    assert json.loads((tmp_path / SOURCES_FILE).read_text())["sources"] == selected


def test_analyze_writes_complete_ranked_plan_with_token_cost(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("# Demo\nPython app\n", encoding="utf-8")
    save_selected_sources(tmp_path, ["README.md"])

    config = tmp_path / ".gk/project-config.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({"providers": [{
        "name": "test",
        "purpose": "governance-adoption",
        "base_url": "https://example.invalid/v1",
        "model": "model",
        "mode": "env",
        "credential_ref": "TEST_KEY",
        "validation": "reference-required",
        "role": "primary",
    }]}), encoding="utf-8")

    kit = tmp_path / "kit"
    (kit / ".docs/agents").mkdir(parents=True)
    (kit / "AGENTS.md").write_text("# Core\nbase governance\n", encoding="utf-8")
    (kit / ".docs/agents/security.md").write_text("# Security\nsecure changes\n", encoding="utf-8")

    monkeypatch.setattr("governancekit.adoption_flow._download", lambda *_a, **_k: kit)
    monkeypatch.setattr("governancekit.adoption_flow.request_completion", lambda *_a, **_k: json.dumps({
        "modules": [
            {"path": "AGENTS.md", "priority": "core", "reason": "base contract", "condition": None},
            {"path": ".docs/agents/security.md", "priority": "on-demand", "reason": "security work", "condition": "when changing security-sensitive code"},
        ]
    }))

    modules = analyze_adoption(tmp_path, development=True)

    assert [item.priority for item in modules] == ["core", "on-demand"]
    assert [item.selected for item in modules] == [True, False]
    assert all(item.estimated_tokens > 0 for item in modules)
    plan = json.loads((tmp_path / PLAN_FILE).read_text())
    assert len(plan["modules"]) == 2
    assert all("estimated_tokens" in item for item in plan["modules"])


def test_apply_copies_only_selected_and_keeps_overrides_project_owned(tmp_path: Path, monkeypatch) -> None:
    kit = tmp_path / "kit"
    (kit / ".docs/agents").mkdir(parents=True)
    (kit / "AGENTS.md").write_text("# Core\n", encoding="utf-8")
    (kit / ".docs/agents/security.md").write_text("# Security\n", encoding="utf-8")
    _seed_kit_runtime(kit)

    plan_path = tmp_path / PLAN_FILE
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(json.dumps({
        "ai_agents_ref": "feature/v2-change-governance",
        "modules": [
            {"path": "AGENTS.md", "selected": True},
            {"path": ".docs/agents/security.md", "selected": False},
        ],
    }), encoding="utf-8")
    monkeypatch.setattr("governancekit.adoption_flow._download", lambda *_a, **_k: kit)

    written = apply_adoption(tmp_path, development=True)

    assert (tmp_path / "AGENTS.md").is_file()
    assert not (tmp_path / ".docs/agents/security.md").exists()
    assert (tmp_path / "docs/ai-governance/overrides/README.md").is_file()
    manifest = json.loads((tmp_path / MANIFEST_FILE).read_text())
    assert set(manifest["files"]) == {
        "AGENTS.md",
        ".docs/context-manifest.yaml",
        ".docs/schemas/context-manifest.schema.json",
    }
    assert "docs/ai-governance/overrides/README.md" in written


def test_apply_refuses_modified_managed_module(tmp_path: Path, monkeypatch) -> None:
    kit = tmp_path / "kit"
    kit.mkdir()
    (kit / "AGENTS.md").write_text("new kit\n", encoding="utf-8")
    _seed_kit_runtime(kit)

    plan_path = tmp_path / PLAN_FILE
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(json.dumps({
        "ai_agents_ref": "feature/v2-change-governance",
        "modules": [{"path": "AGENTS.md", "selected": True}],
    }), encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("local edit\n", encoding="utf-8")
    monkeypatch.setattr("governancekit.adoption_flow._download", lambda *_a, **_k: kit)

    try:
        apply_adoption(tmp_path, development=True)
    except RuntimeError as exc:
        assert "refusing to overwrite unowned or modified module" in str(exc)
    else:
        raise AssertionError("managed-module overwrite must be refused")


def test_reassessed_apply_removes_only_unchanged_deselected_module(tmp_path: Path, monkeypatch) -> None:
    kit = tmp_path.parent / "kit-reassess"
    (kit / ".docs/agents").mkdir(parents=True)
    (kit / "AGENTS.md").write_text("# Core\n", encoding="utf-8")
    (kit / ".docs/agents/security.md").write_text("# Security\n", encoding="utf-8")
    _seed_kit_runtime(kit)
    monkeypatch.setattr("governancekit.adoption_flow._download", lambda *_a, **_k: kit)

    plan_path = tmp_path / PLAN_FILE
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(json.dumps({
        "ai_agents_ref": "feature/v2-change-governance",
        "modules": [
            {"path": "AGENTS.md", "selected": True},
            {"path": ".docs/agents/security.md", "selected": True},
        ],
    }), encoding="utf-8")
    apply_adoption(tmp_path, development=True)
    assert (tmp_path / ".docs/agents/security.md").is_file()

    plan_path.write_text(json.dumps({
        "ai_agents_ref": "feature/v2-change-governance",
        "modules": [
            {"path": "AGENTS.md", "selected": True},
            {"path": ".docs/agents/security.md", "selected": False},
        ],
    }), encoding="utf-8")
    written = apply_adoption(tmp_path, development=True)

    assert not (tmp_path / ".docs/agents/security.md").exists()
    assert "removed:.docs/agents/security.md" in written


def test_numbered_source_selection_supports_ranges(tmp_path: Path) -> None:
    sources = [
        type("S", (), {"path": "README.md"})(),
        type("S", (), {"path": "docs/"})(),
        type("S", (), {"path": "architecture/"})(),
    ]
    assert parse_source_selection("1,3", sources) == ["README.md", "architecture/"]
    assert parse_source_selection("1-2", sources) == ["README.md", "docs/"]


def test_no_track_managed_ignores_kit_but_not_project_overrides(tmp_path: Path, monkeypatch) -> None:
    kit = tmp_path.parent / "kit-ignore"
    (kit / ".docs/agents").mkdir(parents=True)
    (kit / "AGENTS.md").write_text("# Core\n", encoding="utf-8")
    _seed_kit_runtime(kit)
    monkeypatch.setattr("governancekit.adoption_flow._download", lambda *_a, **_k: kit)

    plan_path = tmp_path / PLAN_FILE
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(json.dumps({
        "ai_agents_ref": "feature/v2-change-governance",
        "modules": [{"path": "AGENTS.md", "selected": True}],
    }), encoding="utf-8")

    apply_adoption(tmp_path, development=True, track_managed=False)
    ignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")

    assert ".docs/" in ignore
    assert "AGENTS.md" in ignore
    assert "docs/ai-governance/overrides" not in ignore


def test_parse_json_object_accepts_fenced_json() -> None:
    raw = """```json
{"modules": []}
```"""
    assert _parse_json_object(raw) == {"modules": []}


def test_analyze_retries_once_when_first_response_is_malformed_json(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("# Demo\nPython app\n", encoding="utf-8")
    save_selected_sources(tmp_path, ["README.md"])

    config = tmp_path / ".gk/project-config.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({"providers": [{
        "name": "test",
        "purpose": "governance-adoption",
        "base_url": "https://example.invalid/v1",
        "model": "model",
        "mode": "env",
        "credential_ref": "TEST_KEY",
        "validation": "reference-required",
        "role": "primary",
    }]}), encoding="utf-8")

    kit = tmp_path / "kit"
    (kit / ".docs/agents").mkdir(parents=True)
    (kit / "AGENTS.md").write_text("# Core\nbase governance\n", encoding="utf-8")
    (kit / ".docs/agents/security.md").write_text("# Security\nsecure changes\n", encoding="utf-8")
    monkeypatch.setattr("governancekit.adoption_flow._download", lambda *_a, **_k: kit)

    responses = iter([
        '{"modules": [',
        json.dumps({"modules": [
            {"path": "AGENTS.md", "priority": "core", "reason": "base contract", "condition": None},
            {"path": ".docs/agents/security.md", "priority": "exclude", "reason": "not needed", "condition": None},
        ]}),
    ])
    monkeypatch.setattr(
        "governancekit.adoption_flow.request_completion",
        lambda *_a, **_k: next(responses),
    )

    modules = analyze_adoption(tmp_path, development=True)

    assert [item.priority for item in modules] == ["core", "exclude"]


def test_language_specific_audit_is_excluded_when_language_is_not_detected(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("# Demo\nPython project\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    save_selected_sources(tmp_path, ["README.md"])

    config = tmp_path / ".gk/project-config.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({"providers": [{
        "name": "test",
        "purpose": "governance-adoption",
        "base_url": "https://example.invalid/v1",
        "model": "model",
        "mode": "env",
        "credential_ref": "TEST_KEY",
        "validation": "reference-required",
        "role": "primary",
    }]}), encoding="utf-8")

    kit = tmp_path / "kit"
    (kit / ".docs/workflows").mkdir(parents=True)
    (kit / "AGENTS.md").write_text("# Core\n", encoding="utf-8")
    (kit / ".docs/workflows/php-audit.md").write_text("# PHP Audit\n", encoding="utf-8")
    monkeypatch.setattr("governancekit.adoption_flow._download", lambda *_a, **_k: kit)
    monkeypatch.setattr("governancekit.adoption_flow.request_completion", lambda *_a, **_k: json.dumps({
        "modules": [
            {"path": "AGENTS.md", "priority": "core", "reason": "base", "condition": None},
            {"path": ".docs/workflows/php-audit.md", "priority": "high", "reason": "generic audit", "condition": None},
        ]
    }))

    modules = analyze_adoption(tmp_path, development=True)
    by_path = {item.path: item for item in modules}

    assert by_path[".docs/workflows/php-audit.md"].priority == "exclude"
    assert by_path[".docs/workflows/php-audit.md"].selected is False
    assert "Excluded deterministically" in by_path[".docs/workflows/php-audit.md"].reason


def test_governance_floor_and_trigger_ceiling_for_software_project(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("# Demo\nBrowser outreach tool\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    save_selected_sources(tmp_path, ["README.md"])

    config = tmp_path / ".gk/project-config.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({"providers": [{
        "name": "test",
        "purpose": "governance-adoption",
        "base_url": "https://example.invalid/v1",
        "model": "model",
        "mode": "env",
        "credential_ref": "TEST_KEY",
        "validation": "reference-required",
        "role": "primary",
    }]}), encoding="utf-8")

    kit = tmp_path / "kit"
    (kit / ".docs/agents").mkdir(parents=True)
    (kit / ".docs/workflows").mkdir(parents=True)
    for rel in [
        "AGENTS.md",
        ".docs/agents/change-governance.md",
        ".docs/agents/programmer.md",
        ".docs/agents/reviewer.md",
        ".docs/agents/design-standards.md",
        ".docs/workflows/delivery-loop.md",
        ".docs/workflows/git-delivery.md",
        ".docs/workflows/sending-email.md",
    ]:
        path = kit / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Module\n", encoding="utf-8")

    monkeypatch.setattr("governancekit.adoption_flow._download", lambda *_a, **_k: kit)
    monkeypatch.setattr("governancekit.adoption_flow.request_completion", lambda *_a, **_k: json.dumps({
        "modules": [
            {"path": "AGENTS.md", "priority": "exclude", "reason": "not relevant", "condition": None},
            {"path": ".docs/agents/change-governance.md", "priority": "exclude", "reason": "not relevant", "condition": None},
            {"path": ".docs/agents/programmer.md", "priority": "exclude", "reason": "not relevant", "condition": None},
            {"path": ".docs/agents/reviewer.md", "priority": "exclude", "reason": "not relevant", "condition": None},
            {"path": ".docs/agents/design-standards.md", "priority": "exclude", "reason": "not relevant", "condition": None},
            {"path": ".docs/workflows/delivery-loop.md", "priority": "exclude", "reason": "not relevant", "condition": None},
            {"path": ".docs/workflows/git-delivery.md", "priority": "exclude", "reason": "not relevant", "condition": None},
            {"path": ".docs/workflows/sending-email.md", "priority": "core", "reason": "outreach sends email", "condition": None},
        ]
    }))

    modules = analyze_adoption(tmp_path, development=True)
    by_path = {item.path: item for item in modules}

    assert by_path["AGENTS.md"].priority == "core"
    assert by_path[".docs/agents/change-governance.md"].priority == "core"
    assert by_path[".docs/agents/programmer.md"].priority == "core"
    assert by_path[".docs/agents/reviewer.md"].priority == "high"
    assert by_path[".docs/agents/design-standards.md"].priority == "high"
    assert by_path[".docs/workflows/delivery-loop.md"].priority == "high"
    assert by_path[".docs/workflows/git-delivery.md"].priority == "high"
    assert by_path[".docs/workflows/sending-email.md"].priority == "on-demand"
    assert by_path[".docs/workflows/sending-email.md"].selected is False


def _write_test_provider(root: Path) -> None:
    config = root / ".gk/project-config.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({"providers": [{
        "name": "test",
        "purpose": "governance-adoption",
        "base_url": "https://example.invalid/v1",
        "model": "model",
        "mode": "env",
        "credential_ref": "TEST_KEY",
        "validation": "reference-required",
        "role": "primary",
    }]}), encoding="utf-8")


def test_description_proposal_does_not_write_project_docs_until_accepted(tmp_path: Path, monkeypatch) -> None:
    _write_test_provider(tmp_path)
    monkeypatch.setattr(
        "governancekit.adoption_flow.request_completion",
        lambda *_a, **_k: "# Demo\n\nA browser outreach helper.",
    )

    proposal = build_description_proposal(
        tmp_path,
        {"name": "Demo", "purpose": "Assist job outreach"},
    )

    assert "browser outreach" in proposal
    assert (tmp_path / DESCRIPTION_PROPOSAL_FILE).is_file()
    assert not (tmp_path / PROJECT_DESCRIPTION_FILE).exists()

    target = accept_description_proposal(tmp_path)
    assert target == tmp_path / PROJECT_DESCRIPTION_FILE
    assert target.read_text(encoding="utf-8").startswith("# Demo")


def test_description_reject_discards_proposal_without_project_write(tmp_path: Path, monkeypatch) -> None:
    _write_test_provider(tmp_path)
    monkeypatch.setattr(
        "governancekit.adoption_flow.request_completion",
        lambda *_a, **_k: "# Demo\n\nProposal.",
    )
    build_description_proposal(tmp_path, {"name": "Demo"})

    assert reject_description_proposal(tmp_path) is True
    assert not (tmp_path / DESCRIPTION_PROPOSAL_FILE).exists()
    assert not (tmp_path / PROJECT_DESCRIPTION_FILE).exists()


def test_description_accept_refuses_to_overwrite_existing_project_description(tmp_path: Path, monkeypatch) -> None:
    _write_test_provider(tmp_path)
    monkeypatch.setattr(
        "governancekit.adoption_flow.request_completion",
        lambda *_a, **_k: "# Proposed\n",
    )
    build_description_proposal(tmp_path, {"name": "Demo"})
    existing = tmp_path / PROJECT_DESCRIPTION_FILE
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("# Existing\n", encoding="utf-8")

    try:
        accept_description_proposal(tmp_path)
    except RuntimeError as exc:
        assert "refusing to overwrite existing project description" in str(exc)
    else:
        raise AssertionError("existing project description must not be overwritten")

    assert existing.read_text(encoding="utf-8") == "# Existing\n"
