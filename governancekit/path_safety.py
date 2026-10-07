"""Fail-closed path checks for ``--root`` itself and for paths below it."""
from __future__ import annotations

import os
from pathlib import Path


class UnsafePathError(RuntimeError):
    """A requested path escapes the governed project or traverses a symlink."""


class UnsafeRootError(RuntimeError):
    """``--root`` points at a location that must never be governed as a project."""


def _home() -> Path:
    """The operator's home directory, honouring ``$HOME`` when it is set."""
    env_home = os.environ.get("HOME")
    return Path(env_home).resolve() if env_home else Path.home().resolve()


def assert_governable_root(root: Path) -> Path:
    """Return *root* only when it can plausibly be a project directory.

    Agent tooling resolves ``AGENTS.md``/``CLAUDE.md`` and ``docs/limits.md`` by
    walking up from the working directory. A kit installed in ``$HOME`` — or in any
    ancestor of it — is therefore inherited by every directory below: a project with
    no governance of its own stops failing closed and silently resolves to that copy
    instead, with whatever readiness flags it happens to carry. The same applies to
    the filesystem root. Neither is a project, so refuse before anything is written.
    """
    resolved = root.resolve()
    home = _home()

    if not resolved.exists():
        raise UnsafeRootError(
            f"project root does not exist: {resolved}"
        )
    if not resolved.is_dir():
        raise UnsafeRootError(
            f"project root must be a directory, not a file: {resolved}"
        )

    if resolved == Path(resolved.anchor):
        raise UnsafeRootError(
            f"refusing to operate on the filesystem root: {resolved}"
        )
    if resolved == home:
        raise UnsafeRootError(
            f"refusing to operate on $HOME: {resolved}\n"
            "A kit installed here is inherited by every directory below it, so an "
            "unconfigured project resolves to it instead of stopping. Run the command "
            "from the project directory, or pass --root <project>."
        )
    if resolved in home.parents:
        raise UnsafeRootError(
            f"refusing to operate on {resolved}: it contains $HOME ({home}), so every "
            "project below would inherit the kit installed here."
        )
    return root


def safe_path(root: Path, path: Path) -> Path:
    """Return *path* only when it is contained by *root* without symlinks.

    The lexical component walk rejects a symlink even when it currently resolves
    inside the project. This prevents later replacement of that link from turning a
    normal write into a write outside ``--root``.
    """
    root = root.resolve()
    candidate = path if path.is_absolute() else root / path
    try:
        relative = candidate.absolute().relative_to(root.absolute())
    except ValueError as exc:
        raise UnsafePathError(f"path is outside --root: {candidate}") from exc

    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise UnsafePathError(f"refusing symlink below --root: {current}")

    if not candidate.resolve().is_relative_to(root):
        raise UnsafePathError(f"path resolves outside --root: {candidate}")
    return candidate


def safe_regular_file(root: Path, path: Path) -> bool:
    """Whether *path* is a non-symlink regular file safely below *root*."""
    try:
        safe_path(root, path)
    except UnsafePathError:
        return False
    return path.is_file() and not path.is_symlink()
