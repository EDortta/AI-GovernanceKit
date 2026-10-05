from __future__ import annotations

import argparse
import io
from contextlib import redirect_stderr, redirect_stdout

import pytest

from governancekit import __version__
from governancekit import cli, install_agents
from governancekit.doctor import CheckResult, DoctorResult
from governancekit.install_agents import InstallResult


class _InteractiveStdin:
    def isatty(self) -> bool:
        return True


def test_main_without_command_prints_expanded_help() -> None:
    stdout = io.StringIO()

    with redirect_stdout(stdout):
        code = cli.main([])

    output = stdout.getvalue()
    assert code == 2
    assert "usage: governancekit [-h] [--root ROOT] [--development] [--version]" in output
    assert "positional arguments:" in output
    assert "doctor              Validate required governance files and readiness" in output
    assert "install-agents      Install AI-Agents kit" in output
    assert "Start here:" in output
    assert "Advanced commands:" in output
    assert "config-session         Run the resumable granular configuration workflow." in output
    assert "governancekit --root /project install-agents" in output
    assert "--root before the command" in output
    assert "a command is required" in output


def test_format_doctor_indents_multiline_messages(tmp_path) -> None:
    result = DoctorResult(
        root=tmp_path,
        checks=(
            CheckResult(
                "security advisories",
                False,
                "review 2 advisory hit(s)\ncategories:\n  - shell injection risk: 1",
                advisory=True,
            ),
        ),
    )

    output = cli.format_doctor(result)

    assert "[HINT] security advisories:" in output
    assert "  review 2 advisory hit(s)" in output
    assert "  categories:" in output
    assert "    - shell injection risk: 1" in output


def test_install_agents_prints_identity_setup_for_unconfigured_host(monkeypatch, tmp_path) -> None:
    result = InstallResult(target=tmp_path, upgraded=False)
    monkeypatch.setattr(
        "governancekit.install_agents.run_install_agents", lambda *_args, **_kwargs: result
    )
    stdout = io.StringIO()

    with redirect_stdout(stdout):
        code = cli.main(["--root", str(tmp_path), "install-agents", "--skip-project-configuration"])

    output = stdout.getvalue()
    assert code == 0
    assert output.startswith(f"AI GovernanceKit {__version__} · install-agents\n")
    assert "Next required local setup (per host/checkout):" in output
    assert f"governancekit --root {tmp_path} configure" in output


def test_install_agents_prints_identity_setup_for_incomplete_identity(monkeypatch, tmp_path) -> None:
    result = InstallResult(target=tmp_path, upgraded=False)
    monkeypatch.setattr(
        "governancekit.install_agents.run_install_agents", lambda *_args, **_kwargs: result
    )
    (tmp_path / ".governancekit-identity.json").write_text(
        '{"operator_name": "Ann"}\n', encoding="utf-8"
    )
    stdout = io.StringIO()

    with redirect_stdout(stdout):
        code = cli.main(["--root", str(tmp_path), "install-agents", "--skip-project-configuration"])

    assert code == 0
    assert "Next required local setup (per host/checkout):" in stdout.getvalue()


def test_upgrade_announces_project_analysis_duration(monkeypatch, tmp_path) -> None:
    result = InstallResult(target=tmp_path, upgraded=True)
    monkeypatch.setattr(
        "governancekit.install_agents.run_install_agents", lambda *_args, **_kwargs: result
    )
    monkeypatch.setattr("governancekit.adoption.detect_project_drift", lambda *_args, **_kwargs: [])
    stdout = io.StringIO()

    with redirect_stdout(stdout):
        code = cli.main(["--root", str(tmp_path), "install-agents", "--upgrade", "--skip-project-configuration"])

    assert code == 0
    assert "Analyzing project files for upgrade drift; this can take several minutes in a large project..." in stdout.getvalue()


def test_install_agents_does_not_report_optional_awt_as_manual_step(
    monkeypatch, tmp_path
) -> None:
    result = InstallResult(
        target=tmp_path,
        upgraded=False,
        awt_message="could not run 'awt install': permission denied",
    )
    monkeypatch.setattr(
        "governancekit.install_agents.run_install_agents", lambda *_args, **_kwargs: result
    )
    stdout = io.StringIO()

    with redirect_stdout(stdout):
        code = cli.main(["--root", str(tmp_path), "install-agents"])

    output = stdout.getvalue()
    assert code == 0
    assert "awt: could not run 'awt install': permission denied" in output
    assert "manual step needed" not in output


