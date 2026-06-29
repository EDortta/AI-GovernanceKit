from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from governancekit import install_agents as ia


def _make_source(src: Path) -> None:
    (src / "AGENTS.md").write_text("# kit AGENTS [OPERATOR_NAME]\n", encoding="utf-8")
    (src / "docs" / "agents").mkdir(parents=True)
    (src / "docs" / "agents" / "programmer.md").write_text("v2\n", encoding="utf-8")
    (src / "docs" / "required-reading.md").write_text("- (none)\n", encoding="utf-8")


class InstallAgentsTests(unittest.TestCase):
    def test_ensure_project_docs_creates_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ia._ensure_project_docs(root)
            readme = root / ia._PROJECT_DOCS_DIR / "README.md"
            self.assertTrue(readme.is_file())

            readme.write_text("custom\n", encoding="utf-8")
            ia._ensure_project_docs(root)
            self.assertEqual(readme.read_text(), "custom\n")

    def test_docs_only_replaces_only_doc_paths(self) -> None:
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            (dst / "AGENTS.md").write_text("PROJECT EDITED\n", encoding="utf-8")

            installed = ia._do_upgrade(src, dst, paths=ia._DOCS_PATHS)

            self.assertIn("docs/agents", installed)
            self.assertNotIn("AGENTS.md", installed)
            # AGENTS.md (a rule file) untouched by --docs-only
            self.assertEqual((dst / "AGENTS.md").read_text(), "PROJECT EDITED\n")
            self.assertEqual((dst / "docs" / "agents" / "programmer.md").read_text(), "v2\n")

    def test_gitignore_carves_out_project_docs(self) -> None:
        entries = ia._gitignore_entries(["AGENTS.md", "docs", "handoff.md"])
        self.assertIn("docs/*", entries)
        self.assertIn("!docs/project/", entries)
        self.assertNotIn("docs", entries)  # bare 'docs' would ignore the carve-out
        # ordering: the re-include must come after docs/* for git to honour it
        self.assertLess(entries.index("docs/*"), entries.index("!docs/project/"))

    def test_required_reading_not_in_docs_paths(self) -> None:
        # required-reading.md is project-owned: must survive --upgrade / --docs-only.
        self.assertNotIn("docs/required-reading.md", ia._DOCS_PATHS)
        self.assertNotIn("docs/required-reading.md", ia._UPGRADE_PATHS)


if __name__ == "__main__":
    unittest.main()
