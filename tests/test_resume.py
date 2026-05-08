from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from governancekit.resume import run_resume, _parse_resume_md, _parse_handoff_md


def write_resume_md(path: Path, work_id: str, branch: str, status: str, next_step: str) -> None:
    path.write_text(
        f"# Resume\n\n"
        f"- work_id: {work_id}\n"
        f"- date: 2026-05-08\n"
        f"- branch: {branch}\n"
        f"- status: {status}\n\n"
        f"## Current Focus\n\nDoing things.\n\n"
        f"## Next Step (DO THIS FIRST)\n\n{next_step}\n",
        encoding="utf-8",
    )


def write_valid_repo(root: Path, next_step: str = "Run the next command.") -> None:
    epic = root / "docs" / "issues" / "001-test-[started]"
    (epic / "issues").mkdir(parents=True)
    write_resume_md(epic / "RESUME.md", "WK-20260508-test", "feature/uc-001-test", "started", next_step)
    (root / "handoff.md").write_text(
        "# Handoff\n\n## Current Status\n\n"
        "- work_id: WK-20260508-test\n"
        "- date: 2026-05-08\n"
        "- branch: feature/uc-001-test\n"
        "- status: in progress\n\n"
        "## Next Steps\n\n- Run the next command.\n\n"
        "## Blockers / Risks\n\n- None.\n",
        encoding="utf-8",
    )


class ParseResumeMdTests(unittest.TestCase):
    def test_extracts_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "RESUME.md"
            write_resume_md(p, "WK-001", "feature/test", "started", "Do the thing.")
            meta, _ = _parse_resume_md(p)
            self.assertEqual(meta["work_id"], "WK-001")
            self.assertEqual(meta["branch"], "feature/test")
            self.assertEqual(meta["status"], "started")

    def test_extracts_next_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "RESUME.md"
            write_resume_md(p, "WK-001", "feature/test", "started", "Deploy to staging.")
            _, next_step = _parse_resume_md(p)
            self.assertEqual(next_step, "Deploy to staging.")

    def test_next_step_stops_at_next_heading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "RESUME.md"
            p.write_text(
                "# Resume\n\n"
                "## Next Step (DO THIS FIRST)\n\nDo A.\n\n## Notes\n\nExtra.\n",
                encoding="utf-8",
            )
            _, next_step = _parse_resume_md(p)
            self.assertEqual(next_step, "Do A.")

    def test_missing_next_step_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "RESUME.md"
            p.write_text("# Resume\n\n- work_id: WK-001\n", encoding="utf-8")
            _, next_step = _parse_resume_md(p)
            self.assertEqual(next_step, "")


class ParseHandoffMdTests(unittest.TestCase):
    def test_single_entry_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "handoff.md"
            p.write_text(
                "# Handoff\n\n## Current Status\n\n"
                "- work_id: WK-20260508-test\n"
                "- date: 2026-05-08\n"
                "- branch: feature/uc-001\n"
                "- status: in progress\n\n"
                "## Next Steps\n\n- Do X.\n- Do Y.\n",
                encoding="utf-8",
            )
            entry = _parse_handoff_md(p)
            self.assertIsNotNone(entry)
            self.assertEqual(entry.work_id, "WK-20260508-test")
            self.assertEqual(entry.branch, "feature/uc-001")
            self.assertIn("Do X", entry.next_steps)

    def test_multi_entry_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "handoff.md"
            p.write_text(
                "# Handoff Log\n\n---\n\n"
                "## [2026-05-08] WK-20260508-newest - review\n\n"
                "- Status: review\n"
                "- Summary: Latest work done.\n"
                "- Next steps:\n  - Merge PR.\n"
                "- Blockers/Risks:\n  - No blocker.\n\n---\n\n"
                "## [2026-05-04] WK-20260504-older - done\n\n"
                "- Status: done\n",
                encoding="utf-8",
            )
            entry = _parse_handoff_md(p)
            self.assertIsNotNone(entry)
            self.assertEqual(entry.work_id, "WK-20260508-newest")
            self.assertEqual(entry.date, "2026-05-08")
            self.assertEqual(entry.summary, "Latest work done.")

    def test_unparseable_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "handoff.md"
            p.write_text("just some random text without any known structure\n", encoding="utf-8")
            self.assertIsNone(_parse_handoff_md(p))


class RunResumeTests(unittest.TestCase):
    def test_valid_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_repo(root)
            result = run_resume(root)
            self.assertEqual(result.work_id, "WK-20260508-test")
            self.assertEqual(result.branch, "feature/uc-001-test")
            self.assertEqual(result.next_step, "Run the next command.")
            self.assertIsNotNone(result.handoff)
            self.assertEqual(result.warning, "")

    def test_missing_resume_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_resume(Path(tmp))
            self.assertEqual(result.next_step, "")
            self.assertIsNotNone(result.warning)

    def test_missing_handoff_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            epic = root / "docs" / "issues" / "001-test-[started]"
            (epic / "issues").mkdir(parents=True)
            write_resume_md(
                epic / "RESUME.md", "WK-X", "feature/x", "started", "Do the thing."
            )
            result = run_resume(root)
            self.assertEqual(result.next_step, "Do the thing.")
            self.assertIsNone(result.handoff)
            self.assertIn("handoff", result.warning.lower())

    def test_prefers_started_epic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            issues = root / "docs" / "issues"
            for name, step in [
                ("001-alpha-[review]", "Wrong step."),
                ("002-beta-[started]", "Correct step."),
            ]:
                d = issues / name
                (d / "issues").mkdir(parents=True)
                write_resume_md(d / "RESUME.md", "WK-X", "feature/x", "started", step)
            result = run_resume(root)
            self.assertEqual(result.next_step, "Correct step.")


if __name__ == "__main__":
    unittest.main()
