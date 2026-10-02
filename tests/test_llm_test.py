from __future__ import annotations

import json
from pathlib import Path

from governancekit import cli
from governancekit.llm_test import (
    LlmTestResult,
    format_llm_test,
    check_configured_providers,
    check_well_known_from_directory,
)


def test_configured_provider_probe_uses_saved_reference(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / ".gk"
    state.mkdir()
    credential = tmp_path / ".credentials/llm/gemini.key"
    credential.parent.mkdir(parents=True)
    credential.write_text("secret-value\n", encoding="utf-8")
    (state / "project-config.json").write_text(
        json.dumps({
            "providers": [{
                "name": "gemini",
                "purpose": "general",
                "base_url": "https://example.invalid/v1",
                "model": "model",
                "mode": "file-ref",
                "credential_ref": ".credentials/llm/gemini.key",
                "validation": "reference-required",
                "role": "primary",
            }]
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "governancekit.llm_test.request_completion",
        lambda *_args, **_kwargs: "OK",
    )

    results = check_configured_providers(tmp_path)

    assert len(results) == 1
    assert results[0].ok
    assert results[0].name == "gemini"


def test_external_credentials_directory_is_not_copied_into_project(tmp_path: Path, monkeypatch) -> None:
    credentials = tmp_path / "personal"
    credentials.mkdir()
    (credentials / "gemini.key").write_text("gemini-secret\n", encoding="utf-8")

    seen = {}

    def fake_completion(provider, root, **kwargs):
        seen[provider.name] = (provider.credential_ref, root)
        return "OK"

    monkeypatch.setattr("governancekit.llm_test.request_completion", fake_completion)

    results = check_well_known_from_directory(credentials)

    assert any(item.name == "gemini" and item.ok for item in results)
    assert not any(path.name == ".credentials" for path in tmp_path.iterdir())
    assert seen["gemini"][0] == ".credentials/llm/gemini.key"


def test_human_output_never_contains_secret() -> None:
    output = format_llm_test([
        LlmTestResult("gemini", "model", True, "reachable; completion returned (OK)")
    ])

    assert "PASS gemini / model" in output
    assert "secret" not in output.lower()


def test_cli_llm_test_returns_failure_when_provider_probe_fails(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "governancekit.llm_test.check_configured_providers",
        lambda _root: [LlmTestResult("gemini", "model", False, "HTTP 404")],
    )

    code = cli.main(["--root", str(tmp_path), "llm", "test"])
    output = capsys.readouterr().out

    assert code == 1
    assert "FAIL gemini / model: HTTP 404" in output


def test_select_external_provider_tests_before_persisting_and_uses_symlink(tmp_path: Path, monkeypatch) -> None:
    from governancekit.llm_select import select_well_known_provider

    credentials = tmp_path / "personal"
    credentials.mkdir()
    external = credentials / "openai.key"
    external.write_text("external-secret\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()

    monkeypatch.setattr(
        "governancekit.llm_select._probe",
        lambda *_args, **_kwargs: LlmTestResult("openai", "gpt-5-mini", True, "reachable"),
    )

    provider, written = select_well_known_provider(
        project, "openai", credentials, development=True
    )

    link = project / ".credentials/llm/openai.key"
    assert link.is_symlink()
    assert link.resolve() == external.resolve()
    assert provider.role == "primary"
    assert provider.validation == "tested-external-reference"
    assert ".gk/project-config.json" in written
    data = json.loads((project / ".gk/project-config.json").read_text())
    serialized = json.dumps(data)
    assert "external-secret" not in serialized
    assert str(external) not in serialized


def test_select_external_provider_does_not_write_on_failed_probe(tmp_path: Path, monkeypatch) -> None:
    from governancekit.llm_select import select_well_known_provider

    credentials = tmp_path / "personal"
    credentials.mkdir()
    (credentials / "openai.key").write_text("secret\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()

    monkeypatch.setattr(
        "governancekit.llm_select._probe",
        lambda *_args, **_kwargs: LlmTestResult("openai", "gpt-5-mini", False, "HTTP 401"),
    )

    try:
        select_well_known_provider(project, "openai", credentials, development=True)
    except RuntimeError as exc:
        assert "failed validation before selection" in str(exc)
    else:
        raise AssertionError("failed provider must not be selected")

    assert not (project / ".credentials").exists()
    assert not (project / ".gk").exists()


def test_configured_test_allows_only_explicitly_tested_external_reference(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / ".gk"
    state.mkdir()
    (state / "project-config.json").write_text(
        json.dumps({
            "providers": [{
                "name": "openai",
                "purpose": "governance-adoption",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-5-mini",
                "mode": "file-ref",
                "credential_ref": ".credentials/llm/openai.key",
                "validation": "tested-external-reference",
                "role": "primary",
            }]
        }),
        encoding="utf-8",
    )

    seen = {}

    def fake_probe(provider, root, *, allow_symlink=False):
        seen["allow_symlink"] = allow_symlink
        return LlmTestResult(provider.name, provider.model, True, "reachable")

    monkeypatch.setattr("governancekit.llm_test._probe", fake_probe)

    results = check_configured_providers(tmp_path)

    assert results[0].ok
    assert seen["allow_symlink"] is True