def test_install_agents_silently_skips_optional_awt(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(install_agents, "_download", lambda *_args, **_kwargs: tmp_path)
    monkeypatch.setattr(
        install_agents, "_do_fresh", lambda *_args, **_kwargs: ["scripts/agent-worktree.sh"]
    )
    monkeypatch.setattr(install_agents, "_ensure_project_docs", lambda *_args: None)
    monkeypatch.setattr(install_agents, "_resolve_track_kit_docs", lambda *_args: True)
    monkeypatch.setattr(install_agents, "_update_gitignore", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(install_agents, "_fill_placeholders", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(install_agents, "_write_state", lambda *_args, **_kwargs: None)

    result = install_agents.run_install_agents(tmp_path, track=True)

    assert not result.awt_installed
    assert result.awt_message is None


def test_install_agents_asks_before_using_configured_llm(monkeypatch, tmp_path) -> None:
    result = InstallResult(target=tmp_path, upgraded=True)
    monkeypatch.setattr(
        "governancekit.install_agents.run_install_agents", lambda *_args, **_kwargs: result
    )
    state = tmp_path / ".gk"
    state.mkdir()
    (state / "project-config.json").write_text(
        '{"providers": [{"name": "openai", "mode": "env", "credential_ref": "TEST_KEY", "base_url": "https://example.invalid/v1", "model": "gpt-test", "role": "primary"}]}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(cli.sys, "stdin", _InteractiveStdin())
    answers = iter(["n", "n"])
    prompts: list[str] = []
    monkeypatch.setattr("builtins.input", lambda prompt: (prompts.append(prompt), next(answers))[1])
    monkeypatch.setattr(
        "governancekit.agent_scope.propose_project_scope",
        lambda *_args, **_kwargs: pytest.fail("LLM must not run without confirmation"),
    )
    stdout = io.StringIO()

    with redirect_stdout(stdout):
        code = cli.main(["--root", str(tmp_path), "install-agents"])

    assert code == 0
    assert any(
        prompt.startswith("Use configured LLM provider openai / gpt-test to enrich this proposal? [y/N]")
        for prompt in prompts
    )


def test_docs_only_does_not_modify_root_gitignore(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(install_agents, "_download", lambda *_args, **_kwargs: tmp_path)
    monkeypatch.setattr(install_agents, "_do_upgrade", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(install_agents, "_ensure_project_docs", lambda *_args: None)
    monkeypatch.setattr(install_agents, "_fill_placeholders", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(install_agents, "_write_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        install_agents,
        "_update_gitignore",
        lambda *_args, **_kwargs: pytest.fail("--docs-only must not rewrite .gitignore"),
    )

    result = install_agents.run_install_agents(tmp_path, docs_only=True)

    assert not result.gitignore_updated


def test_every_subcommand_has_a_handler() -> None:
    # The dispatch used to be a 583-line if/elif chain inside main(), where a new
    # command could quietly land after a cross-cutting check. A table makes the
    # omission visible: a parser entry with no handler fails here, not in production.
    parser = cli.build_parser()
    subparsers = [
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    ]
    commands = set(subparsers[0].choices)

    assert commands == set(cli._COMMANDS), commands ^ set(cli._COMMANDS)


def test_root_guard_runs_before_the_handler(monkeypatch, tmp_path) -> None:
    # The guard lives in main(), before the dispatch, so it cannot be skipped by a
    # command that forgets it. Checked on the commands that take no required
    # sub-arguments; argparse rejects the others before main() is reached at all.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for command in ("doctor", "discover", "resume", "author-context"):
        monkeypatch.setitem(
            cli._COMMANDS, command, lambda _args: pytest.fail(f"{command} ran with --root $HOME")
        )
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            assert cli.main(["--root", str(home), command]) == 2
        assert "Unsafe --root" in stderr.getvalue()


def test_development_is_a_global_explicit_flag() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["--development", "discover"])
    assert args.development is True


def test_legacy_adoption_plan_is_marked_as_legacy(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(
        "governancekit.adoption_selection.build_adoption_selection_plan",
        lambda *_args, **_kwargs: type("Plan", (), {"as_dict": lambda self: {}})(),
    )
    monkeypatch.setattr(
        "governancekit.adoption_selection.format_adoption_selection_plan",
        lambda _plan: "legacy-plan",
    )

    code = cli.main(["--root", str(tmp_path), "adoption", "plan"])
    output = capsys.readouterr().out

    assert code == 0
    assert "legacy one-shot flow" in output
    assert "adoption discover -> adoption sources -> adoption analyze -> adoption apply" in output


def test_adoption_describe_checks_llm_before_prompting(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(cli.sys, "stdin", _InteractiveStdin())
    prompted: list[str] = []
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: (prompted.append(prompt), "unexpected")[1],
    )
    monkeypatch.setattr(
        "governancekit.adoption.configured_adoption_provider",
        lambda _root: None,
    )

    code = cli.main(["--root", str(tmp_path), "adoption", "describe"])
    output = capsys.readouterr().out

    assert code == 2
    assert prompted == []
    assert "no configured primary LLM provider" in output
    assert "llm test" in output


def test_adoption_describe_checks_llm_health_before_prompting(monkeypatch, tmp_path, capsys) -> None:
    from governancekit.llm_test import LlmTestResult
    from governancekit.project_config import ProviderConfig

    provider = ProviderConfig(
        name="openai",
        purpose="governance-adoption",
        base_url="https://example.invalid/v1",
        model="gpt-test",
        mode="env",
        credential_ref="TEST_KEY",
        validation="reference-required",
        role="primary",
    )
    monkeypatch.setattr(cli.sys, "stdin", _InteractiveStdin())
    prompted: list[str] = []
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: (prompted.append(prompt), "unexpected")[1],
    )
    monkeypatch.setattr(
        "governancekit.adoption.configured_adoption_provider",
        lambda _root: provider,
    )
    monkeypatch.setattr(
        "governancekit.llm_test.check_configured_providers",
        lambda _root: [LlmTestResult("openai", "gpt-test", False, "credential unavailable")],
    )

    code = cli.main(["--root", str(tmp_path), "adoption", "describe"])
    output = capsys.readouterr().out

    assert code == 2
    assert prompted == []
    assert "primary LLM provider openai / gpt-test is not ready" in output
    assert "credential unavailable" in output


def test_adoption_describe_show_does_not_probe_llm(monkeypatch, tmp_path, capsys) -> None:
    proposal = tmp_path / ".gk/adoption/description-proposal.md"
    proposal.parent.mkdir(parents=True)
    proposal.write_text("# Demo\n", encoding="utf-8")
    monkeypatch.setattr(
        "governancekit.llm_test.check_configured_providers",
        lambda _root: pytest.fail("--show must not probe the LLM"),
    )

    code = cli.main(["--root", str(tmp_path), "adoption", "describe", "--show"])
    output = capsys.readouterr().out

    assert code == 0
    assert "# Demo" in output


def test_llm_configure_preflight_shows_saved_and_detected_state(monkeypatch, tmp_path, capsys) -> None:
    from governancekit.project_config import ProviderConfig, ProjectConfig

    saved_provider = ProviderConfig(
        name="openai",
        purpose="general",
        base_url="https://api.openai.com/v1",
        model="gpt-5-mini",
        mode="file-ref",
        credential_ref=".credentials/llm/openai.key",
        validation="reference-required",
        role="primary",
    )
    config = ProjectConfig(
        project_name="demo",
        domains=[],
        capabilities=[],
        agents=[],
        providers=[saved_provider],
    )
    detected_provider = ProviderConfig(
        name="openai",
        purpose="general",
        base_url="https://api.openai.com/v1",
        model="gpt-5-mini",
        mode="file-ref",
        credential_ref=".credentials/llm/openai.key",
        validation="reference-required",
        role="primary",
    )

    monkeypatch.setattr("governancekit.cli.load_project_config", lambda _root: config, raising=False)
    monkeypatch.setattr(
        "governancekit.scope_conversation._detected_providers",
        lambda _root: [detected_provider],
    )
    monkeypatch.setattr(
        "governancekit.scope_conversation._collect_providers",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    code = cli.main(["--root", str(tmp_path), "llm", "configure"])
    output = capsys.readouterr().out

    assert code == 2
    assert "AI GovernanceKit LLM configuration preflight" in output
    assert "saved configuration:" in output
    assert "primary: openai / gpt-5-mini" in output
    assert "detected local credentials:" in output
    assert ".credentials/llm/openai.key" in output
