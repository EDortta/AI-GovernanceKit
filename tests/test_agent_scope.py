from __future__ import annotations

import unittest

from pathlib import Path
from subprocess import CompletedProcess
import json

from governancekit.agent_scope import _command, _credential_file_path, _provider_failure_detail, propose_project_scope
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

    monkeypatch.setattr("governancekit.agent_scope._urlopen", fake_urlopen)
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


def test_llm_scope_adapter_allows_a_credential_symlink_when_explicitly_enabled(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "docs/product.md"
    source.parent.mkdir()
    source.write_text("product\n", encoding="utf-8")
    credential_store = tmp_path.parent / "operator-credentials"
    credential_store.mkdir()
    profile = credential_store / "openai.json"
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

    monkeypatch.setattr("governancekit.agent_scope._urlopen", fake_urlopen)
    provider = ProviderConfig(
        name="openai", base_url="https://example.test/v1", model="configured-model",
        mode="file-ref", credential_ref=".credentials/openai.json",
    )

    proposal = propose_project_scope(
        tmp_path, "llm-api", ["docs/product.md"], provider=provider,
        allow_project_credential_symlinks=True,
    )

    assert proposal.domain_names == ["sessions"]
    assert captured["authorization"] == "Bearer file-secret"
    assert captured["payload"]["model"] == "profile-model"


def test_llm_scope_adapter_rejects_a_credential_symlink_outside_the_trusted_root(tmp_path: Path) -> None:
    source = tmp_path / "docs/product.md"
    source.parent.mkdir()
    source.write_text("product\n", encoding="utf-8")
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

    with pytest.raises(RuntimeError, match="--credentials-allow-symlinks"):
        propose_project_scope(tmp_path, "llm-api", ["docs/product.md"], provider=provider)

    assert _credential_file_path(
        tmp_path, ".credentials/openai.key", allow_project_credential_symlinks=True
    ) == outside / "openai.key"


# ── the channel the credential travels over ───────────────────────────────────

def test_https_provider_url_is_accepted() -> None:
    from governancekit.agent_scope import validate_provider_url

    assert validate_provider_url("https://api.example.test/v1") == "https://api.example.test/v1"


def test_plain_http_is_refused_because_the_key_would_be_in_the_clear() -> None:
    from governancekit.agent_scope import validate_provider_url

    with pytest.raises(RuntimeError, match="refusing to send a credential over http"):
        validate_provider_url("http://api.example.test/v1")


def test_loopback_http_is_allowed() -> None:
    from governancekit.agent_scope import validate_provider_url

    for url in ("http://localhost:8000/v1", "http://127.0.0.1:8000/v1"):
        assert validate_provider_url(url) == url


def test_a_url_without_a_scheme_is_refused() -> None:
    from governancekit.agent_scope import validate_provider_url

    with pytest.raises(RuntimeError, match="not a valid absolute URL"):
        validate_provider_url("api.example.test/v1")


def test_cross_host_redirect_is_refused_while_carrying_a_credential() -> None:
    import urllib.error
    import urllib.request

    from governancekit.agent_scope import _NoCredentialLeakRedirects

    handler = _NoCredentialLeakRedirects()
    request = urllib.request.Request("https://api.example.test/v1/chat/completions")

    with pytest.raises(urllib.error.URLError, match="cross-host redirect"):
        handler.redirect_request(request, None, 302, "Found", {}, "https://elsewhere.test/collect")


def test_same_host_redirect_is_still_followed() -> None:
    import urllib.request

    from governancekit.agent_scope import _NoCredentialLeakRedirects

    handler = _NoCredentialLeakRedirects()
    request = urllib.request.Request("https://api.example.test/v1/chat/completions")

    redirected = handler.redirect_request(
        request, None, 302, "Found", {}, "https://api.example.test/v2/chat/completions"
    )
    assert redirected is not None


class SourcesMayNotRESOLVEIntoASecretAreaTest(unittest.TestCase):
    """The rule is about the destination, not about the mechanism.

    Refusing every symlink was tried first and was too blunt. Measured, before any
    guard: a monorepo whose `docs/` points OUTSIDE the root was already refused by
    containment, so nothing was gained there; one pointing INSIDE the root read fine
    and is a legitimate layout. Blanket refusal cost that and bought nothing.

    The operator was right that symlinks are the standard credential pattern, and both
    facts he reached for are true — `.credentials/` is gitignored, and git stores mode
    120000 rather than following the link. Neither is a defence: they protect the
    REPOSITORY, and the payload does not go through git. The secret never enters a git
    object; the leak happens on the victim's checkout, against the victim's own store.
    """

    SECRET = "REAL-OPERATOR-TOKEN-DO-NOT-SEND-ANYWHERE"

    def test_a_link_that_lands_in_credentials_is_refused(self) -> None:
        import tempfile

        from governancekit.agent_scope import read_confined_sources

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / ".credentials" / "llm").mkdir(parents=True)
            (root / ".credentials" / "llm" / "openrouter.key").write_text(
                self.SECRET + "\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "vendor-notes.md").symlink_to(
                root / ".credentials" / "llm" / "openrouter.key")

            with self.assertRaises(RuntimeError) as caught:
                read_confined_sources(root, ["docs/vendor-notes.md"])

            self.assertIn(".credentials", str(caught.exception))
            self.assertNotIn(self.SECRET, str(caught.exception))

    def test_a_link_that_lands_in_the_local_state_is_refused(self) -> None:
        # The second door, which no lens found: `.gk/secrets.json` is inside the root,
        # so containment passes, and it holds the local secrets.
        import tempfile

        from governancekit.agent_scope import read_confined_sources

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / ".gk").mkdir()
            (root / ".gk" / "secrets.json").write_text(
                '{"PROJECT_SLUG":"00020126SEGREDO"}\n', encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "y.md").symlink_to(root / ".gk" / "secrets.json")

            with self.assertRaises(RuntimeError):
                read_confined_sources(root, ["docs/y.md"])

    def test_a_legitimate_in_root_symlink_layout_still_reads(self) -> None:
        # `docs/ -> shared/` is an ordinary monorepo shape and must keep working. The
        # first cut of this guard refused it, which was the operator's objection.
        import tempfile

        from governancekit.agent_scope import read_confined_sources

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "shared").mkdir()
            (root / "shared" / "notes.md").write_text("project prose\n", encoding="utf-8")
            (root / "docs").symlink_to(root / "shared")

            self.assertIn("project prose",
                          read_confined_sources(root, ["docs/notes.md"])[0])

    def test_the_copy_path_applies_the_same_rule(self) -> None:
        import tempfile

        from governancekit.agent_scope import _copy_selected_sources

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as dst:
            root = Path(tmp).resolve()
            (root / ".credentials").mkdir()
            (root / ".credentials" / "k").write_text(self.SECRET + "\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "x.md").symlink_to(root / ".credentials" / "k")

            with self.assertRaises(RuntimeError):
                _copy_selected_sources(root, Path(dst), ["docs/x.md"])

    def test_an_ordinary_source_still_reads(self) -> None:
        import tempfile

        from governancekit.agent_scope import read_confined_sources

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "docs").mkdir()
            (root / "docs" / "notes.md").write_text("plain\n", encoding="utf-8")

            self.assertIn("plain", read_confined_sources(root, ["docs/notes.md"])[0])
