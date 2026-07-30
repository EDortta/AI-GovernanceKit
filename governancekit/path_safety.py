"""Fail-closed path checks for commands operating below ``--root``."""
from __future__ import annotations

from pathlib import Path


class UnsafePathError(RuntimeError):
    """A requested path escapes the governed project or traverses a symlink."""


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
