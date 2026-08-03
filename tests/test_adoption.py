import json

from governancekit.adoption import (
    apply_adoption_proposal,
    build_adoption_proposal,
    detect_project_drift,
    format_adoption_proposal,
)
from governancekit.agent_scope import ProposedDomain, ScopeProposal


def test_generated_adoption_is_evidence_based_and_sets_readiness(tmp_path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    proposal = build_adoption_proposal(tmp_path)
    written = apply_adoption_proposal(proposal)
    assert written == [".docs/software-overview.md", ".docs/limits.md"]
    assert "project_context_ready: yes" in (tmp_path / ".docs/software-overview.md").read_text()
    assert "limits_ready: yes" in (tmp_path / ".docs/limits.md").read_text()


def test_adoption_never_overwrites_complete_project_documents(tmp_path) -> None:
    docs = tmp_path / ".docs"
    docs.mkdir()
    (docs / "software-overview.md").write_text("project_context_ready: yes\ncustom\n")
    (docs / "limits.md").write_text("limits_ready: yes\ncustom\n")
    assert apply_adoption_proposal(build_adoption_proposal(tmp_path)) == []
    assert "custom" in (docs / "software-overview.md").read_text()


def test_drift_is_advisory_and_compares_current_discovery_to_accepted_config(tmp_path) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"name": "demo", "dependencies": {"react": "1"}}), encoding="utf-8")
    state = tmp_path / ".gk"
    state.mkdir()
    (state / "project-config.json").write_text(json.dumps({"frameworks": [], "languages": [], "package_managers": [], "providers": []}), encoding="utf-8")
    drift = detect_project_drift(tmp_path)
    assert "new framework detected: react" in drift


def test_configured_primary_llm_enriches_proposal_without_persisting_credentials(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "required-reading.md").write_text("- (none)\n", encoding="utf-8")
    state = tmp_path / ".gk"
    state.mkdir()
    (state / "project-config.json").write_text(json.dumps({"providers": [{"name": "test", "mode": "env", "credential_ref": "TEST_KEY", "base_url": "https://example.invalid/v1", "model": "test", "role": "primary"}]}), encoding="utf-8")
    monkeypatch.setattr("governancekit.agent_scope.propose_project_scope", lambda *_args, **_kwargs: ScopeProposal("LLM summary", [ProposedDomain("core", ["serve"], ["README.md: documented"])], ["confirm deploy"]))
    proposal = build_adoption_proposal(tmp_path, enrich_with_llm=True)
    assert "LLM scope proposal: LLM summary" in proposal.overview
    assert "confirm deploy" in proposal.unresolved
    assert "README.md: documented" in proposal.evidence


def test_configured_primary_llm_is_not_invoked_without_explicit_enrichment(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "required-reading.md").write_text("- (none)\n", encoding="utf-8")
    state = tmp_path / ".gk"
    state.mkdir()
    (state / "project-config.json").write_text(
        json.dumps({"providers": [{"name": "test", "mode": "env", "credential_ref": "TEST_KEY", "base_url": "https://example.invalid/v1", "model": "test", "role": "primary"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "governancekit.agent_scope.propose_project_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("LLM must not run")),
    )

    proposal = build_adoption_proposal(tmp_path)

    assert "LLM scope proposal" not in proposal.overview


def test_provider_failure_names_configured_provider_and_model(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "required-reading.md").write_text("- (none)\n", encoding="utf-8")
    state = tmp_path / ".gk"
    state.mkdir()
    (state / "project-config.json").write_text(
        json.dumps({"providers": [{"name": "openai", "mode": "env", "credential_ref": "TEST_KEY", "base_url": "https://example.invalid/v1", "model": "gpt-test", "role": "primary"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "governancekit.agent_scope.propose_project_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("selected agent returned invalid JSON for the scope proposal")),
    )

    proposal = build_adoption_proposal(tmp_path, enrich_with_llm=True)

    assert proposal.llm_warning is not None
    assert proposal.llm_warning.provider == "openai / gpt-test"
    output = format_adoption_proposal(proposal)
    assert "[WARNING] LLM enrichment was skipped" in output
    assert "Provider/model: openai / gpt-test" in output
    assert "Enter n at the next prompt to leave overview and limits unchanged" in output


def test_invalid_llm_evidence_explains_the_expected_operator_action(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "required-reading.md").write_text("- (none)\n", encoding="utf-8")
    state = tmp_path / ".gk"
    state.mkdir()
    (state / "project-config.json").write_text(
        json.dumps({"providers": [{"name": "openai", "mode": "env", "credential_ref": "TEST_KEY", "base_url": "https://example.invalid/v1", "model": "gpt-test", "role": "primary"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "governancekit.agent_scope.propose_project_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("selected agent returned invalid evidence")),
    )

    output = format_adoption_proposal(build_adoption_proposal(tmp_path, enrich_with_llm=True))

    assert "evidence is not a valid non-empty list of unique text entries" in output
    assert "Expected: each domain must cite selected sources as 'path: reason'" in output
