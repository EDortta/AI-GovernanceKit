from __future__ import annotations

import subprocess
from pathlib import Path

from governancekit.hooks import install_hook


def test_install_pre_commit_hook(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    result = install_hook(tmp_path)

    hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
    assert result.hook_type == "pre-commit"
    assert hook_path.is_file()
    assert "governancekit pre-commit blocked" in hook_path.read_text(encoding="utf-8")


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
