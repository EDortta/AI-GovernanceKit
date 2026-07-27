from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from governancekit.context import (
    ContextError,
    DeterministicTokenCounter,
    build_context,
    format_context,
    prune_telemetry,
)


SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["$schema", "version", "base", "tasks", "budgets", "retrieval", "telemetry"],
    "properties": {
        "$schema": {"type": "string"},
        "version": {"const": 1},
        "base": {"type": "object"},
        "project": {"type": "object"},
        "tasks": {"type": "object"},
        "risks": {"type": "object"},
        "budgets": {"type": "object"},
        "retrieval": {"type": "object"},
        "telemetry": {"type": "object"},
        "exclude_by_default": {"type": "array"},
    },
}


def source(path: str, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def make_repo(tmp_path: Path, *, total: int = 1000, category: int = 1000) -> Path:
    root = tmp_path
    schema = root / ".docs/schemas/context-manifest.schema.json"
    schema.parent.mkdir(parents=True)
    schema.write_text(json.dumps(SCHEMA), encoding="utf-8")
    manifest = {
        "$schema": "schemas/context-manifest.schema.json",
        "version": 1,
        "base": {"required": [{"path": "AGENTS.md", "mode": "full"}]},
        "project": {"include": []},
        "tasks": {
            "implementation": {
                "include": [
                    {"path": "programmer.md", "mode": "full", "required": True},
                    {"path": "design.md", "mode": "full", "required": True},
                ]
            },
            "review": {
                "include": [{"path": "reviewer.md", "mode": "full", "required": True}]
            },
            "council": {
                "include": [{"path": "council.md", "mode": "full", "required": True}]
            },
        },
        "risks": {
            "runtime": {
                "include": [{"path": "security.md", "mode": "full", "required": True}]
            },
            "personal_data": {
                "include": [{"path": "privacy.md", "mode": "full", "required": True}]
            },
        },
        "budgets": {
            "total_input_tokens": total,
            "categories": {
                "base_contracts": category,
                "task_contracts": category,
                "risk_contracts": category,
                "project_context": category,
                "active_work": category,
                "retrieved_evidence": category,
                "reserve": 1,
            },
        },
        "retrieval": {"max_sections": 4, "max_section_tokens": 100},
        "exclude_by_default": ["handoff.md", "archive/**"],
        "telemetry": {
            "path": ".gk/context-telemetry.jsonl",
            "retention_days": 30,
            "content_capture": False,
        },
    }
    path = root / ".docs/context-manifest.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    for name in (
        "AGENTS.md",
        "programmer.md",
        "design.md",
        "reviewer.md",
        "council.md",
        "security.md",
        "privacy.md",
    ):
        source(str(root / name), f"# {name}\nunique contract for {name}\n")
    return root


def paths(result) -> list[str]:
    return [item.path for item in result.sources]


