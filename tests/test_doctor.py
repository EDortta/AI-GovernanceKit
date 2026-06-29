from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from governancekit.doctor import run_doctor


class DoctorTests(unittest.TestCase):
    def test_valid_repository_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)

            result = run_doctor(root)

            self.assertTrue(result.ok, result.checks)

    def test_missing_limits_ready_flag_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / "docs" / "limits.md").write_text("limits_ready: no\n", encoding="utf-8")

            result = run_doctor(root)

            self.assertFalse(result.ok)
            self.assertIn("docs/limits.md", failed_check_names(result))

    def test_empty_resume_next_step_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            resume = root / "docs" / "issues" / "001-bootstrap-[started]" / "RESUME.md"
            resume.write_text("# Resume\n\n## Next Step (DO THIS FIRST)\n", encoding="utf-8")

            result = run_doctor(root)

            self.assertFalse(result.ok)
            self.assertIn("RESUME.md next step", failed_check_names(result))


    def test_missing_required_reading_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / "docs" / "required-reading.md").unlink()

            result = run_doctor(root)

            self.assertFalse(result.ok)
            self.assertIn("docs/required-reading.md", failed_check_names(result))

    def test_required_reading_none_sentinel_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / "docs" / "required-reading.md").write_text(
                "# Required Reading\n\n- (none)\n", encoding="utf-8"
            )

            result = run_doctor(root)

            self.assertNotIn("docs/required-reading.md", failed_check_names(result))

    def test_required_reading_only_stub_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / "docs" / "required-reading.md").write_text(
                "# Required Reading\n\n- [path]\n", encoding="utf-8"
            )

            result = run_doctor(root)

            self.assertIn("docs/required-reading.md", failed_check_names(result))


def write_valid_repo(root: Path) -> None:
    (root / "docs" / "issues" / "001-bootstrap-[started]" / "issues").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
    (root / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    (root / "handoff.md").write_text("# Handoff\n", encoding="utf-8")
    (root / "docs" / "software-overview.md").write_text(
        "project_context_ready: yes\n",
        encoding="utf-8",
    )
    (root / "docs" / "limits.md").write_text("limits_ready: yes\n", encoding="utf-8")
    (root / "docs" / "required-reading.md").write_text(
        "# Required Reading\n\n- `docs/software-overview.md` — context\n",
        encoding="utf-8",
    )

    epic = root / "docs" / "issues" / "001-bootstrap-[started]"
    (epic / "README.md").write_text("# Epic README\n", encoding="utf-8")
    (epic / "epic.md").write_text("# Epic\n", encoding="utf-8")
    (epic / "RESUME.md").write_text(
        "# Resume\n\n## Next Step (DO THIS FIRST)\n\nRun the next validation command.\n",
        encoding="utf-8",
    )
    (epic / "issues" / "001-task-[started].md").write_text("# Task\n", encoding="utf-8")


def failed_check_names(result) -> set[str]:
    return {check.name for check in result.checks if not check.passed}


if __name__ == "__main__":
    unittest.main()

