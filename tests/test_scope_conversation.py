from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from governancekit.agent_scope import ProposedDomain, ScopeProposal
from governancekit.project_config import ProviderConfig, apply_project_config_plan, build_project_config_plan
from governancekit.scope_conversation import DomainCandidate, _LLM_PRESETS, _collect_providers, _detected_providers, _domain_answer, _is_legacy_pending_scope_baseline, _merge_domain_candidates, _print_analysis_notice, _print_domain_selection_help, _print_provider_catalog, _print_provider_help, _saved_providers, _write_credential_file, load_required_reading, resolve_locale, run_scope_conversation


def _proposal() -> ScopeProposal:
    return ScopeProposal(
        summary="Companion for remote work.",
        domains=[ProposedDomain("sessions", ["manage-sessions"], ["docs/product-model.md: session workflow"])],
        questions=["Which actions require approval?"],
    )


def _seed_sources(root: Path) -> None:
    (root / ".docs").mkdir()
    (root / "docs").mkdir()
    for rel in ("AGENTS.md", ".docs/software-overview.md", ".docs/limits.md", "docs/project-rules.md"):
        (root / rel).write_text("content\n", encoding="utf-8")
    (root / "docs/product-model.md").write_text("product\n", encoding="utf-8")
    (root / "docs/project-rules.md").write_text("Read `docs/product-model.md`.\n", encoding="utf-8")
    (root / "docs/required-reading.md").write_text("- `docs/project-rules.md`\n", encoding="utf-8")


def test_locale_prefers_operational_ptbr() -> None:
    assert resolve_locale({"LANG": "pt_BR.UTF-8"}) == "pt-BR"
    assert resolve_locale({"LANG": "es_ES.UTF-8"}) == "es"
    assert resolve_locale({"LANG": "C.UTF-8"}) == "en"


def test_neutral_shell_uses_project_language_before_inherited_language(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "product-foundation.md").write_text(
        "O projeto precisa de uma decisao para aprovacoes e uma experiencia clara.\n",
        encoding="utf-8",
    )

    assert resolve_locale({"LANG": "C.UTF-8", "LANGUAGE": "en_US"}, root=tmp_path) == "pt-BR"


def test_nvidia_preset_uses_its_openai_compatible_endpoint() -> None:
    assert _LLM_PRESETS["nvidia"] == (
        "https://integrate.api.nvidia.com/v1",
        "nvidia/nemotron-3-super-120b-a12b",
        "NVIDIA_API_KEY",
    )


def test_provider_catalog_lists_nvidia_nim_as_openai_compatible(capsys) -> None:
    _print_provider_catalog("en")

    output = capsys.readouterr().out
    assert "OpenAI-compatible" in output
    assert "NVIDIA NIM" in output
    assert "NVIDIA_API_KEY" in output


def test_provider_help_limits_llm_use_to_the_scope_interview(capsys) -> None:
    _print_provider_help("en")

    output = capsys.readouterr().out
    assert "not for development tasks or project implementation" in output
    assert ".credentials/llm/<provider>.key" in output
    assert "Configuration stores only that file path" in output


def test_domain_selection_can_accept_the_complete_agent_proposal(capsys) -> None:
    candidates = [DomainCandidate("sessions", ["manage-sessions"], ["docs/product-model.md: session workflow"], ("LLM",))]

    _print_domain_selection_help("en", candidates)

    assert _domain_answer("proposal", candidates) == ["sessions"]
    output = capsys.readouterr().out
    assert "Single domain and capability list" in output
    assert "Press Enter to accept the single list" in output


def test_domain_candidates_merge_declared_and_llm_origins_without_merging_similar_names() -> None:
    declared = build_project_config_plan(
        Path("/tmp/example-project"), domains=["collaboration"], capabilities=["review"],
        capability_domains={"review": "collaboration"},
    ).config
    proposal = ScopeProposal(
        summary="Product.",
        domains=[
            ProposedDomain("collaboration", ["conversations"], ["docs/product.md: collaboration"]),
            ProposedDomain("review-conversation", ["review"], ["docs/product.md: review"]),
        ],
        questions=[],
    )

    candidates = _merge_domain_candidates(declared, proposal)

    assert [(candidate.name, candidate.origins) for candidate in candidates] == [
        ("collaboration", ("both",)),
        ("review-conversation", ("LLM",)),
    ]
    assert candidates[0].capabilities == ["review", "conversations"]


def test_legacy_pending_adoption_baseline_does_not_override_scope_proposal(tmp_path: Path) -> None:
    plan = build_project_config_plan(tmp_path, domains=["shell"])
    legacy = replace(plan.config, config_version=1)

    assert _is_legacy_pending_scope_baseline(tmp_path, legacy)
    (tmp_path / ".gk").mkdir()
    (tmp_path / ".gk/project-config.json").write_text("{}", encoding="utf-8")
    assert not _is_legacy_pending_scope_baseline(tmp_path, legacy)


def test_analysis_notice_explains_the_delay_and_read_only_boundary(capsys) -> None:
    _print_analysis_notice("en", "llm-api", ["docs/product.md"], ProviderConfig(name="nvidia", model="nemotron"))

    output = capsys.readouterr().out
    assert "Analyze project scope" in output
    assert "reading 1 approved source" in output
    assert "read-only" in output
    assert "up to 90 seconds" in output


def test_created_credential_file_is_private_and_not_part_of_provider_config(tmp_path: Path) -> None:
    reference = _write_credential_file(tmp_path, "OpenAI", "secret-value")
    credential = tmp_path / reference

    assert reference == ".credentials/llm/OpenAI.key"
    assert credential.read_text(encoding="utf-8") == "secret-value\n"
    assert credential.stat().st_mode & 0o777 == 0o600


