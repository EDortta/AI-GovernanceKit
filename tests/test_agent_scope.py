from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
import json

from governancekit.agent_scope import _command, _provider_failure_detail, propose_project_scope
from governancekit.project_config import ProviderConfig
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


def test_cursor_scope_adapter_trusts_only_the_generated_workspace(tmp_path: Path) -> None:
    command = _command("cursor", tmp_path, "prompt", tmp_path / "output.json")

    assert command[:7] == ["cursor", "agent", "--print", "--mode", "ask", "--trust", "--workspace"]


def test_scope_proposal_labels_domains_capabilities_and_open_questions() -> None:
    from governancekit.agent_scope import ProposedDomain, ScopeProposal

    rendered = ScopeProposal(
        summary="Product scope.",
        domains=[ProposedDomain("approvals", ["approve"], ["docs/product.md: scope"])],
        questions=["Which approvals need audit?"],
    ).render()

    assert "evidence gaps to resolve before implementation" in rendered
    assert "not saved answers or required fields" in rendered


def test_provider_failure_detail_does_not_expose_response_data() -> None:
    import io
    import urllib.error

    error = urllib.error.HTTPError("https://example.test", 401, "Unauthorized", {}, io.BytesIO(b"secret response"))

    detail = _provider_failure_detail(error)

    assert detail == "HTTP 401: provider rejected the credential; verify the API key and account access"
    assert "secret" not in detail


def test_llm_scope_adapter_reads_a_project_local_protected_credential_file(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "docs/product.md"
    source.parent.mkdir()
    source.write_text("product\n", encoding="utf-8")
    credential = tmp_path / ".credentials/llm/openai.key"
    credential.parent.mkdir(parents=True)
    credential.write_text("file-secret\n", encoding="utf-8")
    captured: dict[str, str] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": '{"summary":"Product","domains":[{"name":"sessions","capabilities":["manage"],"evidence":["docs/product.md: flow"]}],"questions":[]}'}}]}).encode()

    def fake_urlopen(request, timeout):
        captured["authorization"] = request.headers["Authorization"]
        assert timeout == 90
        return Response()

    monkeypatch.setattr("governancekit.agent_scope.urllib.request.urlopen", fake_urlopen)
    provider = ProviderConfig(
        name="openai",
        base_url="https://example.test/v1",
        model="test-model",
        mode="file-ref",
        credential_ref=".credentials/llm/openai.key",
    )

    proposal = propose_project_scope(tmp_path, "llm-api", ["docs/product.md"], provider=provider)

    assert proposal.domain_names == ["sessions"]
    assert captured["authorization"] == "Bearer file-secret"


def test_llm_scope_adapter_allows_a_symlink_into_the_operator_trusted_credential_root(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "docs/product.md"
    source.parent.mkdir()
    source.write_text("product\n", encoding="utf-8")
    trusted_root = tmp_path / "operator-credentials"
    trusted_root.mkdir()
    profile = trusted_root / "openai.json"
    profile.write_text('{"api_key":"file-secret","model":"profile-model"}', encoding="utf-8")
    credential = tmp_path / ".credentials/openai.json"
    credential.parent.mkdir()
    credential.symlink_to(profile)
    captured: dict[str, object] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": '{"summary":"Product","domains":[{"name":"sessions","capabilities":["manage"],"evidence":["docs/product.md: flow"]}],"questions":[]}'}}]}).encode()

    def fake_urlopen(request, timeout):
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.data)
        assert timeout == 90
        return Response()

    monkeypatch.setattr("governancekit.agent_scope.urllib.request.urlopen", fake_urlopen)
    provider = ProviderConfig(
        name="openai", base_url="https://example.test/v1", model="configured-model",
        mode="file-ref", credential_ref=".credentials/openai.json",
    )

    proposal = propose_project_scope(
        tmp_path, "llm-api", ["docs/product.md"], provider=provider,
        credential_root=trusted_root,
    )

    assert proposal.domain_names == ["sessions"]
    assert captured["authorization"] == "Bearer file-secret"
    assert captured["payload"]["model"] == "profile-model"


def test_llm_scope_adapter_rejects_a_credential_symlink_outside_the_trusted_root(tmp_path: Path) -> None:
    source = tmp_path / "docs/product.md"
    source.parent.mkdir()
    source.write_text("product\n", encoding="utf-8")
    trusted_root = tmp_path / "operator-credentials"
    trusted_root.mkdir()
    outside = tmp_path.parent / "credential-outside"
    outside.mkdir()
    credential = tmp_path / ".credentials/openai.key"
    credential.parent.mkdir()
    credential.symlink_to(outside / "openai.key")
    (outside / "openai.key").write_text("file-secret\n", encoding="utf-8")
    provider = ProviderConfig(
        name="openai", base_url="https://example.test/v1", model="configured-model",
        mode="file-ref", credential_ref=".credentials/openai.key",
    )

    with pytest.raises(RuntimeError, match="trusted credential roots"):
        propose_project_scope(
            tmp_path, "llm-api", ["docs/product.md"], provider=provider,
            credential_root=trusted_root,
        )
