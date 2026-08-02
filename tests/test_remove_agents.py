from __future__ import annotations

import hashlib
import json

from governancekit import cli
from governancekit.remove_agents import apply_removal_plan, build_removal_plan, write_removal_plan


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def make_installed(root, *, content: str = "kit\n"):
    target = root / ".docs" / "agents" / "programmer.md"
    target.parent.mkdir(parents=True)
    target.write_text(content, encoding="utf-8")
    state = root / ".gk"
    state.mkdir()
    (state / "manifest.json").write_text(
        json.dumps({"files": {".docs/agents/programmer.md": digest("kit\n")}}), encoding="utf-8"
    )
    return target


def test_plan_classifies_exact_manifest_file_as_removable(tmp_path) -> None:
    make_installed(tmp_path)

    plan = build_removal_plan(tmp_path)

    item = next(item for item in plan.items if item.path == ".docs/agents/programmer.md")
    assert item.classification == "kit-owned-unchanged"
    assert item.action == "remove"
    assert plan.provider["status"] == "not-invoked"


def test_plan_preserves_modified_or_unknown_files(tmp_path) -> None:
    make_installed(tmp_path, content="kit plus project decision\n")
    custom = tmp_path / ".docs" / "project-notes.md"
    custom.write_text("project content\n", encoding="utf-8")

    plan = build_removal_plan(tmp_path)
    by_path = {item.path: item for item in plan.items}

    assert by_path[".docs/agents/programmer.md"].classification == "kit-owned-modified"
    assert by_path[".docs/agents/programmer.md"].requires_operator_review
    assert by_path[".docs/project-notes.md"].classification == "unknown"
    assert by_path[".docs/project-notes.md"].action == "preserve"


def test_apply_creates_backup_before_removing_only_verified_files(tmp_path) -> None:
    target = make_installed(tmp_path)
    plan = build_removal_plan(tmp_path)

    result = apply_removal_plan(tmp_path, plan)

    assert result.removed == [".docs/agents/programmer.md"]
    assert not target.exists()
    assert (result.backup_dir / ".docs/agents/programmer.md").read_text(encoding="utf-8") == "kit\n"
    manifest = json.loads((result.backup_dir / "restore-manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"] == result.removed


def test_cli_plan_writes_json_and_apply_uses_it(tmp_path, capsys) -> None:
    make_installed(tmp_path)

    assert cli.main(["--root", str(tmp_path), "remove-agents", "plan", "--json"]) == 0
    plan_output = json.loads(capsys.readouterr().out)
    assert plan_output["plan_path"].endswith(".gk/remove-agents-plan.json")
    assert cli.main(["--root", str(tmp_path), "remove-agents", "apply", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["removed"] == [".docs/agents/programmer.md"]


def test_plan_output_cannot_escape_root(tmp_path) -> None:
    make_installed(tmp_path)
    plan = build_removal_plan(tmp_path)
    try:
        write_removal_plan(tmp_path, plan, tmp_path.parent / "escape.json")
    except Exception as exc:
        assert "outside --root" in str(exc)
    else:
        raise AssertionError("expected output outside root to be refused")


def test_llm_extraction_moves_project_content_only_after_explicit_acceptance(tmp_path) -> None:
    target = make_installed(tmp_path, content="generic kit\nLOCAL DECISION\n")
    (tmp_path / ".gk/project-config.json").write_text(
        json.dumps({"providers": [{"name": "test", "mode": "env", "credential_ref": "TEST_KEY", "base_url": "https://example.invalid/v1", "model": "test", "role": "primary"}]}),
        encoding="utf-8",
    )
    plan = build_removal_plan(
        tmp_path, with_llm=True,
        extractor=lambda *_args: ("LOCAL DECISION\n", "generic kit\n", 0.9),
    )
    item = next(item for item in plan.items if item.path == ".docs/agents/programmer.md")
    assert item.action == "extract-project-content"
    try:
        apply_removal_plan(tmp_path, plan)
    except ValueError as exc:
        assert "--accept-project-extractions" in str(exc)
    else:
        raise AssertionError("explicit acceptance must be required")
    result = apply_removal_plan(tmp_path, plan, accept_project_extractions=True)
    assert target.read_text(encoding="utf-8") == "generic kit\n"
    extracted = tmp_path / item.project_destination
    assert extracted.read_text(encoding="utf-8") == "LOCAL DECISION\n"
    assert str(item.project_destination) in (tmp_path / "docs/required-reading.md").read_text(encoding="utf-8")
    assert result.extracted == [item.project_destination]
