import json

from governancekit.adoption import (
    apply_adoption_proposal,
    build_adoption_proposal,
    detect_project_drift,
    format_adoption_proposal,
)
from governancekit.agent_scope import ProposedDomain, ScopeProposal
from governancekit.context_authoring import flag_is_yes


def test_generated_adoption_never_declares_itself_ready(tmp_path) -> None:
    """A machine may write the document. It may never write the flag.

    This assertion is the inverse of the one it replaces. The old contract had the
    generator emit `- project_context_ready: yes` in the same file where it listed
    the things it could not determine, which opened the Start Gate over content no
    human had read. Only `context_authoring.confirm_document` flips a flag.
    """
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")

    applied = apply_adoption_proposal(build_adoption_proposal(tmp_path))

    assert applied.written == ["docs/software-overview.md", "docs/limits.md"]
    for rel, marker in (
        ("docs/software-overview.md", "project_context_ready"),
        ("docs/limits.md", "limits_ready"),
    ):
        text = (tmp_path / rel).read_text()
        assert f"- {marker}: no" in text
        assert not flag_is_yes(text, marker)
    assert applied.unconfirmed == ["docs/software-overview.md", "docs/limits.md"]


def test_the_shipped_template_prose_does_not_pass_as_a_ready_flag(tmp_path) -> None:
    """The incident, as a test, with the artifact the kit actually publishes.

    The installer seeds these two files from the kit's own `docs/`, and that text
    explains the flag in a sentence. The old gate tested `"project_context_ready:
    yes" in old` over the whole file, so the SENTENCE matched, adoption skipped the
    write, and the flow reported "existing project documents preserved" over the
    kit's own boilerplate. Fixture is the real prose, not a synthetic string.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    seeded = (
        "# Software Overview\n\n## Metadata\n\n- project_context_ready: no\n\n"
        "This repository provides a universal, reusable agent-governance bundle.\n\n"
        "## Install-Time Role\n\nWhen copied into a target project, the programmer must "
        "replace this content with that project's actual context and set "
        "`project_context_ready: yes` only after the file is accurate.\n"
    )
    (docs / "software-overview.md").write_text(seeded, encoding="utf-8")

    applied = apply_adoption_proposal(build_adoption_proposal(tmp_path))

    assert "docs/software-overview.md" in applied.written
    assert "the programmer must replace" not in (docs / "software-overview.md").read_text()


def test_a_confirmed_document_is_never_retracted(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "software-overview.md").write_text("- project_context_ready: yes\ncustom\n")
    (docs / "limits.md").write_text("- limits_ready: yes\ncustom\n")

    applied = apply_adoption_proposal(build_adoption_proposal(tmp_path))

    assert applied.written == []
    assert [why for _, why in applied.preserved] == [
        "you already confirmed it ready", "you already confirmed it ready"
    ]
    assert "custom" in (docs / "software-overview.md").read_text()
    assert applied.unconfirmed == []


def test_a_short_hand_written_document_is_not_clobbered(tmp_path) -> None:
    """Too short to classify as authored, and none of it is the kit's.

    `classify_document` calls a three-line document TEMPLATE, because length is all
    it has. Writing over it would destroy exactly what the Start Gate exists to
    collect, so the deterministic path replaces only text the kit itself put there.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "software-overview.md").write_text(
        "# Overview\n\n- project_context_ready: no\n\nWe bill churches monthly.\n",
        encoding="utf-8",
    )

    applied = apply_adoption_proposal(build_adoption_proposal(tmp_path))

    assert "docs/software-overview.md" not in applied.written
    assert "We bill churches monthly." in (docs / "software-overview.md").read_text()
    # The discriminating case for where `unconfirmed` comes from: this document was
    # NOT written, and its flag on disk is still `no`, so it must be listed. Deriving
    # the verdict from the write list — the belief — silently drops it, and the suite
    # could not tell the two apart until this line existed.
    assert applied.unconfirmed == ["docs/software-overview.md", "docs/limits.md"]


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
