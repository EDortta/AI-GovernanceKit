from __future__ import annotations

import io
from contextlib import redirect_stdout

from governancekit import cli


def test_main_without_command_prints_expanded_help() -> None:
    stdout = io.StringIO()

    with redirect_stdout(stdout):
        code = cli.main([])

    output = stdout.getvalue()
    assert code == 2
    assert "usage: governancekit [-h] [--root ROOT] [--version]" in output
    assert "positional arguments:" in output
    assert "doctor              Validate required governance files and readiness" in output
    assert "context             Inspect or build a deterministic task context." in output
    assert "voice-integration   Detect optional AI-ListenToMeOnCLI availability." in output
    assert "Common command options:" in output
    assert "--upgrade, --docs-only, --force" in output
    assert "--set KEY=VALUE, --operator-name NAME" in output
    assert "a command is required" in output
