from __future__ import annotations

import json
from pathlib import Path

from governancekit import cli
from governancekit.classification import build_change_classification, save_change_classification
from governancekit.config_session import load_config_session


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


def test_session_requires_approvals_before_apply(tmp_path: Path, capsys) -> None:
    _seed_contract(tmp_path)
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    save_change_classification(
        tmp_path,
        build_change_classification(
            summary="Migrate auth contract",
            labels=["migration", "contract-change"],
            rationale="Existing callers will adapt.",
            affected_domains=["backend"],
            affected_capabilities=["api"],
            compatibility="unsafe in any order",
            residual_risk="medium",
        ),
    )

    code = cli.main(
        [
            "--root",
            str(tmp_path),
            "config-session",
            "start",
            "--project-name",
            "Demo",
            "--domain",
            "backend",
            "--capability",
            "api",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "pending_approval" in out
    assert "configuration plan is saved but has not been applied" in out
    assert "config-session approve --approval project-config-review" in out
    assert "config-session approve --approval existing-project-adoption-review" in out
    assert "config-session apply" in out

    code = cli.main(["--root", str(tmp_path), "config-session", "apply"])
    assert code == 1
    assert "missing:" in capsys.readouterr().out

    for approval in [
        "project-config-review",
        "existing-project-adoption-review",
        "normal-issue-approval",
        "human-review:contract-change",
        "human-review:migration",
    ]:
        code = cli.main(
            ["--root", str(tmp_path), "config-session", "approve", "--approval", approval]
        )
        assert code == 0
        capsys.readouterr()

    code = cli.main(["--root", str(tmp_path), "config-session", "apply"])
    assert code == 0
    assert ".gk/project-config.json" in capsys.readouterr().out
    session = load_config_session(tmp_path)
    assert session is not None
    assert session.status == "applied"
    config = json.loads((tmp_path / ".gk" / "project-config.json").read_text(encoding="utf-8"))
    assert config["project_name"] == "Demo"
    assert config["capability_domains"]["api"] == "backend"


def test_show_session_as_json(tmp_path: Path, capsys) -> None:
    _seed_contract(tmp_path)
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")

    code = cli.main(["--root", str(tmp_path), "config-session", "start", "--json"])
    assert code == 0
    capsys.readouterr()

    code = cli.main(["--root", str(tmp_path), "config-session", "show", "--json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "pending_approval"


def test_approval_output_explains_next_command(tmp_path: Path, capsys) -> None:
    _seed_contract(tmp_path)
    cli.main(["--root", str(tmp_path), "config-session", "start", "--json"])
    capsys.readouterr()

    code = cli.main(
        ["--root", str(tmp_path), "config-session", "approve", "--approval", "project-config-review"]
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "all required approvals are granted" in output
    assert "apply: governancekit --root" in output


def test_session_rejects_configured_provider_without_credential_reference(
    tmp_path: Path, capsys
) -> None:
    _seed_contract(tmp_path)

    code = cli.main(
        [
            "--root",
            str(tmp_path),
            "config-session",
            "start",
            "--provider",
            "openai:env",
        ]
    )

    assert code == 1
    assert "credential_ref" in capsys.readouterr().out