def test_manual_placeholder_is_not_presented_as_a_saved_llm_provider() -> None:
    manual = ProviderConfig(name="manual", mode="manual")
    assert _saved_providers(None) == []
    assert _saved_providers(type("Config", (), {"providers": [manual]})()) == []


def test_provider_interview_can_create_a_hidden_local_credential_file(tmp_path: Path, monkeypatch, capsys) -> None:
    answers = iter(["", "openai", "", "", "criar", "", "", "n"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr("governancekit.scope_conversation.getpass.getpass", lambda _prompt: "pasted-secret")

    providers = _collect_providers(tmp_path, "pt-BR", None)

    assert providers[0].mode == "file-ref"
    assert providers[0].credential_ref == ".credentials/llm/openai.key"
    assert (tmp_path / providers[0].credential_ref).read_text(encoding="utf-8") == "pasted-secret\n"
    output = capsys.readouterr().out
    assert "entrada oculta" in output
    assert "pasted-secret" not in output


def test_detected_nvidia_credential_uses_the_nim_preset_without_reading_the_secret(tmp_path: Path, monkeypatch) -> None:
    for env_name in ("GEMINI_API_KEY", "NVIDIA_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(env_name, raising=False)
    credential = tmp_path / ".credentials/llm/nvidia.key"
    credential.parent.mkdir(parents=True)
    credential.write_text("do-not-read-this-secret\n", encoding="utf-8")

    providers = _detected_providers(tmp_path)

    assert len(providers) == 1
    provider = providers[0]
    assert provider.name == "nvidia"
    assert provider.mode == "file-ref"
    assert provider.credential_ref == ".credentials/llm/nvidia.key"
    assert provider.base_url == _LLM_PRESETS["nvidia"][0]
    assert provider.model == _LLM_PRESETS["nvidia"][1]


def test_provider_interview_offers_a_detected_nvidia_configuration(tmp_path: Path, monkeypatch, capsys) -> None:
    for env_name in ("GEMINI_API_KEY", "NVIDIA_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(env_name, raising=False)
    credential = tmp_path / ".credentials/llm/nvidia.key"
    credential.parent.mkdir(parents=True)
    credential.write_text("secret\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt: "")

    providers = _collect_providers(tmp_path, "en", None)

    assert providers[0].name == "nvidia"
    assert "Local LLM credentials found" in capsys.readouterr().out


def test_load_required_reading_rejects_traversal_and_symlink_escape(tmp_path: Path) -> None:
    _seed_sources(tmp_path)
    outside = tmp_path.parent / "outside.md"
    outside.write_text("secret\n", encoding="utf-8")
    (tmp_path / "docs/project-rules.md").write_text(
        "Read `docs/../../outside.md` and `docs/external.md`.\n", encoding="utf-8"
    )
    (tmp_path / "docs/external.md").symlink_to(outside)

    available, missing = load_required_reading(tmp_path)

    assert "docs/../../outside.md" not in available
    assert "docs/external.md" not in available
    assert any("outside project root" in item for item in missing)


def test_ptbr_interview_guides_provider_and_retries_invalid_role(tmp_path: Path, monkeypatch, capsys) -> None:
    _seed_sources(tmp_path)
    answers = iter([
        "Bridge Mobile", "",  # project, configure providers
        "openai", "general", "general", "primary", "env", "OPENAI_API_KEY", "", "", "n",  # provider
        "openai-agents", "", "",  # agent, domains, capabilities
        "Companion for remote work.",
    ])
    def fake_input(prompt: str) -> str:
        print(prompt, end="")
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr("governancekit.scope_conversation.supported_scope_agents", lambda _agents: ["openai-agents"])
    monkeypatch.setattr("governancekit.scope_conversation.propose_project_scope", lambda *_args, **_kwargs: _proposal())

    conversation = run_scope_conversation(tmp_path, locale="pt-BR")

    assert conversation.providers[0].purpose == "general"
    assert conversation.providers[0].role == "primary"
    output = capsys.readouterr().out
    assert "Papel inválido" in output
    assert "escolha padrão para análise" in output
    assert "── Provedores LLM" in output
    assert "\n\n" in output
    assert "── Projeto e agente" in output
    assert output.index("Nome do projeto") < output.index("Agentes de escopo disponíveis")


def test_scope_conversation_reuses_pending_configuration_as_defaults(tmp_path: Path, monkeypatch, capsys) -> None:
    _seed_sources(tmp_path)
    plan = build_project_config_plan(
        tmp_path, project_name="Existing", domains=["sessions"], capabilities=["manage-sessions"],
        agents=["openai-agents"], selected_agent="openai-agents",
        capability_domains={"manage-sessions": "sessions"},
        scope_summary="Existing scope.",
    )
    # A pending approval is enough to make the next upgrade preserve prior answers.
    session_path = tmp_path / ".gk/config-session.json"
    session_path.parent.mkdir()
    session_path.write_text('{"plan": ' + __import__("json").dumps(plan.as_dict()) + '}', encoding="utf-8")
    answers = iter(["", "", "", "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr("governancekit.scope_conversation.supported_scope_agents", lambda _agents: ["openai-agents"])
    monkeypatch.setattr("governancekit.scope_conversation.propose_project_scope", lambda *_args, **_kwargs: _proposal())

    conversation = run_scope_conversation(tmp_path, locale="pt-BR")

    assert conversation.project_name == "Existing"
    assert conversation.capability_domains == {"manage-sessions": "sessions"}
    assert conversation.scope_summary == "Existing scope."
    assert "configuração salva ou pendente" in capsys.readouterr().out
