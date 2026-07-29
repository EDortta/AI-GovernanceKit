from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

from governancekit.agent_scope import propose_project_scope
import pytest


def test_codex_scope_proposal_is_read_only_and_parsed(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "docs/product.md"
    source.parent.mkdir()
    source.write_text("product\n", encoding="utf-8")

    def fake_run(command, **_kwargs):
        workspace = Path(command[command.index("--cd") + 1])
        assert workspace != tmp_path
        assert (workspace / "docs/product.md").read_text(encoding="utf-8") == "product\n"
        output_index = command.index("-o") + 1
        Path(command[output_index]).write_text(
            '{"summary":"Product","domains":[{"name":"sessions","capabilities":["manage"],"evidence":["docs/product.md: flow"]}],"questions":[]}',
            encoding="utf-8",
        )
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("governancekit.agent_scope.shutil.which", lambda _name: "/usr/bin/fake")
    monkeypatch.setattr("governancekit.agent_scope.subprocess.run", fake_run)

    proposal = propose_project_scope(tmp_path, "openai-agents", ["docs/product.md"])

    assert proposal.domain_names == ["sessions"]
    assert proposal.capabilities_for("sessions") == ["manage"]


def test_scope_proposal_rejects_evidence_outside_selected_sources(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "docs/product.md"
    source.parent.mkdir()
    source.write_text("product\n", encoding="utf-8")
    def fake_run(command, **_kwargs):
        output_index = command.index("-o") + 1
        Path(command[output_index]).write_text(
            '{"summary":"Product","domains":[{"name":"sessions","capabilities":["manage"],"evidence":["docs/secret.md: claim"]}],"questions":[]}',
            encoding="utf-8",
        )
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("governancekit.agent_scope.shutil.which", lambda _name: "/usr/bin/fake")
    monkeypatch.setattr("governancekit.agent_scope.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="outside the selected sources"):
        propose_project_scope(tmp_path, "openai-agents", ["docs/product.md"])
