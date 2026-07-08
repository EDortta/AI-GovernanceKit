from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from governancekit.configure import (
    parse_set_pairs,
    run_configure,
    run_configure_identity,
)
from governancekit.identity import load_identity


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


class ConfigureIdentityTests(unittest.TestCase):
    def test_non_interactive_missing_required_does_not_save(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = run_configure_identity(
                root, preset={"operator_name": "Ann"}, interactive=False
            )
            self.assertFalse(result.saved)
            self.assertIn("host_id", result.missing_required)
            self.assertIn("instance_path", result.missing_required)
            self.assertIsNone(load_identity(root))

    def test_non_interactive_complete_saves_and_gitignores(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = run_configure_identity(
                root,
                preset={
                    "operator_name": "Ann",
                    "host_id": "host-a",
                    "instance_path": "/home/ann/proj",
                    "assigned_ports": "8630,6062",
                },
                interactive=False,
            )
            self.assertTrue(result.saved)
            saved = load_identity(root)
            self.assertIsNotNone(saved)
            self.assertEqual(saved.operator_name, "Ann")
            self.assertEqual(saved.assigned_ports, ["8630", "6062"])
            self.assertTrue((root / ".governancekit-identity.json").is_file())
            gitignore = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertIn(".governancekit-identity.json", gitignore)

    def test_gitignore_entry_not_duplicated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            preset = {
                "operator_name": "Ann",
                "host_id": "host-a",
                "instance_path": "/home/ann/proj",
            }
            run_configure_identity(root, preset=preset, interactive=False)
            run_configure_identity(root, preset=preset, interactive=False)
            gitignore = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(gitignore.count(".governancekit-identity.json"), 1)

    def test_cli_configure_set_ok_when_identity_unconfigured(self) -> None:
        # Regression: `configure --set KEY=VALUE` with NO identity flags must exit 0
        # when the placeholder fill succeeds, even though host identity is not yet
        # configured (non-interactive). Previously it returned 1 and broke CI/piped use.
        from governancekit import cli

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "AGENTS.md").write_text("owner: [OPERATOR_NAME]\n", encoding="utf-8")

            code = cli.main(["--root", str(root), "configure", "--set", "OPERATOR_NAME=Ann"])

            self.assertEqual(code, 0)
            self.assertIn("Ann", (root / "AGENTS.md").read_text(encoding="utf-8"))
            # And identity was genuinely not saved (so we exercised the missing-required path).
            self.assertFalse((root / ".governancekit-identity.json").is_file())

    def test_cli_configure_errors_when_identity_flags_incomplete(self) -> None:
        # Complement: if the user DID pass an identity flag but left required fields
        # out, that is a real error and must still exit 1.
        from governancekit import cli

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "AGENTS.md").write_text("owner: [OPERATOR_NAME]\n", encoding="utf-8")

            code = cli.main(
                ["--root", str(root), "configure", "--set", "OPERATOR_NAME=Ann",
                 "--operator-name", "Ann"]
            )

            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
