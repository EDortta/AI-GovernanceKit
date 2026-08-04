from __future__ import annotations

from pathlib import Path

from governancekit.install_agents import (
    _READINESS_ASIDE_DIR,
    _migrate_readiness_files_to_docs,
)


def _dotdocs_target(root: Path, *, limits: str = "- limits_ready: yes\n") -> Path:
    (root / ".docs").mkdir(parents=True, exist_ok=True)
    (root / ".docs" / "limits.md").write_text(limits, encoding="utf-8")
    return root


def test_readiness_file_moves_back_to_docs(tmp_path) -> None:
    _dotdocs_target(tmp_path)

    moved, notes = _migrate_readiness_files_to_docs(tmp_path)

    assert moved
    assert (tmp_path / "docs" / "limits.md").read_text() == "- limits_ready: yes\n"
    assert not (tmp_path / ".docs" / "limits.md").exists()
    assert any("limits.md → docs/limits.md" in n for n in notes)


def test_readiness_symlink_workaround_is_dropped(tmp_path) -> None:
    # The symlink was the workaround projects used for this very misfiling: the real
    # file is already in docs/, so dropping the link completes the migration.
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "limits.md").write_text("- limits_ready: yes\n", encoding="utf-8")
    (tmp_path / ".docs").mkdir()
    (tmp_path / ".docs" / "limits.md").symlink_to("../docs/limits.md")

    moved, notes = _migrate_readiness_files_to_docs(tmp_path)

    assert moved
    assert not (tmp_path / ".docs" / "limits.md").is_symlink()
    assert (tmp_path / "docs" / "limits.md").read_text() == "- limits_ready: yes\n"
    assert any("symlink" in n for n in notes)


def test_readiness_conflict_keeps_docs_and_sets_the_other_aside(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "limits.md").write_text("PROJECT CONTENT\n", encoding="utf-8")
    _dotdocs_target(tmp_path, limits="SEED\n")

    moved, notes = _migrate_readiness_files_to_docs(tmp_path)

    assert moved
    # The project's file is never touched, and the other copy is preserved for review.
    assert (tmp_path / "docs" / "limits.md").read_text() == "PROJECT CONTENT\n"
    assert (tmp_path / _READINESS_ASIDE_DIR / "limits.md").read_text() == "SEED\n"
    assert any("CONFLICT" in n for n in notes)


def test_identical_duplicate_is_removed_not_set_aside(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "limits.md").write_text("SAME\n", encoding="utf-8")
    _dotdocs_target(tmp_path, limits="SAME\n")

    moved, notes = _migrate_readiness_files_to_docs(tmp_path)

    assert moved
    assert not (tmp_path / ".docs" / "limits.md").exists()
    assert not (tmp_path / _READINESS_ASIDE_DIR).exists()
    assert any("duplicate removed" in n for n in notes)


def test_readiness_migration_is_idempotent(tmp_path) -> None:
    _dotdocs_target(tmp_path)
    _migrate_readiness_files_to_docs(tmp_path)

    moved, notes = _migrate_readiness_files_to_docs(tmp_path)

    assert not moved
    assert notes == []
