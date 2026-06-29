from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from governancekit.configure import parse_set_pairs, run_configure


class ConfigureTests(unittest.TestCase):
    def test_set_pairs_parsing(self) -> None:
        self.assertEqual(
            parse_set_pairs(["OPERATOR_NAME=Ann", "GITHUB_OWNER=ann-org"]),
            {"OPERATOR_NAME": "Ann", "GITHUB_OWNER": "ann-org"},
        )
        with self.assertRaises(ValueError):
            parse_set_pairs(["NOEQUALS"])

    def test_fills_known_placeholder_across_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "AGENTS.md").write_text("Hi [OPERATOR_NAME]\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "x.md").write_text("owner [OPERATOR_NAME]\n", encoding="utf-8")

            result = run_configure(root, preset={"OPERATOR_NAME": "Ann"}, interactive=False)

            self.assertEqual(result.values, {"OPERATOR_NAME": "Ann"})
            self.assertEqual(len(result.changed_files), 2)
            self.assertNotIn("[OPERATOR_NAME]", (root / "AGENTS.md").read_text())
            self.assertNotIn("[OPERATOR_NAME]", (root / "docs" / "x.md").read_text())

    def test_ignores_unknown_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "README.md").write_text("status [FAIL] and [HINT]\n", encoding="utf-8")

            result = run_configure(root, preset={}, interactive=False)

            self.assertEqual(result.found_tokens, [])
            self.assertEqual(result.changed_files, [])

    def test_reports_unfilled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "AGENTS.md").write_text("[OPERATOR_NAME] [GITHUB_OWNER]\n", encoding="utf-8")

            result = run_configure(root, preset={"OPERATOR_NAME": "Ann"}, interactive=False)

            self.assertEqual(result.unfilled, ["GITHUB_OWNER"])


if __name__ == "__main__":
    unittest.main()
