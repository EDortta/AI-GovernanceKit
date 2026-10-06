from __future__ import annotations

import json
from pathlib import Path

from governancekit import cli
from governancekit.wizard import _llm_menu, inspect_wizard_state, render_home


class _InteractiveStdin:
    def isatty(self) -> bool:
        return True


def test_bare_cli_opens_wizard_in_interactive_terminal(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli.sys, "stdin", _InteractiveStdin())
    called: dict[str, object] = {}

    def fake_wizard(root, *, development, execute):
        called["root"] = root
        called["development"] = development
        called["execute"] = execute
        return 0

    monkeypatch.setattr("governancekit.wizard.run_wizard", fake_wizard)

    code = cli.main(["--root", str(tmp_path)])

    assert code == 0
    assert called["root"] == tmp_path.resolve()
    assert called["development"] is False
    assert callable(called["execute"])


def test_wizard_state_recommends_llm_first_when_unconfigured(tmp_path: Path) -> None:
    state = inspect_wizard_state(tmp_path)

    assert state.provider is None
    assert state.next_step == "Configure the project LLM"
    output = render_home(state)
    assert "AI GOVERNANCEKIT" in output
    assert "Recommended next step: Configure the project LLM" in output


def test_wizard_state_recommends_sources_after_llm_is_ready(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    config = tmp_path / ".gk/project-config.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({
        "config_version": 6,
        "governancekit_version": "2.3.0",
        "governancekit_mode": "development",
        "ai_agents_installed_ref": None,
        "ai_agents_installed_repo": None,
        "ai_agents_target_ref": None,
        "ai_agents_target_repo": None,
        "project_name": "demo",
        "project_state": "existing",
        "languages": [],
        "frameworks": [],
        "package_managers": [],
        "automation_commands": [],
        "domains": [],
        "capabilities": [],
        "capability_domains": {},
        "agents": [],
        "selected_agent": None,
        "providers": [{
            "name": "openai",
            "purpose": "general",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-5-mini",
            "mode": "env",
            "credential_ref": "OPENAI_API_KEY",
            "validation": "reference-required",
            "role": "primary"
        }],
        "governance_files": [],
        "integration_status": "pending",
        "required_reading": [],
        "scope_summary": None,
        "notes": []
    }), encoding="utf-8")

    state = inspect_wizard_state(tmp_path, provider_ready=True)

    assert state.provider == "openai / gpt-5-mini"
    assert state.documentation_candidates == 1
    assert state.next_step == "Discover and select project documentation"


def test_wizard_state_recommends_source_based_description_after_selection(tmp_path: Path) -> None:
    config = tmp_path / ".gk/project-config.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({
        "config_version": 6,
        "governancekit_version": "2.3.0",
        "governancekit_mode": "development",
        "ai_agents_installed_ref": None,
        "ai_agents_installed_repo": None,
        "ai_agents_target_ref": None,
        "ai_agents_target_repo": None,
        "project_name": "demo",
        "project_state": "existing",
        "languages": [],
        "frameworks": [],
        "package_managers": [],
        "automation_commands": [],
        "domains": [],
        "capabilities": [],
        "capability_domains": {},
        "agents": [],
        "selected_agent": None,
        "providers": [{
            "name": "openai",
            "purpose": "general",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-5-mini",
            "mode": "env",
            "credential_ref": "OPENAI_API_KEY",
            "validation": "reference-required",
            "role": "primary"
        }],
        "governance_files": [],
        "integration_status": "pending",
        "required_reading": [],
        "scope_summary": None,
        "notes": []
    }), encoding="utf-8")
    sources = tmp_path / ".gk/adoption/sources.json"
    sources.parent.mkdir(parents=True, exist_ok=True)
    sources.write_text(json.dumps({"sources": ["README.md"]}), encoding="utf-8")

    state = inspect_wizard_state(tmp_path, provider_ready=True)

    assert state.selected_sources == 1
    assert state.next_step == "Let the LLM propose a description from selected sources"


def test_llm_menu_maps_zero_exit_code_to_ready(monkeypatch, tmp_path: Path) -> None:
    answers = iter(["3", "b"])

    monkeypatch.setattr(
        "governancekit.wizard._run",
        lambda *_args, **_kwargs: 0,
    )

    result = _llm_menu(
        tmp_path,
        False,
        execute=lambda _args: 0,
        development=False,
        input_fn=lambda _prompt: next(answers),
    )

    assert result is True


def test_llm_menu_maps_nonzero_exit_code_to_not_ready(monkeypatch, tmp_path: Path) -> None:
    answers = iter(["3", "b"])

    monkeypatch.setattr(
        "governancekit.wizard._run",
        lambda *_args, **_kwargs: 1,
    )

    result = _llm_menu(
        tmp_path,
        False,
        execute=lambda _args: 1,
        development=False,
        input_fn=lambda _prompt: next(answers),
    )

    assert result is False


def test_submenu_command_is_framed_and_menu_reappears(monkeypatch, tmp_path: Path, capsys) -> None:
    from governancekit.wizard import _documentation_menu

    answers = iter(["1", "b"])
    monkeypatch.setattr(
        "governancekit.wizard._run",
        lambda *_args, **_kwargs: 0,
    )

    _documentation_menu(
        tmp_path,
        False,
        execute=lambda _args: 0,
        development=False,
        input_fn=lambda _prompt: next(answers),
    )

    output = capsys.readouterr().out
    assert "[BEGIN]" in output
    assert "[FINISH]" in output
    assert output.count("Project documentation") == 2


def test_internal_help_systemexit_does_not_leave_wizard(tmp_path: Path) -> None:
    from governancekit.wizard import _run

    def fake_execute(_args):
        raise SystemExit(0)

    assert _run(fake_execute, tmp_path, False, ["--help"]) == 0
