from __future__ import annotations

from pathlib import Path

from governancekit.agent_scope import ProposedDomain, ScopeProposal
from governancekit.project_config import apply_project_config_plan, build_project_config_plan
from governancekit.scope_conversation import load_required_reading, resolve_locale, run_scope_conversation


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
        "Bridge Mobile", "openai-agents", "", "",  # project, agent, domains, capabilities
        "",  # configure providers
        "openai", "general", "general", "primary", "env", "OPENAI_API_KEY", "n",  # provider
        "Companion for remote work.",
    ])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr("governancekit.scope_conversation.supported_scope_agents", lambda _agents: ["openai-agents"])
    monkeypatch.setattr("governancekit.scope_conversation.propose_project_scope", lambda *_args, **_kwargs: _proposal())

    conversation = run_scope_conversation(tmp_path, locale="pt-BR")

    assert conversation.providers[0].purpose == "general"
    assert conversation.providers[0].role == "primary"
    output = capsys.readouterr().out
    assert "Papel inválido" in output
    assert "primary é o padrão" in output
    assert "── Provedores LLM" in output
    assert "\n\n" in output


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
    answers = iter(["", "", "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr("governancekit.scope_conversation.supported_scope_agents", lambda _agents: ["openai-agents"])
    monkeypatch.setattr("governancekit.scope_conversation.propose_project_scope", lambda *_args, **_kwargs: _proposal())

    conversation = run_scope_conversation(tmp_path, locale="pt-BR")

    assert conversation.project_name == "Existing"
    assert conversation.capability_domains == {"manage-sessions": "sessions"}
    assert conversation.scope_summary == "Existing scope."
    assert "configuração salva ou pendente" in capsys.readouterr().out
