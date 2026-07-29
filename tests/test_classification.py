from __future__ import annotations

import json
from pathlib import Path

from governancekit import cli
from governancekit.classification import (
    _CLASSIFICATION_FILE,
    build_change_classification,
    load_change_classification,
    save_change_classification,
)


def test_build_requires_valid_labels() -> None:
    classification = build_change_classification(
        summary="Add adoption state",
        labels=["additive", "migration"],
        rationale="Persists new shareable config for adoption flows.",
        affected_domains=["governance"],
        affected_capabilities=["configuration"],
        compatibility="safe in any order",
        residual_risk="low",
    )

    assert classification.approvals_required == ["human-review:migration", "normal-issue-approval"] or classification.approvals_required == ["normal-issue-approval", "human-review:migration"]


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    classification = build_change_classification(
        summary="Change API contract",
        labels=["contract-change"],
        rationale="Existing callers must adapt to the new shape.",
        affected_domains=["api"],
        affected_capabilities=["public-contract"],
        compatibility="server first is unsafe",
        residual_risk="medium",
    )

    rel = save_change_classification(tmp_path, classification)

    assert rel == _CLASSIFICATION_FILE
    loaded = load_change_classification(tmp_path)
    assert loaded is not None
    assert loaded.summary == "Change API contract"


def test_cli_plan_apply_show_roundtrip(tmp_path: Path, capsys) -> None:
    code = cli.main(
        [
            "--root",
            str(tmp_path),
            "classify-change",
            "plan",
            "--summary",
            "Move secrets to file refs",
            "--label",
            "security-sensitive",
            "--label",
            "migration",
            "--rationale",
            "Tracked config must stop carrying inline credentials.",
            "--domain",
            "identity",
            "--capability",
            "provider-configuration",
            "--compatibility",
            "manual rollout required",
            "--residual-risk",
            "rotation still requires operator",
        ]
    )
    assert code == 0
    assert "security-sensitive" in capsys.readouterr().out

    code = cli.main(
        [
            "--root",
            str(tmp_path),
            "classify-change",
            "apply",
            "--summary",
            "Move secrets to file refs",
            "--label",
            "security-sensitive",
            "--label",
            "migration",
            "--rationale",
            "Tracked config must stop carrying inline credentials.",
            "--domain",
            "identity",
            "--capability",
            "provider-configuration",
            "--compatibility",
            "manual rollout required",
            "--residual-risk",
            "rotation still requires operator",
        ]
    )
    assert code == 0
    capsys.readouterr()

    code = cli.main(["--root", str(tmp_path), "classify-change", "show", "--json"])
    assert code == 0
    current = json.loads(capsys.readouterr().out)
    assert current["labels"] == ["migration", "security-sensitive"]
