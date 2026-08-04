from __future__ import annotations

import io
from contextlib import redirect_stderr
from pathlib import Path

import pytest

from governancekit import cli, install_agents
from governancekit.path_safety import UnsafeRootError, assert_governable_root


def test_home_is_refused(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home" / "operator"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    with pytest.raises(UnsafeRootError) as exc:
        assert_governable_root(home)

    assert "refusing to operate on $HOME" in str(exc.value)


def test_ancestor_of_home_is_refused(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home" / "operator"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    with pytest.raises(UnsafeRootError) as exc:
        assert_governable_root(home.parent)

    assert "it contains $HOME" in str(exc.value)


def test_filesystem_root_is_refused(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    with pytest.raises(UnsafeRootError):
        assert_governable_root(Path("/"))


def test_project_below_home_is_allowed(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home" / "operator"
    project = home / "Projects" / "app"
    project.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    assert assert_governable_root(project) == project


def test_cli_refuses_install_agents_in_home(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home" / "operator"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        install_agents,
        "run_install_agents",
        lambda *_args, **_kwargs: pytest.fail("install must not run with --root $HOME"),
    )
    stderr = io.StringIO()

    with redirect_stderr(stderr):
        code = cli.main(["--root", str(home), "install-agents"])

    assert code == 2
    assert "Unsafe --root" in stderr.getvalue()
