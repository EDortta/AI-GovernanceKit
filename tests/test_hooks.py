from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from governancekit.hooks import install_hook

_PACKAGE_PARENT = str(Path(__file__).resolve().parents[1])


def test_install_pre_commit_hook(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    result = install_hook(tmp_path)

    hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
    assert result.hook_type == "pre-commit"
    assert hook_path.is_file()
    assert "governancekit pre-commit blocked" in hook_path.read_text(encoding="utf-8")


def _run_installed_hook(root: Path) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        f"{_PACKAGE_PARENT}{os.pathsep}{existing}" if existing else _PACKAGE_PARENT
    )
    return subprocess.run(
        ["bash", str(root / ".git" / "hooks" / "pre-commit")],
        cwd=root, capture_output=True, text=True, env=environment,
    )


def test_the_hook_actually_reaches_the_doctor_verdict(tmp_path: Path) -> None:
    """Regression, twice over — the two ways this hook silently passed everything.

    1. It invoked ``python3 -m governancekit.cli``, which had no ``__main__``
       guard: the module imported, printed nothing, and exited 0.
    2. It piped that output into ``python3 - <<'PY'``, where the heredoc *replaces*
       the pipe as stdin, so the reader never saw a report either way.

    Both were invisible to a test that only asserted on the script's text, which is
    what the other tests here do. This one runs it.
    """
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for setting in (("user.email", "hook@test"), ("user.name", "hook")):
        subprocess.run(["git", "config", *setting], cwd=tmp_path, check=True)
    install_hook(tmp_path)
    # A repository with no AGENTS.md fails a mandatory doctor check, so a hook that
    # reaches the verdict must refuse; one that does not will exit 0.
    (tmp_path / "app.py").write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=tmp_path, check=True)

    completed = _run_installed_hook(tmp_path)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "mandatory doctor check failed" in completed.stderr
    assert "AGENTS.md" in completed.stderr


def test_the_hook_does_not_block_when_the_toolchain_is_missing(tmp_path: Path) -> None:
    # An unreadable or absent report is a broken toolchain, not a broken commit.
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    install_hook(tmp_path)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(tmp_path / "nowhere")
    environment["PATH"] = os.path.dirname(sys.executable) + os.pathsep + "/usr/bin:/bin"

    completed = subprocess.run(
        ["bash", str(tmp_path / ".git" / "hooks" / "pre-commit")],
        cwd=tmp_path, capture_output=True, text=True, env=environment,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_existing_hook_requires_force(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
    hook_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    try:
        install_hook(tmp_path)
    except RuntimeError as exc:
        assert "--force" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
