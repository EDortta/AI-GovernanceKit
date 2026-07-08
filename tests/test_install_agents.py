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
    (src / "docs" / "software-overview.md").write_text(
        "- project_context_ready: yes\n", encoding="utf-8"
    )


class InstallAgentsTests(unittest.TestCase):
    def test_dest_rel_maps_kit_docs_but_not_project(self) -> None:
        # Kit docs relocate to .docs/; project-owned seeds stay in docs/.
        self.assertEqual(ia._dest_rel("docs/agents"), ".docs/agents")
        self.assertEqual(ia._dest_rel("docs/software-overview.md"), ".docs/software-overview.md")
        self.assertEqual(ia._dest_rel("docs/required-reading.md"), "docs/required-reading.md")
        self.assertEqual(ia._dest_rel("AGENTS.md"), "AGENTS.md")

    def test_resolve_src_prefers_dotdocs_source(self) -> None:
        # A restructured source stores kit docs under .docs/; project seeds in docs/.
        with tempfile.TemporaryDirectory() as s:
            src = Path(s)
            (src / ".docs" / "agents").mkdir(parents=True)
            (src / "docs").mkdir()
            (src / "docs" / "required-reading.md").write_text("- (none)\n", encoding="utf-8")
            self.assertEqual(ia._resolve_src(src, "docs/agents"), src / ".docs" / "agents")
            self.assertEqual(
                ia._resolve_src(src, "docs/required-reading.md"),
                src / "docs" / "required-reading.md",
            )

    def test_fresh_install_reads_dotdocs_source(self) -> None:
        # Fresh install from a .docs/ source lands kit in .docs/ and seeds in docs/.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            (src / "AGENTS.md").write_text("# kit\n", encoding="utf-8")
            (src / ".docs" / "agents").mkdir(parents=True)
            (src / ".docs" / "agents" / "programmer.md").write_text("v3\n", encoding="utf-8")
            (src / ".docs" / "software-overview.md").write_text(
                "- project_context_ready: yes\n", encoding="utf-8"
            )
            (src / "docs").mkdir()
            (src / "docs" / "required-reading.md").write_text("- (none)\n", encoding="utf-8")

            installed = ia._do_fresh(src, dst, force=True)
            self.assertIn(".docs/agents", installed)
            self.assertEqual((dst / ".docs" / "agents" / "programmer.md").read_text(), "v3\n")
            self.assertEqual((dst / ".docs" / "software-overview.md").read_text().strip(),
                             "- project_context_ready: no")
            self.assertEqual((dst / "docs" / "required-reading.md").read_text(), "- (none)\n")
            self.assertFalse((dst / "docs" / "agents").exists())

    def test_ensure_project_docs_creates_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ia._ensure_project_docs(root)
            readme = root / ia._PROJECT_DOCS_DIR / "README.md"
            self.assertTrue(readme.is_file())

            readme.write_text("custom\n", encoding="utf-8")
            ia._ensure_project_docs(root)
            self.assertEqual(readme.read_text(), "custom\n")

    def test_docs_only_installs_into_dotdocs(self) -> None:
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            (dst / "AGENTS.md").write_text("PROJECT EDITED\n", encoding="utf-8")

            installed = ia._do_upgrade(src, dst, paths=ia._KIT_DOC_PATHS)

            self.assertIn(".docs/agents", installed)
            self.assertNotIn("AGENTS.md", installed)
            # AGENTS.md (a rule file) untouched by --docs-only
            self.assertEqual((dst / "AGENTS.md").read_text(), "PROJECT EDITED\n")
            self.assertEqual((dst / ".docs" / "agents" / "programmer.md").read_text(), "v2\n")

    def test_gitignore_uses_dotdocs_and_leaves_docs_tracked(self) -> None:
        entries = ia._gitignore_entries(
            ["AGENTS.md", "docs/agents", "docs/required-reading.md", "handoff.md"]
        )
        self.assertIn(".docs/", entries)
        self.assertIn("AGENTS.md", entries)
        self.assertIn("handoff.md", entries)
        # Project-owned docs/ files must never be ignored.
        self.assertNotIn("docs/required-reading.md", entries)
        self.assertNotIn("docs/*", entries)
        # A single .docs/ entry, not one per kit subpath.
        self.assertEqual(entries.count(".docs/"), 1)

    def test_gitignore_tracks_kit_docs_when_opted_in(self) -> None:
        entries = ia._gitignore_entries(
            ["AGENTS.md", "docs/agents", ".credentials"], track_kit_docs=True
        )
        self.assertNotIn(".docs/", entries)
        # Secrets and rule files stay ignored regardless.
        self.assertIn(".credentials", entries)
        self.assertIn("AGENTS.md", entries)

    def test_gitignore_section_keeps_secrets_across_modes(self) -> None:
        # Regression: the managed .gitignore section must always cover .credentials
        # and handoff.md so real token symlinks never become trackable — even when
        # the user opts to track kit docs.
        with tempfile.TemporaryDirectory() as temp_dir:
            gi = Path(temp_dir) / ".gitignore"
            ia._update_gitignore(gi, ia._FRESH_PATHS, track_kit_docs=True)
            section = gi.read_text(encoding="utf-8")
            self.assertIn(".credentials", section)
            self.assertIn("handoff.md", section)
        self.assertIn(".credentials", ia._FRESH_PATHS)
        self.assertIn("handoff.md", ia._FRESH_PATHS)

    def test_track_config_persists_and_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            # Explicit CLI value is persisted and returned.
            self.assertTrue(ia._resolve_track_kit_docs(root, True))
            self.assertEqual(ia._read_kit_config(root).get("track_kit_docs"), True)
            # Non-interactive with existing config reads the persisted value.
            self.assertTrue(ia._resolve_track_kit_docs(root, None))

    def test_migrate_legacy_layout_moves_kit_and_promotes_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            (docs / "workflows").mkdir(parents=True)
            (docs / "workflows" / "session-close.md").write_text("wf\n", encoding="utf-8")
            (docs / "software-overview.md").write_text("- project_context_ready: yes\n", encoding="utf-8")
            (docs / "required-reading.md").write_text("- (none)\n", encoding="utf-8")
            (docs / "issues").mkdir()
            (docs / "issues" / "README.md").write_text("kit issues readme\n", encoding="utf-8")
            (docs / "issues" / "001-active-[started]").mkdir()
            (docs / "project").mkdir()
            (docs / "project" / "mydoc.md").write_text("mine\n", encoding="utf-8")

            migrated, notes = ia._migrate_legacy_layout(root)
            self.assertTrue(migrated)

            # Kit docs moved to .docs/
            self.assertTrue((root / ".docs" / "workflows" / "session-close.md").is_file())
            self.assertTrue((root / ".docs" / "software-overview.md").is_file())
            self.assertTrue((root / ".docs" / "issues" / "README.md").is_file())
            # Project docs promoted to docs/
            self.assertTrue((root / "docs" / "mydoc.md").is_file())
            self.assertFalse((root / "docs" / "project").exists())
            # Project-owned files stay in docs/
            self.assertTrue((root / "docs" / "required-reading.md").is_file())
            # Active issue stays in docs/issues/
            self.assertTrue((root / "docs" / "issues" / "001-active-[started]").is_dir())
            # Backup created
            self.assertTrue((root / ia._MIGRATION_BACKUP_DIR).is_dir())

            # Idempotent: .docs/ now exists → second run is a no-op.
            migrated2, _ = ia._migrate_legacy_layout(root)
            self.assertFalse(migrated2)

    def test_migrate_ignores_non_kit_project_with_generic_docs(self) -> None:
        # Regression: a project that merely has a generic docs/ (its own
        # software-overview.md + a GitHub Pages site) but NO kit markers must never be
        # migrated — otherwise --upgrade would hide its site under gitignored .docs/.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            docs.mkdir()
            (docs / "software-overview.md").write_text("my own overview\n", encoding="utf-8")
            (docs / "index.html").write_text("<html>my site</html>", encoding="utf-8")
            (docs / "articles").mkdir()
            (docs / "articles" / "post.md").write_text("post\n", encoding="utf-8")

            migrated, _ = ia._migrate_legacy_layout(root)

            self.assertFalse(migrated)
            self.assertFalse((root / ".docs").exists())
            self.assertFalse((root / ia._MIGRATION_BACKUP_DIR).exists())
            # The project's own docs/ is untouched.
            self.assertTrue((docs / "index.html").is_file())
            self.assertTrue((docs / "articles" / "post.md").is_file())

    def test_migrate_completes_interrupted_run_without_overwriting(self) -> None:
        # Regression: a pre-existing .docs/ (from an interrupted prior run) must NOT
        # strand the remaining kit files in docs/ — migration completes, never
        # overwriting what .docs/ already holds.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            (docs / "agents").mkdir(parents=True)
            (docs / "agents" / "programmer.md").write_text("kit rules\n", encoding="utf-8")
            (docs / "workflows").mkdir()
            (docs / "workflows" / "session-close.md").write_text("wf\n", encoding="utf-8")
            # Simulate an interrupted migration: .docs/agents already moved.
            (root / ".docs" / "agents").mkdir(parents=True)
            (root / ".docs" / "agents" / "programmer.md").write_text("ALREADY MOVED\n", encoding="utf-8")

            migrated, _ = ia._migrate_legacy_layout(root)

            self.assertTrue(migrated)
            # Remaining kit file completed into .docs/.
            self.assertTrue((root / ".docs" / "workflows" / "session-close.md").is_file())
            # Existing .docs/ entry preserved, not clobbered.
            self.assertEqual(
                (root / ".docs" / "agents" / "programmer.md").read_text(encoding="utf-8"),
                "ALREADY MOVED\n",
            )

    def test_required_reading_stays_project_owned(self) -> None:
        # required-reading.md is project-owned: never overwritten by kit paths.
        self.assertNotIn("docs/required-reading.md", ia._KIT_DOC_PATHS)
        self.assertNotIn("docs/required-reading.md", ia._UPGRADE_PATHS)
        # And it seeds into docs/, not .docs/
        self.assertEqual(ia._dest_rel("docs/required-reading.md"), "docs/required-reading.md")

    def test_fill_placeholders_ignores_doc_example_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            doc = root / "AGENTS.md"
            doc.write_text(
                "Replace [PLACEHOLDER] and [TOKEN] examples. Owner: [OPERATOR_NAME].\n",
                encoding="utf-8",
            )
            ia._fill_placeholders(root, ["AGENTS.md"])
            text = doc.read_text(encoding="utf-8")
            self.assertIn("[PLACEHOLDER]", text)
            self.assertIn("[TOKEN]", text)
            self.assertIn("[OPERATOR_NAME]", text)


if __name__ == "__main__":
    unittest.main()
