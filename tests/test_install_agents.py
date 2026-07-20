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

    def test_upgrade_preserves_project_authored_agent(self) -> None:
        # The real-world case: jk-structure keeps its own agents (build-deploy.md etc.)
        # inside .docs/agents/. An upgrade must refresh kit files and keep those.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            agents = dst / ".docs" / "agents"
            agents.mkdir(parents=True)
            (agents / "programmer.md").write_text("v1\n", encoding="utf-8")
            (agents / "build-deploy.md").write_text("PROJECT RULE\n", encoding="utf-8")

            preserved: list[str] = []
            ia._do_upgrade(src, dst, paths=ia._KIT_DOC_PATHS, manifest={}, preserved=preserved)

            self.assertEqual((agents / "programmer.md").read_text(), "v2\n")
            self.assertEqual((agents / "build-deploy.md").read_text(), "PROJECT RULE\n")
            self.assertIn(".docs/agents/build-deploy.md", preserved)

    def test_upgrade_retires_untouched_kit_file(self) -> None:
        # A file the kit shipped and later dropped IS removed — but only because the
        # manifest proves the kit wrote it and the project never edited it.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            agents = dst / ".docs" / "agents"
            agents.mkdir(parents=True)
            retired = agents / "old-agent.md"
            retired.write_text("kit v1 content\n", encoding="utf-8")
            manifest = {".docs/agents/old-agent.md": ia._file_sha256(retired)}

            preserved: list[str] = []
            ia._do_upgrade(
                src, dst, paths=ia._KIT_DOC_PATHS, manifest=manifest, preserved=preserved
            )

            self.assertFalse(retired.exists())
            self.assertEqual(preserved, [])

    def test_upgrade_keeps_locally_edited_kit_file(self) -> None:
        # Kit-authored but edited by the project: the hash no longer matches, so the
        # edit is treated as project intent and survives.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            agents = dst / ".docs" / "agents"
            agents.mkdir(parents=True)
            edited = agents / "old-agent.md"
            edited.write_text("EDITED BY PROJECT\n", encoding="utf-8")
            manifest = {".docs/agents/old-agent.md": ia._file_sha256(Path(__file__))}

            preserved: list[str] = []
            ia._do_upgrade(
                src, dst, paths=ia._KIT_DOC_PATHS, manifest=manifest, preserved=preserved
            )

            self.assertEqual(edited.read_text(), "EDITED BY PROJECT\n")
            self.assertIn(".docs/agents/old-agent.md", preserved)

    def test_state_roundtrip_and_merge(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(ia._state_files(ia._read_state(root)), {})

            (root / ".docs" / "agents").mkdir(parents=True)
            (root / ".docs" / "agents" / "programmer.md").write_text("v2\n", encoding="utf-8")
            ia._write_state(root, [".docs/agents"], repo="r", ref="v1", metadata={"OPERATOR_NAME": "Esteban"})
            first = ia._state_files(ia._read_state(root))
            self.assertIn(".docs/agents/programmer.md", first)

            # A narrower later run must not erase what it did not touch.
            (root / "AGENTS.md").write_text("# kit\n", encoding="utf-8")
            ia._write_state(root, ["AGENTS.md"], repo="r", ref="v2", metadata={})
            merged = ia._state_files(ia._read_state(root))
            self.assertIn("AGENTS.md", merged)
            self.assertIn(".docs/agents/programmer.md", merged)

    def test_metadata_reapplied_without_a_terminal(self) -> None:
        # The continuity case: an upgrade overwrote the file with a fresh template, so
        # [OPERATOR_NAME] is raw again. A stored answer must be re-applied silently
        # instead of leaving the placeholder exposed.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text("# kit [OPERATOR_NAME]\n", encoding="utf-8")

            values = ia._fill_placeholders(
                root, ["AGENTS.md"], known={"OPERATOR_NAME": "Esteban"}
            )

            self.assertEqual((root / "AGENTS.md").read_text(), "# kit Esteban\n")
            self.assertEqual(values["OPERATOR_NAME"], "Esteban")

    def test_unknown_metadata_survives_as_unfilled(self) -> None:
        # A variable the kit newly introduced has no stored answer; it must stay raw
        # (to be asked later) rather than being invented.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text(
                "[OPERATOR_NAME] / [SMTP_ACCOUNT]\n", encoding="utf-8"
            )

            values = ia._fill_placeholders(
                root, ["AGENTS.md"], known={"OPERATOR_NAME": "Esteban"}
            )

            self.assertEqual((root / "AGENTS.md").read_text(), "Esteban / [SMTP_ACCOUNT]\n")
            self.assertNotIn("SMTP_ACCOUNT", values)

    def test_state_hash_matches_file_after_placeholder_fill(self) -> None:
        # Regression: hashing the pristine template would never match the configured
        # file, making every filled file look hand-edited on the next upgrade.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            agents = root / "AGENTS.md"
            agents.write_text("# kit [OPERATOR_NAME]\n", encoding="utf-8")

            metadata = ia._fill_placeholders(
                root, ["AGENTS.md"], known={"OPERATOR_NAME": "Esteban"}
            )
            ia._write_state(root, ["AGENTS.md"], repo="r", ref="v1", metadata=metadata)

            recorded = ia._state_files(ia._read_state(root))["AGENTS.md"]
            self.assertEqual(recorded, ia._file_sha256(agents))
            self.assertEqual(
                ia._state_metadata(ia._read_state(root))["OPERATOR_NAME"], "Esteban"
            )

    def test_edited_kit_file_is_stashed_before_being_replaced(self) -> None:
        # A kit file the project edited is still kit-owned, so the new version wins —
        # but the edit must be recoverable, not silently destroyed.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            agents = dst / ".docs" / "agents"
            agents.mkdir(parents=True)
            (agents / "programmer.md").write_text("EDITED BY PROJECT\n", encoding="utf-8")
            manifest = {".docs/agents/programmer.md": ia._file_sha256(Path(__file__))}

            overwritten: list[str] = []
            ia._do_upgrade(
                src, dst, paths=ia._KIT_DOC_PATHS, manifest=manifest,
                preserved=[], overwritten=overwritten,
            )

            self.assertEqual((agents / "programmer.md").read_text(), "v2\n")
            self.assertIn(".docs/agents/programmer.md", overwritten)
            stash = dst / ia._STATE_DIR / "overwritten" / ".docs/agents/programmer.md"
            self.assertEqual(stash.read_text(), "EDITED BY PROJECT\n")

    def test_unedited_kit_file_is_replaced_without_stashing(self) -> None:
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            agents = dst / ".docs" / "agents"
            agents.mkdir(parents=True)
            pristine = agents / "programmer.md"
            pristine.write_text("v1\n", encoding="utf-8")
            manifest = {".docs/agents/programmer.md": ia._file_sha256(pristine)}

            overwritten: list[str] = []
            ia._do_upgrade(
                src, dst, paths=ia._KIT_DOC_PATHS, manifest=manifest,
                preserved=[], overwritten=overwritten,
            )

            self.assertEqual(pristine.read_text(), "v2\n")
            self.assertEqual(overwritten, [])

    def test_secrets_ignored_but_manifest_shared(self) -> None:
        # The team must share the hashes; only the credential half stays out of git.
        for track in (True, False):
            entries = ia._gitignore_entries(["AGENTS.md", "docs/agents"], track_kit_docs=track)
            self.assertIn(ia._SECRETS_FILE, entries)
            self.assertNotIn(f"{ia._STATE_DIR}/", entries)
            self.assertNotIn(ia._STATE_FILE, entries)

    def test_secrets_split_from_shareable_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ia._write_state(
                root, [], repo="r", ref="v1",
                metadata={"OPERATOR_NAME": "Esteban", "SMTP_ACCOUNT": "a@b.c"},
            )
            manifest = ia._read_json(root / ia._STATE_FILE)
            secrets = ia._read_json(root / ia._SECRETS_FILE)

            self.assertEqual(manifest["metadata"], {"OPERATOR_NAME": "Esteban"})
            self.assertEqual(secrets["metadata"], {"SMTP_ACCOUNT": "a@b.c"})
            self.assertEqual((root / ia._SECRETS_FILE).stat().st_mode & 0o777, 0o600)
            # Callers still see one logical state.
            self.assertEqual(
                ia._state_metadata(ia._read_state(root)),
                {"OPERATOR_NAME": "Esteban", "SMTP_ACCOUNT": "a@b.c"},
            )

    def test_no_secrets_file_when_nothing_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ia._write_state(root, [], repo="r", ref="v1", metadata={"ORG_NAME": "YouBR"})
            self.assertFalse((root / ia._SECRETS_FILE).exists())

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