def test_task_and_risk_selection_is_explicit(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    implementation = build_context(root, "implementation", risks=["runtime", "personal_data"])
    assert "programmer.md" in paths(implementation)
    assert "design.md" in paths(implementation)
    assert "security.md" in paths(implementation)
    assert "privacy.md" in paths(implementation)
    assert "council.md" not in paths(implementation)
    review = build_context(root, "review")
    assert "programmer.md" not in paths(review)
    assert "reviewer.md" in paths(review)


def test_council_only_loads_for_council_task(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    assert "council.md" in paths(build_context(root, "council"))
    assert "council.md" not in paths(build_context(root, "implementation"))


def test_history_is_not_loaded_by_default(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    source(str(root / "handoff.md"), "historical")
    assert "handoff.md" not in paths(build_context(root, "implementation"))


def test_required_over_budget_fails_without_truncation(tmp_path: Path) -> None:
    root = make_repo(tmp_path, total=5, category=5)
    with pytest.raises(ContextError, match="required context exceeds usable budget"):
        build_context(root, "implementation")


def test_optional_over_budget_is_omitted_with_warning(tmp_path: Path) -> None:
    root = make_repo(tmp_path, total=30, category=30)
    manifest_path = root / ".docs/context-manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    manifest["project"]["include"] = [{"path": "optional.md", "mode": "full"}]
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    source(str(root / "optional.md"), "x" * 200)
    result = build_context(root, "review")
    assert "optional.md" not in paths(result)
    assert any("optional source omitted by budget: optional.md" in item for item in result.warnings)


def test_duplicate_path_is_selected_once_and_reported(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    manifest_path = root / ".docs/context-manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    manifest["project"]["include"] = [{"path": "AGENTS.md", "mode": "full"}]
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    result = build_context(root, "review")
    assert paths(result).count("AGENTS.md") == 1
    assert "duplicate path omitted: AGENTS.md" in result.warnings


def test_identical_content_and_provenance_are_reported(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    same = "# Same\n" + "identical substantial rule block " * 10
    source(str(root / "reviewer.md"), same)
    source(str(root / "copy.md"), same)
    manifest_path = root / ".docs/context-manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    manifest["project"]["include"] = [{"path": "copy.md", "mode": "full"}]
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    result = build_context(root, "review")
    assert any(item["kind"] == "identical_content" for item in result.duplicates)
    reviewer = next(item for item in result.sources if item.path == "reviewer.md")
    assert reviewer.provenance == ("full",)


def test_sections_and_lexical_retrieve_are_deterministic(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    source(str(root / "selected.md"), "# Keep\nalpha rule\n\n# Drop\nbeta rule\n")
    source(str(root / "retrieved.md"), "# Alpha\nimplementation symbol\n\n# Other\nunrelated\n")
    manifest_path = root / ".docs/context-manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    manifest["project"]["include"] = [
        {"path": "selected.md", "mode": "sections", "sections": ["Keep"]},
        {"path": "retrieved.md", "mode": "retrieve", "terms": ["implementation"]},
    ]
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    result = build_context(root, "implementation")
    selected = next(item for item in result.sources if item.path == "selected.md")
    retrieved = next(item for item in result.sources if item.path == "retrieved.md")
    assert "alpha rule" in selected.content and "beta rule" not in selected.content
    assert "implementation symbol" in retrieved.content and "unrelated" not in retrieved.content
    assert retrieved.provenance == ("retrieve:Alpha",)


def test_fallback_count_and_json_are_stable(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    counter = DeterministicTokenCounter()
    assert counter.count("12345") == 2
    first = build_context(root, "review", counter=counter).as_dict()
    second = build_context(root, "review", counter=counter).as_dict()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["exact_count"] is False


def test_category_budget_is_enforced(tmp_path: Path) -> None:
    root = make_repo(tmp_path, total=1000, category=5)
    with pytest.raises(ContextError, match="category exceeds budget: base_contracts"):
        build_context(root, "review")


def test_metadata_only_telemetry_requires_and_records_work_id(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    issue = root / "docs/issues/006/epic.md"
    source(str(issue), "# WK-20260727-context-optimization\nsensitive prompt body")
    build_context(root, "review", issue=issue, write_telemetry=True)
    payload = json.loads((root / ".gk/context-telemetry.jsonl").read_text())
    assert payload["work_id"] == "WK-20260727-context-optimization"
    assert "sensitive prompt body" not in json.dumps(payload)
    assert payload["source_paths"]


def test_human_output_shows_budget_categories_and_largest_sources(tmp_path: Path) -> None:
    output = format_context(build_context(make_repo(tmp_path), "review"))
    assert "Context budget:" in output
    assert "Categories:" in output
    assert "Largest contributors:" in output


def test_real_base_context_stays_under_declared_budget() -> None:
    root = Path(__file__).resolve().parents[2] / "Agents"
    if not (root / ".docs/context-manifest.yaml").is_file():
        pytest.skip("companion AI-Agents checkout is not available")
    result = build_context(root, "implementation", counter=DeterministicTokenCounter())
    assert result.category_tokens["base_contracts"] <= result.category_budgets["base_contracts"]


def test_reserve_reduces_usable_budget_and_declared_order_is_preserved(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    result = build_context(root, "implementation")
    assert result.usable_budget == result.budget - 1
    assert paths(result)[:3] == ["AGENTS.md", "programmer.md", "design.md"]


def test_required_retrieve_without_match_fails(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    manifest_path = root / ".docs/context-manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    manifest["tasks"]["review"]["include"] = [
        {"path": "reviewer.md", "mode": "retrieve", "required": True, "terms": ["absent"]}
    ]
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    source(str(root / "reviewer.md"), "nothing relevant and no markdown headings")
    with pytest.raises(ContextError, match="required retrieval produced no content"):
        build_context(root, "review")


def test_inspect_mode_returns_hard_violations_instead_of_raising(tmp_path: Path) -> None:
    root = make_repo(tmp_path, total=5, category=5)
    result = build_context(root, "implementation", strict=False)
    assert result.exceeded
    assert result.hard_violations


def test_containment_detects_small_document_inside_large_one(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    shared = ["shared rule block " + str(index) + " x" * 80 for index in range(3)]
    source(str(root / "reviewer.md"), "\n\n".join(shared))
    source(str(root / "large.md"), "\n\n".join(shared + ["unique " + str(i) + " y" * 80 for i in range(8)]))
    manifest_path = root / ".docs/context-manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    manifest["project"]["include"] = [{"path": "large.md", "mode": "full"}]
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    result = build_context(root, "review")
    assert any(item["kind"] == "contained_overlap" for item in result.duplicates)


def test_telemetry_has_timestamp_and_prune_applies_retention(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    issue = root / "docs/issues/007/epic.md"
    source(str(issue), "# WK-20260727-context-hardening\n")
    build_context(root, "review", issue=issue, write_telemetry=True)
    telemetry = root / ".gk/context-telemetry.jsonl"
    current = json.loads(telemetry.read_text())
    assert current["timestamp"].endswith("Z")
    old = dict(current)
    now = datetime.now(timezone.utc)
    old["timestamp"] = (now - timedelta(days=31)).isoformat()
    telemetry.write_text(json.dumps(old) + "\n" + json.dumps(current) + "\n")
    assert prune_telemetry(root, now=now) == 1
    assert len(telemetry.read_text().splitlines()) == 1
