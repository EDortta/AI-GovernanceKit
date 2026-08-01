from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest

from governancekit import cli, install_agents
from governancekit.doctor import CheckResult, DoctorResult
from governancekit.install_agents import InstallResult


def test_main_without_command_prints_expanded_help() -> None:
    stdout = io.StringIO()

    with redirect_stdout(stdout):
        code = cli.main([])

    output = stdout.getvalue()
    assert code == 2
    assert "usage: governancekit [-h] [--root ROOT] [--credential-root CREDENTIAL_ROOT]" in output
    assert "positional arguments:" in output
    assert "doctor              Validate required governance files and readiness" in output
    assert "context             Inspect or build a deterministic task context." in output
    assert "voice-integration   Detect optional AI-ListenToMeOnCLI availability." in output
    assert "Common command options:" in output
    assert "Target a project explicitly" in output
    assert "governancekit --root /absolute/path --credential-root /trusted/credentials COMMAND [OPTIONS]" in output
    assert "--upgrade, --docs-only, --force" in output
    assert "--set KEY=VALUE, --operator-name NAME" in output
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
    monkeypatch.setattr(install_agents, "_download", lambda *_args: tmp_path)
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


def test_docs_only_does_not_modify_root_gitignore(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(install_agents, "_download", lambda *_args: tmp_path)
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
