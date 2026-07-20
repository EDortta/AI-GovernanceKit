from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from governancekit.doctor import _check_security_advisories


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True)


# A source line every scan must flag, kept in one place so the tests assert on
# the *scope* of the walk, not on the pattern set.
_ANTIPATTERN = "subprocess.run(cmd, shell=True)\n"
_LABEL = "shell injection risk"


class AdvisoryScanScopeTests(unittest.TestCase):
    # --- the bug: the scan walked gitignored dirs and into submodules ---
    # Observed on AcheiVc (2026-07-17): 4 of 15 hits were main.dart.js, Flutter
    # build output under .dart_tool/ (gitignored) inside a submodule. Noise that
    # trains the operator to ignore the whole check.

    def test_scan_skips_gitignored_files(self) -> None:
        # Use `.dart_tool/` — the real AcheiVc case — NOT a name already in
        # _CODEMAP_SKIP (e.g. build/, dist/), or the test would pass for the
        # wrong reason and never exercise the gitignore path (design-standards §1).
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _git_init(root)
            (root / ".gitignore").write_text(".dart_tool/\n", encoding="utf-8")
            (root / ".dart_tool").mkdir()
            (root / ".dart_tool" / "main.py").write_text(_ANTIPATTERN, encoding="utf-8")

            result = _check_security_advisories(root)

            self.assertTrue(result.passed, result.message)
            self.assertNotIn(_LABEL, result.message)

    def test_scan_does_not_descend_into_submodule(self) -> None:
        # A directory carrying its own .git is a nested repo; its contents belong
        # to another project and must not be scanned as this one's source.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _git_init(root)
            sub = root / "vendored-app"
            sub.mkdir()
            (sub / ".git").write_text("gitdir: /nowhere\n", encoding="utf-8")
            (sub / "child.py").write_text(_ANTIPATTERN, encoding="utf-8")

            result = _check_security_advisories(root)

            self.assertTrue(result.passed, result.message)
            self.assertNotIn(_LABEL, result.message)

    # --- guards against over-skipping: the scan must still find real source ---

    def test_scan_still_flags_tracked_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _git_init(root)
            (root / "app.py").write_text(_ANTIPATTERN, encoding="utf-8")

            result = _check_security_advisories(root)

            self.assertFalse(result.passed)
            self.assertIn(_LABEL, result.message)

    def test_scan_flags_non_ignored_sibling_of_ignored_dir(self) -> None:
        # Ignoring .dart_tool/ must not silence app.py next to it.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _git_init(root)
            (root / ".gitignore").write_text(".dart_tool/\n", encoding="utf-8")
            (root / ".dart_tool").mkdir()
            (root / ".dart_tool" / "gen.py").write_text(_ANTIPATTERN, encoding="utf-8")
            (root / "app.py").write_text(_ANTIPATTERN, encoding="utf-8")

            result = _check_security_advisories(root)

            self.assertFalse(result.passed)
            self.assertIn("app.py", result.message)
            self.assertNotIn("gen.py", result.message)

    def test_scan_without_git_still_scans_everything(self) -> None:
        # Fail-open (design-standards §6): with no git to consult, the scan
        # degrades to checking MORE, never less. A plain dir is still scanned.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "app.py").write_text(_ANTIPATTERN, encoding="utf-8")

            result = _check_security_advisories(root)

            self.assertFalse(result.passed)
            self.assertIn(_LABEL, result.message)


if __name__ == "__main__":
    unittest.main()
