from __future__ import annotations

import contextlib
import io
import shutil
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from governancekit import install_agents as ia
from governancekit.path_safety import UnsafePathError


def _make_source(src: Path) -> None:
    (src / "AGENTS.md").write_text(
        "# kit AGENTS {{OPERATOR_NAME}} {{SMTP_ACCOUNT}}\n", encoding="utf-8"
    )
    (src / "docs" / "agents").mkdir(parents=True)
    (src / "docs" / "agents" / "programmer.md").write_text("v2\n", encoding="utf-8")
    (src / "docs" / "governancekit-integration.json").write_text(
        '{"schema_version": 1, "ai_agents": {"repo": "EDortta/AI-Agents", "ref": "v1.1.6"}, '
        '"governancekit": {"version_range": ">=0.2.2,<0.4.0", "required_features": ["version-reporting"]}}\n',
        encoding="utf-8",
    )
    (src / "docs" / "required-reading.md").write_text("- (none)\n", encoding="utf-8")
    (src / "docs" / "software-overview.md").write_text(
        "- project_context_ready: yes\n", encoding="utf-8"
    )


class InstallAgentsTests(unittest.TestCase):
    def test_dest_rel_maps_kit_docs_but_not_project(self) -> None:
        # Kit docs relocate to .docs/; project-owned seeds stay in docs/.
        self.assertEqual(ia._dest_rel("docs/agents"), ".docs/agents")
        self.assertEqual(ia._dest_rel("docs/software-overview.md"), "docs/software-overview.md")
        self.assertEqual(ia._dest_rel("docs/limits.md"), "docs/limits.md")
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
            (src / ".docs" / "governancekit-integration.json").write_text(
                '{"schema_version": 1, "ai_agents": {"repo": "EDortta/AI-Agents", "ref": "v1.1.6"}, '
                '"governancekit": {"version_range": ">=0.2.2,<0.4.0", "required_features": ["version-reporting"]}}\n',
                encoding="utf-8",
            )
            (src / "docs").mkdir()
            (src / "docs" / "software-overview.md").write_text(
                "- project_context_ready: yes\n", encoding="utf-8"
            )
            (src / "docs" / "required-reading.md").write_text("- (none)\n", encoding="utf-8")

            installed = ia._do_fresh(src, dst, force=True)
            self.assertIn(".docs/agents", installed)
            self.assertIn(".docs/governancekit-integration.json", installed)
            self.assertEqual((dst / ".docs" / "agents" / "programmer.md").read_text(), "v3\n")
            self.assertIn('"schema_version": 1', (dst / ".docs" / "governancekit-integration.json").read_text())
            # Project-owned, so it lands in docs/ — with the flag reset, because the
            # project must re-answer it for this project.
            self.assertEqual((dst / "docs" / "software-overview.md").read_text().strip(),
                             "- project_context_ready: no")
            self.assertFalse((dst / ".docs" / "software-overview.md").exists())
            self.assertEqual((dst / "docs" / "required-reading.md").read_text(), "- (none)\n")
            self.assertFalse((dst / "docs" / "agents").exists())

    def test_ensure_project_docs_creates_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ia._ensure_project_docs(root)
            readme = root / ia._PROJECT_DOCS_DIR / "README.md"
            required_reading = root / ia._PROJECT_DOCS_DIR / "required-reading.md"
            project_rules = root / ia._PROJECT_DOCS_DIR / "project-rules.md"
            self.assertTrue(readme.is_file())
            self.assertIn("docs/project-rules.md", required_reading.read_text(encoding="utf-8"))
            self.assertTrue(project_rules.is_file())

            readme.write_text("custom\n", encoding="utf-8")
            ia._ensure_project_docs(root)
            self.assertEqual(readme.read_text(), "custom\n")

    def test_ensure_project_docs_adds_missing_index_to_existing_docs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / ia._PROJECT_DOCS_DIR
            docs.mkdir()
            (docs / "README.md").write_text("project docs\n", encoding="utf-8")

            ia._ensure_project_docs(root)

            self.assertEqual((docs / "README.md").read_text(encoding="utf-8"), "project docs\n")
            self.assertTrue((docs / "required-reading.md").is_file())

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

    def test_full_upgrade_state_prunes_missing_paths_but_docs_only_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".gk").mkdir()
            (root / ".gk" / "manifest.json").write_text(
                '{"files":{"gone.md":"hash"},"metadata":{}}', encoding="utf-8"
            )
            ia._write_state(root, [], repo="r", ref="v2", metadata={}, prune_missing=True)
            self.assertNotIn("gone.md", ia._state_files(ia._read_state(root)))

    def test_metadata_reapplied_without_a_terminal(self) -> None:
        # The continuity case: an upgrade overwrote the file with a fresh template, so
        # {{OPERATOR_NAME}} is raw again. A stored answer must be re-applied silently
        # instead of leaving the placeholder exposed.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text("# kit {{OPERATOR_NAME}}\n", encoding="utf-8")

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
                "{{OPERATOR_NAME}} / {{SMTP_ACCOUNT}}\n", encoding="utf-8"
            )

            values = ia._fill_placeholders(
                root, ["AGENTS.md"], known={"OPERATOR_NAME": "Esteban"}
            )

            self.assertEqual((root / "AGENTS.md").read_text(), "Esteban / {{SMTP_ACCOUNT}}\n")
            self.assertNotIn("SMTP_ACCOUNT", values)

    def test_state_hash_matches_file_after_placeholder_fill(self) -> None:
        # Regression: hashing the pristine template would never match the configured
        # file, making every filled file look hand-edited on the next upgrade.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            agents = root / "AGENTS.md"
            agents.write_text("# kit {{OPERATOR_NAME}}\n", encoding="utf-8")

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
        # The team must share the hashes; only the local half stays out of git —
        # the override, plus the legacy pair for the un-migrated fleet.
        for track in (True, False):
            entries = ia._gitignore_entries(["AGENTS.md", "docs/agents"], track_kit_docs=track)
            self.assertIn(ia._OVERRIDE_FILE, entries)
            self.assertIn(ia._OPERATOR_FILE, entries)
            self.assertIn(ia._SECRETS_FILE, entries)
            self.assertNotIn(f"{ia._STATE_DIR}/", entries)
            self.assertNotIn(ia._STATE_FILE, entries)

    def test_operator_and_secrets_split_from_shareable_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ia._write_state(
                root, [], repo="r", ref="v1",
                metadata={
                    "OPERATOR_NAME": "Esteban",
                    "SMTP_ACCOUNT": "a@b.c",
                    "GITHUB_OWNER": "uuid-123",
                },
            )
            manifest = ia._read_json(root / ia._STATE_FILE)
            override = ia._read_json(root / ia._OVERRIDE_FILE)

            # `GITHUB_OWNER` is SHAREABLE: it identifies the repository, not a person,
            # so it belongs in the tracked half.
            self.assertEqual(manifest["metadata"], {"GITHUB_OWNER": "uuid-123"})
            # AC-29: the local half is ONE file, `.gk/manifest.override.json`.
            # The property this test always guarded is unchanged — an operator
            # answer never reaches the tracked manifest — only the local
            # destination moved. The legacy pair is not created any more: two
            # local files were two sources of truth, and `_write_state`
            # migrates and deletes them.
            self.assertEqual(
                override["metadata"],
                {"OPERATOR_NAME": "Esteban", "SMTP_ACCOUNT": "a@b.c"},
            )
            self.assertFalse((root / ia._OPERATOR_FILE).exists())
            self.assertFalse((root / ia._SECRETS_FILE).exists())
            self.assertEqual(ia._SENSITIVE_PLACEHOLDERS, frozenset())
            self.assertEqual((root / ia._OVERRIDE_FILE).stat().st_mode & 0o777, 0o600)
            # Callers still see one logical state.
            self.assertEqual(
                ia._state_metadata(ia._read_state(root)),
                {
                    "OPERATOR_NAME": "Esteban",
                    "SMTP_ACCOUNT": "a@b.c",
                    "GITHUB_OWNER": "uuid-123",
                },
            )

    def test_no_secrets_file_when_nothing_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ia._write_state(root, [], repo="r", ref="v1", metadata={"ORG_NAME": "YouBR"})
            self.assertFalse((root / ia._OPERATOR_FILE).exists())
            self.assertFalse((root / ia._SECRETS_FILE).exists())

    def test_legacy_manifest_operator_metadata_is_ignored_until_reentered(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ia._STATE_DIR).mkdir()
            (root / ia._STATE_FILE).write_text(
                '{\n'
                '  "state_version": 1,\n'
                '  "repo": "r",\n'
                '  "ref": "v1",\n'
                '  "metadata": {"OPERATOR_NAME": "Esteban", "ORG_NAME": "YouBR"}\n'
                '}\n',
                encoding="utf-8",
            )

            self.assertEqual(ia._state_metadata(ia._read_state(root)), {"ORG_NAME": "YouBR"})

    def test_operator_metadata_is_not_shared_in_manifest_after_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ia._STATE_DIR).mkdir()
            (root / ia._STATE_FILE).write_text(
                '{\n'
                '  "state_version": 1,\n'
                '  "repo": "r",\n'
                '  "ref": "v1",\n'
                '  "metadata": {"OPERATOR_NAME": "Esteban", "ORG_NAME": "YouBR"}\n'
                '}\n',
                encoding="utf-8",
            )

            ia._write_state(root, [], repo="r", ref="v2", metadata={})

            manifest = ia._read_json(root / ia._STATE_FILE)
            self.assertEqual(manifest["metadata"], {"ORG_NAME": "YouBR"})
            self.assertFalse((root / ia._OPERATOR_FILE).exists())

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
        # Secrets and rule files stay ignored regardless — but `.credentials` is
        # covered by the secret patterns as `.credentials/*` plus re-includes, never
        # as a bare directory. Git does not descend into an excluded directory, so a
        # bare entry would make the scaffolding the kit seeds there permanently
        # untrackable, which is the opposite of what the patterns were written for.
        self.assertNotIn(".credentials", entries)
        self.assertIn(".credentials/*", entries)
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
            self.assertTrue((root / ".docs" / "issues" / "README.md").is_file())
            # Project docs promoted to docs/
            self.assertTrue((root / "docs" / "mydoc.md").is_file())
            self.assertFalse((root / "docs" / "project").exists())
            # Project-owned files stay in docs/ — including the readiness files, whose
            # content and flags the project owns even though the kit ships a template.
            self.assertTrue((root / "docs" / "required-reading.md").is_file())
            self.assertTrue((root / "docs" / "software-overview.md").is_file())
            self.assertFalse((root / ".docs" / "software-overview.md").exists())
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

    def test_content_migration_extracts_only_project_or_changed_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            backup = root / ia._MIGRATION_BACKUP_DIR / "agents"
            backup.mkdir(parents=True)
            (backup / "programmer.md").write_text("project delta\n", encoding="utf-8")
            (backup / "build-deploy.md").write_text("project-only\n", encoding="utf-8")
            (root / ".docs" / "agents").mkdir(parents=True)
            (root / ".docs" / "agents" / "programmer.md").write_text("kit\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "required-reading.md").write_text("- (none)\n", encoding="utf-8")

            migrated, notes = ia._migrate_legacy_content(root)

            self.assertTrue(migrated, notes)
            content = (root / "docs" / "project-rules" / "legacy-agent-contracts.md").read_text()
            self.assertIn("programmer.md", content)
            self.assertIn("build-deploy.md", content)
            index = (root / "docs" / "required-reading.md").read_text()
            self.assertNotIn("(none)", index)
            self.assertIn("docs/project-rules.md", index)

    def test_upgrade_refuses_orphaned_content_without_explicit_migration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ia._MIGRATION_BACKUP_DIR / "agents").mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError, "migrate-content"):
                ia.run_install_agents(root, upgrade=True)

    def test_upgrade_refuses_symlinked_managed_directory(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir, tempfile.TemporaryDirectory() as outside_dir:
            src, dst, outside = Path(source_dir), Path(target_dir), Path(outside_dir)
            _make_source(src)
            (dst / ".docs").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(UnsafePathError):
                ia._do_upgrade(src, dst, paths=["docs/agents"])

            self.assertFalse((outside / "agents").exists())

    def test_fill_placeholders_ignores_doc_example_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            doc = root / "AGENTS.md"
            doc.write_text(
                "Replace [PLACEHOLDER] and [TOKEN] examples. Owner: {{OPERATOR_NAME}}.\n",
                encoding="utf-8",
            )
            ia._fill_placeholders(root, ["AGENTS.md"])
            text = doc.read_text(encoding="utf-8")
            self.assertIn("[PLACEHOLDER]", text)
            self.assertIn("[TOKEN]", text)
            self.assertIn("{{OPERATOR_NAME}}", text)

    def test_fill_placeholders_only_supports_canonical_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            doc = root / "AGENTS.md"
            doc.write_text(
                "policy [OPERATOR_NAME] current {{ORG_NAME}}\n",
                encoding="utf-8",
            )

            values = ia._fill_placeholders(
                root,
                ["AGENTS.md"],
                known={"OPERATOR_NAME": "Esteban", "ORG_NAME": "Acme"},
            )

            self.assertEqual(
                doc.read_text(encoding="utf-8"),
                "policy [OPERATOR_NAME] current Acme\n",
            )
            self.assertEqual(values["OPERATOR_NAME"], "Esteban")
            self.assertEqual(values["ORG_NAME"], "Acme")


class SendingEmailRetirementTests(unittest.TestCase):
    """AI-Agents#5 and its council rounds, on the Python installer's side."""

    def test_the_reading_index_is_seeded_from_a_template_not_from_the_kit(self) -> None:
        # The kit's own index declares the kit's email transport and local sources.
        # Copying it into a new project made that project assert one operator's helper
        # as its own transport, in the exact table the email contract tells the agent
        # to trust — the cross-project carryover AI-Agents#5 exists to forbid.
        with tempfile.TemporaryDirectory() as temp_dir:
            src = Path(temp_dir) / "src"
            (src / "docs").mkdir(parents=True)
            (src / "templates").mkdir()
            (src / "docs" / "required-reading.md").write_text(
                "| `~/.config/email/send.py` | opcional | o transporte DAQUI |\n",
                encoding="utf-8",
            )
            (src / "templates" / "required-reading.template.md").write_text(
                "# Required Reading\n\n## Fontes locais\n", encoding="utf-8",
            )

            resolved = ia._resolve_src(src, "docs/required-reading.md")

            self.assertEqual(resolved, src / "templates" / "required-reading.template.md")
            self.assertNotIn("send.py", resolved.read_text(encoding="utf-8"))

    def test_templates_is_never_a_managed_path_at_the_project_root(self) -> None:
        # It was, for one commit, so the shipped shell installer could find its
        # starters. The council reproduced the cost: `templates` is the commonest
        # top-level directory name in web projects and every kit path here is
        # unprefixed, so the entry gitignored the project's templates at any depth,
        # rmtree'd them on `--force`, and — via the manifest — DELETED them on the
        # second upgrade. Reinstating it needs a namespaced destination.
        self.assertNotIn("templates", ia._FRESH_PATHS)
        self.assertNotIn("templates", ia._UPGRADE_PATHS)

    def test_a_project_owning_a_templates_directory_keeps_it(self) -> None:
        # The behavioural half: the assertions above pin the lists, this pins what the
        # lists cause. A bare `templates` entry reaches .gitignore as an unanchored
        # pattern, which is how the files became invisible before they were deleted.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ia._update_gitignore(root / ".gitignore", ia._FRESH_PATHS, track_kit_docs=False)

            written = (root / ".gitignore").read_text(encoding="utf-8").splitlines()

            self.assertNotIn("templates", [line.strip() for line in written])

    def test_smtp_account_is_no_longer_collected_but_stays_operator_local(self) -> None:
        # Not fillable: the canonical contract names no transport, so an install cannot
        # know whether the project sends email, let alone through SMTP.
        self.assertNotIn("SMTP_ACCOUNT", ia._PLACEHOLDER_DESCRIPTIONS)
        # Still classified: an install predating the retirement holds the operator's
        # address in .gk/operator.json, and this set is what keeps it out of the
        # COMMITTED manifest. Dropping it would publish a legacy value on next upgrade.
        self.assertIn("SMTP_ACCOUNT", ia._OPERATOR_PLACEHOLDERS)

    def test_a_retired_token_is_still_filled_from_a_stored_value(self) -> None:
        # A legacy target upgraded at a ref whose files still carry the token would
        # otherwise dead-end: the slot stays raw, `doctor` fails NON-advisory with "kit
        # not configured", and `configure` cannot fix it because its known-token set is
        # built from the same dict the retirement emptied. Retired means "never asked",
        # not "never applied".
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            doc = root / "AGENTS.md"
            doc.write_text("contato: {{SMTP_ACCOUNT}}\n", encoding="utf-8")

            values = ia._fill_placeholders(
                root, ["AGENTS.md"], known={"SMTP_ACCOUNT": "legacy@example.invalid"},
            )

            self.assertEqual(
                doc.read_text(encoding="utf-8"), "contato: legacy@example.invalid\n",
            )
            self.assertEqual(values.get("SMTP_ACCOUNT"), "legacy@example.invalid")
            self.assertIn("SMTP_ACCOUNT", ia._RETIRED_PLACEHOLDERS)
            # And it stays on the side that never reaches a committed file.
            self.assertIn("SMTP_ACCOUNT", ia._OPERATOR_PLACEHOLDERS)

    def test_a_retired_token_with_no_stored_value_is_not_reported_as_unknown(self) -> None:
        # Reporting it would send the operator to `configure`, which cannot fill it.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "AGENTS.md").write_text("contato: {{SMTP_ACCOUNT}}\n", encoding="utf-8")

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                ia._fill_placeholders(root, ["AGENTS.md"], known={})

            self.assertNotIn("SMTP_ACCOUNT", buffer.getvalue())

    def test_a_retired_token_with_no_stored_value_is_still_fixable(self) -> None:
        # The dead end the retirement created and the first fix missed: with no stored
        # value, doctor fails NON-advisory naming `configure`, and configure could not
        # fill a token it no longer knew. The check failed forever and its own remedy
        # did nothing — worse than before the retirement, when configure worked.
        from governancekit.configure import run_configure
        from governancekit.doctor import _check_unfilled_placeholders

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "AGENTS.md").write_text("contato: {{SMTP_ACCOUNT}}\n", encoding="utf-8")

            self.assertFalse(_check_unfilled_placeholders(root).passed)

            run_configure(root, preset={"SMTP_ACCOUNT": "ops@example.invalid"},
                          interactive=False)

            self.assertEqual(
                (root / "AGENTS.md").read_text(encoding="utf-8"),
                "contato: ops@example.invalid\n",
            )
            self.assertTrue(_check_unfilled_placeholders(root).passed)

    def test_a_retired_token_is_absent_from_the_unfilled_report(self) -> None:
        # The guard reached `unknown` and the prompt loop but not the final report, so
        # a run that filled anything else still named the retired slot.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "AGENTS.md").write_text(
                "org {{ORG_NAME}} contato {{SMTP_ACCOUNT}}\n", encoding="utf-8",
            )

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                ia._fill_placeholders(root, ["AGENTS.md"], known={"ORG_NAME": "Acme"})

            self.assertIn("Placeholders filled in", buffer.getvalue())
            self.assertNotIn("SMTP_ACCOUNT", buffer.getvalue())

    def test_the_pinned_ref_has_a_verified_checksum(self) -> None:
        # The chain that delivers any of this to a user has four links, and two live in
        # another repository: source -> tag -> (DEFAULT_REF + checksum here) -> upgrade.
        # A DEFAULT_REF with no checksum entry downloads unverified or refuses; a
        # DEFAULT_REF left behind delivers the OLD kit while the fix sits unreleased,
        # which is how the withdrawn contract kept reinstalling itself. Council r2 of
        # GK#7 (R2-6/R2-14).
        self.assertIn((ia.REPO, ia.DEFAULT_REF), ia.KNOWN_TARBALL_SHA256)
        digest = ia.KNOWN_TARBALL_SHA256[(ia.REPO, ia.DEFAULT_REF)]
        self.assertRegex(digest, r"^[0-9a-f]{64}$")


class CouncilRoundOneTest(unittest.TestCase):
    """The findings four adversarial lenses reproduced against the first cut.

    Each of these went red before its fix. They are grouped because they share one
    root: the decision table was ported from the shell installer without the ordering
    and the bookkeeping that make it safe.
    """

    def test_a_configured_file_reads_as_identical_to_the_kit_not_as_drift(self) -> None:
        # THE root cause. The target holds `Esteban` where the download still holds
        # `{{OPERATOR_NAME}}`, so the byte-identity short-circuit could never fire for
        # the one file the protection is about. Reproduced three ways by the council:
        # a target whose manifest entry was lost became permanently drifted and never
        # received another AGENTS.md; `configure` (which rewrites the file and does not
        # update the manifest) froze it the same way; and the `.kit-new` handed over
        # for merging carried raw placeholders, so following the instruction turned
        # `doctor` red.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            (src / "AGENTS.md").write_text("# kit {{OPERATOR_NAME}}\n", encoding="utf-8")
            (dst / "AGENTS.md").write_text("# kit Esteban\n", encoding="utf-8")

            ia._prerender_source(src, {"OPERATOR_NAME": "Esteban"})
            drifted: list[str] = []
            # No manifest at all: the pre-`.gk` population, which fails closed.
            installed = ia._do_upgrade(
                src, dst, paths=["AGENTS.md"], manifest={}, drifted=drifted
            )

            self.assertEqual(drifted, [], "the kit's own substitution is not drift")
            self.assertEqual(installed, ["AGENTS.md"])
            self.assertFalse((dst / "AGENTS.md.kit-new").exists())

    def test_the_kit_new_handed_over_for_merging_is_rendered(self) -> None:
        # The operator is told to merge this file. If it carries raw placeholders,
        # following the instruction fails the non-advisory `unfilled placeholders`
        # check, whose remedy is `configure`, which re-creates the drift.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            (src / "AGENTS.md").write_text(
                "# kit v2 {{OPERATOR_NAME}}\n", encoding="utf-8"
            )
            (dst / "AGENTS.md").write_text("# our rules\n", encoding="utf-8")

            ia._prerender_source(src, {"OPERATOR_NAME": "Esteban"})
            ia._do_upgrade(src, dst, paths=["AGENTS.md"], manifest={}, drifted=[])

            self.assertEqual((dst / "AGENTS.md.kit-new").read_text(), "# kit v2 Esteban\n")

    def test_a_real_upgrade_run_renders_the_source_before_judging_it(self) -> None:
        # The lesson the claim auditor taught one level up: a function proven in
        # isolation is not a function that runs. Removing the call from
        # `run_install_agents` left every unit test above green, so this one goes
        # through the real entry point with only the download replaced.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            (src / "AGENTS.md").write_text("# kit {{OPERATOR_NAME}}\n", encoding="utf-8")
            (dst / "AGENTS.md").write_text("# kit Esteban\n", encoding="utf-8")
            # The population that has the answer stored but no manifest entry for the
            # file — a pre-`.gk` install, or a shell install whose manifest pass bailed.
            (dst / ia._STATE_DIR).mkdir(parents=True, exist_ok=True)
            (dst / ia._OPERATOR_FILE).write_text(
                '{"state_version": 1, "metadata": {"OPERATOR_NAME": "Esteban"}}',
                encoding="utf-8",
            )

            with unittest.mock.patch.object(ia, "_download", return_value=src):
                with contextlib.redirect_stdout(io.StringIO()):
                    result = ia.run_install_agents(dst, upgrade=True, track=False)

            self.assertEqual(result.drifted_paths, [], "the kit's own substitution is not drift")
            self.assertGreater(result.substitutions_prerendered, 0)
            self.assertFalse((dst / "AGENTS.md.kit-new").exists())

    def test_prerendering_never_rewrites_a_binary(self) -> None:
        # `.docs/icons` ships binaries. The shell's pass skips what it cannot decode;
        # a port that read bytes and wrote text back would corrupt them silently.
        with tempfile.TemporaryDirectory() as s:
            src = Path(s)
            icon = src / "icon.png"
            icon.write_bytes(b"\x89PNG\r\n\x1a\n{{OPERATOR_NAME}}\xff\xfe")

            ia._prerender_source(src, {"OPERATOR_NAME": "Esteban"})

            self.assertEqual(icon.read_bytes(), b"\x89PNG\r\n\x1a\n{{OPERATOR_NAME}}\xff\xfe")

    def test_a_preserved_project_file_survives_a_SECOND_upgrade(self) -> None:
        # Upgrade #1 preserves a project file inside a kit directory and says so;
        # `_write_state` then rglobbed it into the TRACKED manifest as kit-owned, and
        # upgrade #2 deleted it in silence at confidence 1.0. The report said "kept"
        # and the next run destroyed it.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            ours = dst / ".docs" / "agents" / "our-reviewer.md"
            ours.parent.mkdir(parents=True)
            ours.write_text("PROJECT RULE\n", encoding="utf-8")

            for _ in range(2):
                preserved: list[str] = []
                installed = ia._do_upgrade(
                    src, dst, paths=ia._KIT_DOC_PATHS,
                    manifest=ia._state_files(ia._read_state(dst)), preserved=preserved,
                )
                ia._write_state(
                    dst, installed, repo="r", ref="v1", metadata={},
                    prune_missing=True, preserved=preserved,
                )
                self.assertIn(".docs/agents/our-reviewer.md", preserved)

            self.assertTrue(ours.is_file(), "upgrade #2 deleted what upgrade #1 kept")
            self.assertNotIn(
                ".docs/agents/our-reviewer.md",
                ia._state_files(ia._read_state(dst)),
                "a file the kit did not write must not be claimed by the manifest",
            )

    def test_the_pre_upgrade_backup_holds_the_state_before_THIS_upgrade(self) -> None:
        # Accumulating runs make the name mean nothing in particular: a file backed up
        # by an earlier upgrade and not touched by this one would still sit there, and
        # the operator restoring it would roll back a version they never asked to lose.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            for rel in ("CLAUDE.md", "GEMINI.md"):
                (src / rel).write_text("kit v2\n", encoding="utf-8")
                (dst / rel).write_text("kit v1\n", encoding="utf-8")
            manifest = {rel: ia._file_sha256(dst / rel) for rel in ("CLAUDE.md", "GEMINI.md")}

            first: list[str] = []
            ia._do_upgrade(
                src, dst, paths=["CLAUDE.md", "GEMINI.md"], manifest=manifest,
                backed_up=first,
            )
            self.assertEqual(sorted(first), ["CLAUDE.md", "GEMINI.md"])

            # A narrower second run: it replaces CLAUDE.md and never looks at GEMINI.md.
            (src / "CLAUDE.md").write_text("kit v3\n", encoding="utf-8")
            second: list[str] = []
            ia._do_upgrade(
                src, dst, paths=["CLAUDE.md"],
                manifest={"CLAUDE.md": ia._file_sha256(dst / "CLAUDE.md")},
                backed_up=second,
            )

            backups = dst / ia._STATE_DIR / "pre-upgrade"
            self.assertEqual((backups / "CLAUDE.md").read_text(), "kit v2\n")
            self.assertFalse(
                (backups / "GEMINI.md").exists(),
                "a backup from an earlier run makes `pre-upgrade` mean nothing",
            )
            self.assertEqual(second, ["CLAUDE.md"])

    def test_the_state_gitignore_covers_what_the_other_installer_writes(self) -> None:
        # `.gk/.gitignore` is rewritten wholesale on every run, so anything the shell
        # ignores and this one omits gets un-ignored on the first Python upgrade of a
        # shell-installed target. `.gk/pre-migrate/` holds that target's root
        # contracts as they stood before migration — the hand-edited AGENTS.md itself.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ia._write_state(root, [], repo="r", ref="v1", metadata={})
            ignored = (root / ia._STATE_DIR / ".gitignore").read_text()
            for entry in ("overwritten/", "pre-upgrade/", "pre-migrate/", "council/"):
                self.assertIn(entry, ignored)


class ProjectOwnedPathsTest(unittest.TestCase):
    """Two families the installer seeds and must never claim back.

    `.credentials/` holds the programmer's identity, their tokens and the LLM keys the
    interview writes. The two readiness documents are what the project says about
    itself. Both were ordinary conflicts: answering `y` — or `--force`, which never
    asks — ran `shutil.rmtree` over them. The shell installer has guarded both for
    months; this is the Python side converging on it.
    """

    def _source(self, src: Path) -> None:
        _make_source(src)
        creds = src / ".credentials"
        creds.mkdir()
        (creds / "README.md").write_text("how to put tokens here\n", encoding="utf-8")
        (creds / "identity.json.example").write_text("{}\n", encoding="utf-8")

    def test_force_never_deletes_an_existing_credentials_directory(self) -> None:
        # The data-loss test. `--force` skips the prompt entirely, so this path had no
        # human in it at all.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            self._source(src)
            creds = dst / ".credentials"
            (creds / "llm").mkdir(parents=True)
            (creds / "identity.json").write_text('{"operator_name": "Esteban"}\n', encoding="utf-8")
            (creds / "llm" / "openai.key").write_text("sk-real-key\n", encoding="utf-8")

            seeded: list[str] = []
            preserved: list[str] = []
            ia._do_fresh(src, dst, force=True, seeded=seeded, preserved=preserved)

            self.assertEqual(
                (creds / "identity.json").read_text(), '{"operator_name": "Esteban"}\n'
            )
            self.assertEqual((creds / "llm" / "openai.key").read_text(), "sk-real-key\n")
            self.assertIn(".credentials/README.md", seeded)
            self.assertIn(".credentials/identity.json", preserved)

    def test_credentials_are_never_recorded_in_the_tracked_manifest(self) -> None:
        # `.gk/manifest.json` is tracked on purpose. A SHA-256 of a low-entropy token
        # is a confirmation oracle, and the paths alone say which providers a
        # programmer holds keys for. This only stayed safe while the directory was
        # being deleted first.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            self._source(src)
            (dst / ".credentials").mkdir()
            (dst / ".credentials" / "identity.json").write_text("{}\n", encoding="utf-8")

            installed = ia._do_fresh(src, dst, force=True, seeded=[], preserved=[])
            ia._write_state(dst, installed, repo="r", ref="v1", metadata={})

            recorded = ia._state_files(ia._read_state(dst))
            self.assertFalse(
                [rel for rel in recorded if rel.startswith(".credentials")],
                f"the tracked manifest names credential files: {sorted(recorded)}",
            )

    def test_a_legacy_manifest_loses_its_credential_entries_on_the_next_run(self) -> None:
        # The fleet migration: projects installed before today already carry these
        # entries in a committed file.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".gk").mkdir()
            (root / ".gk" / "manifest.json").write_text(
                '{"files": {".credentials/identity.json": "abc", "AGENTS.md": "def"}}',
                encoding="utf-8",
            )
            (root / "AGENTS.md").write_text("# kit\n", encoding="utf-8")

            ia._write_state(root, [], repo="r", ref="v1", metadata={})

            recorded = ia._state_files(ia._read_state(root))
            self.assertNotIn(".credentials/identity.json", recorded)
            self.assertIn("AGENTS.md", recorded)

    def test_force_does_not_replace_an_authored_readiness_document(self) -> None:
        # `--force` is documented as "overwrite existing KIT files". These are the
        # project's, and the shell installer has never overwritten them.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            self._source(src)
            docs = dst / "docs"
            docs.mkdir()
            (docs / "software-overview.md").write_text(
                "# Ours\n\n- project_context_ready: yes\n\nWe bill churches monthly.\n",
                encoding="utf-8",
            )

            preserved: list[str] = []
            ia._do_fresh(src, dst, force=True, seeded=[], preserved=preserved)

            text = (docs / "software-overview.md").read_text()
            self.assertIn("We bill churches monthly.", text)
            self.assertIn("docs/software-overview.md", preserved)
            # And the operator's answer survives with it. The reset lowers only what
            # this run seeded: demoting a preserved document shuts the Start Gate over
            # content nobody touched, in the same run that reports the file as "kept".
            # The first cut of this test asserted the demotion as correct.
            self.assertIn("- project_context_ready: yes", text)

    def test_the_readiness_reset_lowers_the_LINE_and_not_prose_that_quotes_it(self) -> None:
        # The reset is the third reader/writer of these flags, and the last one still
        # matching a bare substring. A document that quotes the metadata line inside a
        # sentence — the natural way to explain the flag to whoever must set it — had
        # its sentence rewritten too, turning an instruction into its own opposite.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "limits.md").write_text(
                "# Limits\n\n- limits_ready: yes\n\n"
                "Write - limits_ready: yes in the metadata block once these are accurate.\n",
                encoding="utf-8",
            )

            ia._reset_readiness_flags(root)

            text = (root / "docs" / "limits.md").read_text()
            self.assertIn("- limits_ready: no\n", text)
            self.assertIn(
                "Write - limits_ready: yes in the metadata block", text,
                "the reset rewrote the sentence that explains the flag",
            )


class CouncilRoundTwoTest(unittest.TestCase):
    """What round 2 found in round 1's fixes. Three of the five were regressions the
    fixes themselves introduced, which is the argument for the second round."""

    def test_a_stored_value_cannot_smuggle_another_token_into_the_render(self) -> None:
        # `.gk/manifest.json` is the half a team SHARES and commits. A value that is
        # itself a token used to be expanded by the next sequential pass, so a
        # shareable answer could pull a local secret into a kit file — and, under
        # --track, into git.
        #
        # This test's expectation CHANGED with AC-1, and the reason matters. It used to
        # assert the injected token was written out literally — which is what a single
        # regex sweep does, and it was believed to be enough. It is not: the literal
        # token is then real text in the file, and the NEXT stage fills it. Measured,
        # with a single sweep on both stages: 'Owner: STORED-SECRET-DO-NOT-COMMIT'. The
        # value is now refused at the gate, so nothing is written at all.
        with tempfile.TemporaryDirectory() as s:
            src = Path(s)
            (src / "doc.md").write_text("owner: {{ORG_NAME}}\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                ia._prerender_source(
                    src, {"ORG_NAME": "{{SMTP_ACCOUNT}}", "SMTP_ACCOUNT": "SECRET"}
                )

            self.assertEqual((src / "doc.md").read_text(), "owner: {{ORG_NAME}}\n")
            self.assertNotIn("SECRET", (src / "doc.md").read_text())

    def test_only_declared_placeholders_are_rendered(self) -> None:
        # Without the filter the kit did not even need to ship the token: injected
        # text supplied it. `_fill_placeholders` has always filtered this way.
        with tempfile.TemporaryDirectory() as s:
            src = Path(s)
            (src / "doc.md").write_text("{{MADE_UP_TOKEN}}\n", encoding="utf-8")

            count = ia._prerender_source(src, {"MADE_UP_TOKEN": "anything"})

            self.assertEqual(count, 0)
            self.assertEqual((src / "doc.md").read_text(), "{{MADE_UP_TOKEN}}\n")

    def test_an_absurdly_long_stored_value_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as s:
            src = Path(s)
            (src / "doc.md").write_text("{{OPERATOR_NAME}}\n", encoding="utf-8")

            count = ia._prerender_source(
                src, {"OPERATOR_NAME": "x" * (ia._MAX_PLACEHOLDER_VALUE + 1)}
            )

            self.assertEqual(count, 0)

    def test_the_parked_copy_is_ignored_by_git(self) -> None:
        # It is rendered — that is what makes it mergeable — so it carries the
        # operator's name, the value the tracked state deliberately never holds.
        # `AGENTS.md` was ignored and its `.kit-new` sibling was not.
        entries = ia._gitignore_entries(ia._FRESH_PATHS, track_kit_docs=False)
        self.assertIn("*.kit-new", entries)

    def test_docs_only_does_not_destroy_the_backups_of_a_full_upgrade(self) -> None:
        # A narrower run must not clear the wider run's insurance: `--docs-only` never
        # touches the root contracts whose only copy that directory holds.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            (src / "CLAUDE.md").write_text("kit v2\n", encoding="utf-8")
            (dst / "CLAUDE.md").write_text("kit v1\n", encoding="utf-8")

            ia._do_upgrade(
                src, dst, paths=["CLAUDE.md"],
                manifest={"CLAUDE.md": ia._file_sha256(dst / "CLAUDE.md")},
                backed_up=[],
            )
            ia._do_upgrade(
                src, dst, paths=ia._KIT_DOC_PATHS, manifest={}, preserved=[],
                clear_backups=False,
            )

            self.assertTrue((dst / ia._STATE_DIR / "pre-upgrade" / "CLAUDE.md").is_file())

    def test_the_kits_own_substitution_is_not_reported_as_a_hand_edit(self) -> None:
        # `configure` fills a slot inside a kit directory; the manifest hash goes
        # stale. `_sync_dir` judged by hash alone, so the next upgrade announced it had
        # replaced a file "you had edited by hand", stashed a byte-identical copy, and
        # told the operator to move their project rules out of kit files. The edit was
        # the kit's own. `_replace_kit_file` already short-circuited on identity.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            target = dst / ".docs" / "agents" / "programmer.md"
            target.parent.mkdir(parents=True)
            target.write_text("v2\n", encoding="utf-8")  # identical to the source

            overwritten: list[str] = []
            ia._do_upgrade(
                src, dst, paths=ia._KIT_DOC_PATHS,
                manifest={".docs/agents/programmer.md": "a-stale-hash"},
                preserved=[], overwritten=overwritten,
            )

            self.assertEqual(overwritten, [])
            self.assertFalse(
                (dst / ia._STATE_DIR / "overwritten" / ".docs/agents/programmer.md").exists()
            )


class UpgradeReplacesFilesTest(unittest.TestCase):
    """R2-16': the file branch of `_do_upgrade` was a bare `shutil.copy2`.

    The directory branch has judged every file against the manifest since the day
    `_sync_dir` replaced an `rmtree`, and the shell installer judges single files
    too. Between them sat every root file — `AGENTS.md` first among them, which is
    the file every agent is told to read and therefore the first place anyone
    writes a project rule.
    """

    def _target(self, dst: Path) -> Path:
        return dst / "AGENTS.md"

    def test_a_protected_file_the_project_edited_survives_the_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            agents = self._target(dst)
            agents.write_text("# kit AGENTS\n\n## Project rules\n\nreviewer: ana\n", encoding="utf-8")
            manifest = {"AGENTS.md": ia._file_sha256(Path(__file__))}

            drifted: list[str] = []
            installed = ia._do_upgrade(
                src, dst, paths=["AGENTS.md"], manifest=manifest, drifted=drifted
            )

            self.assertIn("reviewer: ana", agents.read_text())
            self.assertEqual(drifted, ["AGENTS.md"])
            self.assertIn("# kit AGENTS", (dst / "AGENTS.md.kit-new").read_text())
            # Not "installed": the manifest must not learn a hash for a file the kit
            # did not write, or the NEXT upgrade reads it as untouched kit content.
            self.assertEqual(installed, [])

    def test_a_drifted_protected_file_survives_a_SECOND_upgrade(self) -> None:
        # The manifest poison only shows on the second cycle, which is why the first
        # one is not enough to call this closed. If the first upgrade recorded the
        # project's version as kit content, the second one reads "hash matches,
        # untouched kit file" and replaces it — the protection would hold exactly once.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            agents = self._target(dst)
            shutil.copy2(src / "AGENTS.md", agents)
            ia._write_state(dst, ["AGENTS.md"], repo="r", ref="v1", metadata={})
            agents.write_text("# kit AGENTS\n\nreviewer: ana\n", encoding="utf-8")

            for _ in range(2):
                drifted: list[str] = []
                installed = ia._do_upgrade(
                    src, dst, paths=["AGENTS.md"],
                    manifest=ia._state_files(ia._read_state(dst)), drifted=drifted,
                )
                ia._write_state(
                    dst, installed, repo="r", ref="v2", metadata={}, prune_missing=True
                )
                self.assertEqual(drifted, ["AGENTS.md"])

            self.assertIn("reviewer: ana", agents.read_text())

    def test_a_protected_file_of_unknown_provenance_fails_closed(self) -> None:
        # No manifest entry at all — a pre-.gk install. Those are precisely the ones
        # most likely to hold hand-written rules, so the unknown case keeps the file.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            agents = self._target(dst)
            agents.write_text("PROJECT CONTRACT\n", encoding="utf-8")

            drifted: list[str] = []
            ia._do_upgrade(src, dst, paths=["AGENTS.md"], manifest={}, drifted=drifted)

            self.assertEqual(agents.read_text(), "PROJECT CONTRACT\n")
            self.assertEqual(drifted, ["AGENTS.md"])

    def test_a_protected_file_identical_to_the_kit_is_not_drift(self) -> None:
        # The migration case: the file already IS the kit's version while the manifest
        # still holds a pre-migration hash. Judging by the manifest alone would demand
        # a merge of a file against itself, and leave a .kit-new nobody needs.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            agents = self._target(dst)
            shutil.copy2(src / "AGENTS.md", agents)
            stale = dst / "AGENTS.md.kit-new"
            stale.write_text("from an earlier run\n", encoding="utf-8")

            drifted: list[str] = []
            installed = ia._do_upgrade(
                src, dst,
                paths=["AGENTS.md"],
                manifest={"AGENTS.md": ia._file_sha256(Path(__file__))},
                drifted=drifted,
            )

            self.assertEqual(drifted, [])
            self.assertFalse(stale.exists(), "a .kit-new is stale once the two match")
            self.assertEqual(installed, ["AGENTS.md"])

    def test_an_edited_root_file_that_is_not_protected_is_stashed_then_replaced(self) -> None:
        # Kit-owned for writing: the new version wins, but the edit is real intent and
        # must be recoverable rather than destroyed.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            (src / "CLAUDE.md").write_text("kit v2\n", encoding="utf-8")
            edited = dst / "CLAUDE.md"
            edited.write_text("EDITED BY PROJECT\n", encoding="utf-8")
            manifest = {"CLAUDE.md": ia._file_sha256(Path(__file__))}

            overwritten: list[str] = []
            drifted: list[str] = []
            ia._do_upgrade(
                src, dst, paths=["CLAUDE.md"], manifest=manifest,
                overwritten=overwritten, drifted=drifted,
            )

            self.assertEqual(edited.read_text(), "kit v2\n")
            self.assertEqual(overwritten, ["CLAUDE.md"])
            self.assertEqual(drifted, [])
            stash = dst / ia._STATE_DIR / "overwritten" / "CLAUDE.md"
            self.assertEqual(stash.read_text(), "EDITED BY PROJECT\n")

    def test_every_replaced_root_file_leaves_a_pre_upgrade_copy(self) -> None:
        # Insurance independent of the judgement above: even a file the manifest calls
        # untouched keeps a copy, so a wrong call costs one `cp` to undo.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            (src / "CLAUDE.md").write_text("kit v2\n", encoding="utf-8")
            pristine = dst / "CLAUDE.md"
            pristine.write_text("kit v1\n", encoding="utf-8")
            manifest = {"CLAUDE.md": ia._file_sha256(pristine)}

            overwritten: list[str] = []
            ia._do_upgrade(
                src, dst, paths=["CLAUDE.md"], manifest=manifest, overwritten=overwritten
            )

            self.assertEqual(pristine.read_text(), "kit v2\n")
            self.assertEqual(overwritten, [], "an untouched kit file is replaced silently")
            backup = dst / ia._STATE_DIR / "pre-upgrade" / "CLAUDE.md"
            self.assertEqual(backup.read_text(), "kit v1\n")

    def test_the_backup_directories_are_ignored_by_the_state_gitignore(self) -> None:
        # A backup that reaches git is not a backup, it is a commit of the file the
        # operator was trying to keep private, plus noise on every upgrade.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ia._write_state(root, [], repo="r", ref="v1", metadata={})
            ignored = (root / ia._STATE_DIR / ".gitignore").read_text()
            self.assertIn("overwritten/", ignored)
            self.assertIn("pre-upgrade/", ignored)


if __name__ == "__main__":
    unittest.main()


class CouncilRoundOnAdoptionTest(unittest.TestCase):
    """What the four lenses found in the adoption/credentials delivery."""

    def test_a_file_where_the_kit_ships_a_directory_does_not_crash_the_install(self) -> None:
        # The seed-only branch jumps over the `unlink()` the old code reached, so the
        # mismatched-type case had no handler at all and `_do_fresh` raised
        # FileExistsError. Nothing here may replace the file — that path is the
        # project's — but killing the run over it helps nobody.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            (src / ".credentials").mkdir()
            (src / ".credentials" / "README.md").write_text("docs\n", encoding="utf-8")
            (dst / ".credentials").write_text("i am a file, not a directory\n", encoding="utf-8")

            preserved: list[str] = []
            ia._do_fresh(src, dst, force=True, seeded=[], preserved=preserved)

            self.assertEqual(
                (dst / ".credentials").read_text(), "i am a file, not a directory\n"
            )
            self.assertIn(".credentials", preserved)

    def test_a_confirmed_readiness_flag_survives_a_fresh_run(self) -> None:
        # The reset lowers what this run SEEDED. A preserved document keeps the answer
        # the operator gave — the alternative shuts the Start Gate over content nobody
        # touched, in the same run whose report calls the file "kept".
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            docs = dst / "docs"
            docs.mkdir()
            for rel, marker in (("software-overview.md", "project_context_ready"),
                                ("limits.md", "limits_ready")):
                (docs / rel).write_text(
                    f"# Ours\n\n- {marker}: yes\n\nSix lines of real project prose.\n"
                    "Second line.\nThird line.\nFourth line.\nFifth line.\nSixth line.\n",
                    encoding="utf-8",
                )

            ia._do_fresh(src, dst, force=True, seeded=[], preserved=[])

            self.assertIn("- project_context_ready: yes", (docs / "software-overview.md").read_text())
            self.assertIn("- limits_ready: yes", (docs / "limits.md").read_text())

    def test_a_freshly_seeded_document_is_still_lowered(self) -> None:
        # The guard must not cost the reset its job: a document this run installed from
        # the kit arrives saying `yes` and must not open the Start Gate.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, dst = Path(s), Path(d)
            _make_source(src)
            (src / "docs" / "software-overview.md").write_text(
                "# Kit\n\n- project_context_ready: yes\n", encoding="utf-8"
            )

            ia._do_fresh(src, dst, force=True, seeded=[], preserved=[])

            self.assertIn(
                "- project_context_ready: no",
                (dst / "docs" / "software-overview.md").read_text(),
            )


class RenderGateTest(unittest.TestCase):
    """AC-1 — the render gate every writer shares.

    Round 2 hardened `_prerender_source` and left `_fill_placeholders` and
    `configure.run_configure` with their own sequential `str.replace`. The audit of
    that closure found the hardening had stopped in the middle of the pipeline, and
    then found something worse: the property round 2 chose does not close the chain
    on its own. Both facts are tested here.
    """

    def test_the_two_stage_chain_cannot_carry_a_local_secret_into_a_kit_file(self) -> None:
        # THE test for AC-1, and the one that would have caught the original gap.
        # It exercises the pipeline as `run_install_agents` orders it: render the
        # downloaded source, copy, then fill the installed target. Stage 1 alone is
        # not the mechanism; the pair is.
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, root = Path(s), Path(d)
            (src / "donations.md").write_text("Owner: {{ORG_NAME}}\n", encoding="utf-8")
            # ORG_NAME lives in the SHARED half of the state (a teammate, or a merged
            # pull request, can set it). PROJECT_SLUG is the victim's LOCAL secret.
            poisoned = {
                "ORG_NAME": "{{PROJECT_SLUG}}",
                "PROJECT_SLUG": "STORED-SECRET-DO-NOT-COMMIT",
            }

            with contextlib.redirect_stdout(io.StringIO()):
                ia._prerender_source(src, poisoned)
                (root / "donations.md").write_text(
                    (src / "donations.md").read_text(), encoding="utf-8"
                )
                ia._fill_placeholders(root, ["donations.md"], known=poisoned)

            self.assertNotIn("STORED-SECRET-DO-NOT-COMMIT", (root / "donations.md").read_text())

    def test_a_single_sweep_alone_would_not_have_closed_the_chain(self) -> None:
        # The measurement that corrected AC-1's own diagnosis, kept as a test so the
        # next person to "simplify" the gate back to one-pass-only sees it fail. By
        # the time stage 2 runs, the injected token is ordinary text in the file: a
        # single sweep substitutes it exactly as a sequential one would.
        table = {"PROJECT_SLUG": "STORED-SECRET-DO-NOT-COMMIT"}
        rendered, _, _ = ia._render_text("Owner: {{PROJECT_SLUG}}\n", table)

        self.assertIn("STORED-SECRET-DO-NOT-COMMIT", rendered)

    def test_a_value_carrying_placeholder_syntax_is_refused_by_name(self) -> None:
        # Refusing in silence is how this same delivery turned a traceback into an
        # empty provider list. The operator has to be told which value was dropped.
        table, refused = ia._render_table({"ORG_NAME": "{{PROJECT_SLUG}}"})

        self.assertEqual(table, {})
        self.assertEqual([t for t, _ in refused], ["ORG_NAME"])

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            ia._report_refused_values(refused)

        self.assertIn("ORG_NAME", buffer.getvalue())
        self.assertIn("placeholder syntax", buffer.getvalue())

    def test_an_oversized_value_is_refused_by_name_and_not_dropped_in_silence(self) -> None:
        table, refused = ia._render_table(
            {"OPERATOR_NAME": "x" * (ia._MAX_PLACEHOLDER_VALUE + 1)}
        )

        self.assertEqual(table, {})
        self.assertEqual([t for t, _ in refused], ["OPERATOR_NAME"])

    def test_an_undeclared_key_is_dropped_without_a_word(self) -> None:
        # Deliberately NOT a refusal: the state carries ordinary metadata, and
        # reporting all of it would bury the two refusals that matter.
        table, refused = ia._render_table({"MADE_UP_TOKEN": "anything"})

        self.assertEqual(table, {})
        self.assertEqual(refused, [])

    def test_fill_placeholders_applies_the_gate_it_used_to_skip(self) -> None:
        # The gap AC-1 opened with: this writer had neither the cap nor the syntax
        # rule. Both are asserted through the real entry point, not through the table.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "doc.md").write_text(
                "a: {{OPERATOR_NAME}} b: {{ORG_NAME}}\n", encoding="utf-8"
            )

            with contextlib.redirect_stdout(io.StringIO()):
                ia._fill_placeholders(
                    root, ["doc.md"],
                    known={
                        "OPERATOR_NAME": "x" * (ia._MAX_PLACEHOLDER_VALUE + 1),
                        "ORG_NAME": "{{PROJECT_SLUG}}",
                    },
                )

            self.assertEqual(
                (root / "doc.md").read_text(), "a: {{OPERATOR_NAME}} b: {{ORG_NAME}}\n"
            )

    def test_a_refused_value_is_reported_as_still_unfilled(self) -> None:
        # A refused token was not filled. Reporting it as filled would be a claim the
        # disk contradicts — the shape of defect this whole epic audits.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "doc.md").write_text("{{ORG_NAME}}\n", encoding="utf-8")

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                ia._fill_placeholders(
                    root, ["doc.md"], known={"ORG_NAME": "{{PROJECT_SLUG}}"}
                )

            self.assertIn("Still unfilled", buffer.getvalue())
            self.assertIn("ORG_NAME", buffer.getvalue())

    def test_a_refused_typed_value_is_not_carried_forward_into_the_state(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "doc.md").write_text("{{ORG_NAME}}\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                out = ia._fill_placeholders(
                    root, ["doc.md"], known={"ORG_NAME": "{{PROJECT_SLUG}}"}
                )

            # It stays in the state it ARRIVED in (nothing is deleted behind the
            # operator's back), and it is not adopted as a rendered value.
            self.assertEqual(out.get("ORG_NAME"), "{{PROJECT_SLUG}}")

    def test_the_sweep_is_single_pass(self) -> None:
        # Kept as its own assertion so removing the sweep is caught even though it is
        # no longer the property that closes the chain.
        rendered, count, injected = ia._render_text(
            "{{ORG_NAME}}", {"ORG_NAME": "PROJECT_SLUG", "PROJECT_SLUG": "SECRET"}
        )

        self.assertEqual(rendered, "PROJECT_SLUG")
        self.assertEqual(count, 1)
        self.assertEqual(injected, [])


class RenderFixedPointTest(unittest.TestCase):
    """The property the first two attempts at this gate did not have.

    Round 2 chose "one sweep". The audit chose "a value may not carry placeholder
    syntax". A council of four skeptics broke the second one with three variants,
    reproduced through the real pipeline — including one where the value is entirely
    innocent and the braces come from the kit's own template.
    """

    def _chain(self, template: str, state: dict[str, str]) -> str:
        """Run the real two-stage pipeline in `run_install_agents` order."""
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as d:
            src, root = Path(s), Path(d)
            (src / "doc.md").write_text(template, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                ia._prerender_source(src, state)
                (root / "doc.md").write_text((src / "doc.md").read_text(), encoding="utf-8")
                ia._fill_placeholders(root, ["doc.md"], known=state)
            return (root / "doc.md").read_text()

    SECRET = "STORED-SECRET-DO-NOT-COMMIT"

    def test_two_values_cannot_compose_into_a_token_across_adjacent_slots(self) -> None:
        # Each value passes every rule about values: no placeholder syntax, short,
        # declared. Together, in ONE sweep, they spell `{{PROJECT_SLUG}}`.
        out = self._chain(
            "Owner: {{ORG_NAME}}{{GITHUB_OWNER}}\n",
            {
                "ORG_NAME": "{{PROJECT_SLUG",
                "GITHUB_OWNER": "}}",
                "PROJECT_SLUG": self.SECRET,
            },
        )
        self.assertNotIn(self.SECRET, out)

    def test_one_value_cannot_compose_with_itself_in_a_repeated_slot(self) -> None:
        out = self._chain(
            "Owner: {{ORG_NAME}}{{ORG_NAME}}\n",
            {"ORG_NAME": "}}x{{PROJECT_SLUG", "PROJECT_SLUG": self.SECRET},
        )
        self.assertNotIn(self.SECRET, out)

    def test_the_kits_own_braces_cannot_supply_the_syntax(self) -> None:
        # The one that no rule about values can ever catch: `PROJECT_SLUG` is an
        # innocent string with no syntax in it at all. The doubled braces are the
        # TEMPLATE's, and `{{{{ORG_NAME}}}}` renders to `{{PROJECT_SLUG}}`.
        # Built, not written: see tests/test_render_gate.py for why the payload is
        # never spelled out in a file, and for the CI gate that keeps it out.
        template = "Owner: " + "{{" + "{{ORG_NAME}}" + "}}" + "\n"
        out = self._chain(
            template, {"ORG_NAME": "PROJECT_SLUG", "PROJECT_SLUG": self.SECRET}
        )
        self.assertNotIn(self.SECRET, out)

    def test_an_injecting_render_leaves_the_file_untouched_and_names_the_tokens(self) -> None:
        text = "Owner: {{ORG_NAME}}{{GITHUB_OWNER}}\n"
        rendered, count, injected = ia._render_text(
            text, {"ORG_NAME": "{{PROJECT_SLUG", "GITHUB_OWNER": "}}"}
        )

        self.assertEqual(rendered, text, "the file must not be half-rendered")
        self.assertEqual(count, 0)
        self.assertEqual(injected, ["GITHUB_OWNER", "ORG_NAME"])

    def test_an_ordinary_render_still_reaches_a_fixed_point(self) -> None:
        # The guard must not fire on the normal case: a value that merely CONTAINS
        # another token's name, without braces, is not injection.
        rendered, count, injected = ia._render_text(
            "hi {{OPERATOR_NAME}}\n", {"OPERATOR_NAME": "Esteban {{ not a token"}
        )

        self.assertEqual(injected, [])
        self.assertEqual(count, 1)
        self.assertIn("Esteban", rendered)


class RenderCapTest(unittest.TestCase):
    """AC-1's own regression, caught by the migrator lens with a baseline diff.

    The cap lived only in `_prerender_source`, which renders the downloaded SOURCE.
    Carrying it to the writers that render the TARGET turned a working stored answer
    into a refusal: an upgrade UN-RENDERED a file the previous release had rendered,
    `doctor` flipped to FAIL, and the verdict oscillated against a host with an
    older wheel. The cap is a denial-of-service bound, not a validity rule.
    """

    def test_a_long_but_plausible_answer_is_still_rendered(self) -> None:
        # 98,848 characters is a measured base64 PNG of a bank-app QR screenshot.
        # Under the old 4096 this was refused and the slot was dead.
        value = "Q" * 98_848
        table, refused = ia._render_table({"PROJECT_ROOT": value})

        self.assertEqual(refused, [])
        self.assertEqual(table["PROJECT_ROOT"], value)

    def test_an_upgrade_does_not_un_render_a_file_the_previous_release_rendered(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text("operador {{OPERATOR_NAME}}\n", encoding="utf-8")
            stored = {"OPERATOR_NAME": "L" * 5000}

            with contextlib.redirect_stdout(io.StringIO()):
                ia._fill_placeholders(root, ["AGENTS.md"], known=stored)

            self.assertNotIn("{{OPERATOR_NAME}}", (root / "AGENTS.md").read_text())

    def test_the_bound_still_exists(self) -> None:
        table, refused = ia._render_table(
            {"OPERATOR_NAME": "x" * (ia._MAX_PLACEHOLDER_VALUE + 1)}
        )

        self.assertEqual(table, {})
        self.assertEqual([t for t, _ in refused], ["OPERATOR_NAME"])


class RefusalReportingTest(unittest.TestCase):
    """What the operator is told, and what they are told to do about it."""

    def test_the_refusal_names_the_state_files_and_the_remedy(self) -> None:
        # Without this the loop measured by the council has no exit: doctor fails,
        # sends the operator to `configure`, `configure` refuses the same stored
        # value, and the only way out left is pasting the value into a git-tracked
        # kit file by hand — the one place the operator/secrets split exists to
        # keep it out of.
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            ia._report_refused_values([("ORG_NAME", "because")])

        out = buffer.getvalue()
        self.assertIn("configure --set", out)
        self.assertIn(".gk/manifest.json", out)

    def test_a_refusal_for_a_token_no_file_carries_is_not_reported(self) -> None:
        # It warned on every install about a slot no shipped file uses, and warned
        # twice per run with identical wording — which trains the reader to skip the
        # block that matters.
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            ia._report_refused_values([("ORG_NAME", "because")], needed={"OPERATOR_NAME"})

        self.assertEqual(buffer.getvalue(), "")

    def test_a_non_string_stored_value_is_refused_instead_of_crashing(self) -> None:
        # JSON permits numbers and lists; a hostile shared manifest used to abort the
        # install with a raw TypeError out of the regex.
        table, refused = ia._render_table({"ORG_NAME": 7, "OPERATOR_NAME": ["a"]})

        self.assertEqual(table, {})
        self.assertEqual(sorted(t for t, _ in refused), ["OPERATOR_NAME", "ORG_NAME"])

    def test_a_refused_value_is_never_offered_as_the_interactive_default(self) -> None:
        # The prompt read `{{ORG_NAME}} [{{PROJECT_SLUG}}]: ` and Enter re-submitted
        # it: the tool recommended the attacker's payload, then refused what it had
        # recommended.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "doc.md").write_text("{{ORG_NAME}}\n", encoding="utf-8")
            prompts: list[str] = []

            def _capture(prompt: str) -> str:
                prompts.append(prompt)
                return ""

            with contextlib.redirect_stdout(io.StringIO()), \
                 unittest.mock.patch("sys.stdin.isatty", return_value=True), \
                 unittest.mock.patch("builtins.input", _capture):
                ia._fill_placeholders(
                    root, ["doc.md"], known={"ORG_NAME": "{{PROJECT_SLUG}}"}
                )

            self.assertTrue(prompts)
            self.assertNotIn("PROJECT_SLUG", prompts[0])


class ComposingTokensAreDroppedPerRunTest(unittest.TestCase):
    """Skipping the FILE re-opened `ade371f5#6`; the token is dropped instead.

    A file left raw beside rendered siblings makes the source and the target
    disagree, and the next upgrade reads the kit's own substitution as operator
    intent: `.kit-new` is written and a protected file freezes. The council measured
    the whole sequence over four runs of one target.
    """

    def _template(self) -> str:
        return "operador {{OPERATOR_NAME}}\ntag: " + "{{" + "{{ORG_NAME}}" + "}}" + "\n"

    def test_an_innocent_sibling_token_is_still_rendered(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text(self._template(), encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                ia._fill_placeholders(
                    root, ["AGENTS.md"],
                    known={"OPERATOR_NAME": "Esteban", "ORG_NAME": "PROJECT_SLUG"},
                )

            text = (root / "AGENTS.md").read_text()
            self.assertIn("Esteban", text, "the innocent slot must still be filled")
            self.assertIn("{{ORG_NAME}}", text, "the composing slot must stay raw")

    def test_a_dropped_token_is_reported_as_unfilled_and_not_claimed_in_force(self) -> None:
        # It used to be in `table`, so `Still unfilled` stayed silent about it and the
        # returned state declared it applied while the disk held it raw.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text(self._template(), encoding="utf-8")

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                out = ia._fill_placeholders(
                    root, ["AGENTS.md"],
                    known={"OPERATOR_NAME": "Esteban", "ORG_NAME": "PROJECT_SLUG"},
                )

            self.assertIn("Still unfilled", buffer.getvalue())
            self.assertIn("ORG_NAME", buffer.getvalue())
            # The stored answer survives untouched — nothing is deleted behind the
            # operator's back — but the disk is what it is, and it holds the slot raw.
            self.assertEqual(out["ORG_NAME"], "PROJECT_SLUG")
            self.assertIn("{{ORG_NAME}}", (root / "AGENTS.md").read_text())

    def test_the_warning_says_the_operator_cannot_fix_it(self) -> None:
        # `configure --set` is the remedy for a refused VALUE and is useless here:
        # the braces are the kit's. Naming it would send the operator in a circle.
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            ia._report_composing_tokens({"doc.md": {"ORG_NAME"}})

        out = buffer.getvalue()
        self.assertIn("ORG_NAME", out)
        self.assertIn("doc.md", out, "the message must name the file it blames")
        self.assertIn("will not change this", out)

    def test_only_the_overlapping_token_is_blamed(self) -> None:
        # An earlier cut blamed every token the file carried, naming innocent slots —
        # including personal-data ones — in a security message.
        text = "titular {{GITHUB_OWNER}}\nowner " + "{{" + "{{ORG_NAME}}" + "}}" + "\n"
        _, _, composing = ia._render_text(
            text, {"ORG_NAME": "PROJECT_SLUG", "GITHUB_OWNER": "Ana"}
        )

        self.assertEqual(composing, ["ORG_NAME"])


class BracesAreRefusedInAnyStoredValueTest(unittest.TestCase):
    def test_a_value_with_an_opening_brace_pair_is_refused(self) -> None:
        table, refused = ia._render_table({"ORG_NAME": "{{PROJECT_SLUG"})
        self.assertEqual(table, {})
        self.assertEqual([t for t, _ in refused], ["ORG_NAME"])

    def test_a_value_with_a_closing_brace_pair_is_refused(self) -> None:
        # The half that made two innocent-looking values compose across adjacent slots.
        table, refused = ia._render_table({"PROJECT_SLUG": "}}"})
        self.assertEqual(table, {})
        self.assertEqual([t for t, _ in refused], ["PROJECT_SLUG"])

    def test_a_json_null_is_absence_not_a_refusal(self) -> None:
        table, refused = ia._render_table({"ORG_NAME": None})
        self.assertEqual(table, {})
        self.assertEqual(refused, [])


class PrerenderDropsComposingTokensTest(unittest.TestCase):
    """The source pass needs the same drop, and had no test until a mutation said so.

    Mutating `_prerender_source` to keep a composing token left the whole suite
    green — the gap `_fill_placeholders` did not have. A guard nobody tests is the
    claim this epic exists to disbelieve.
    """

    def test_a_composing_token_is_dropped_in_the_file_that_composes(self) -> None:
        with tempfile.TemporaryDirectory() as s:
            src = Path(s)
            (src / "a.md").write_text(
                "operador {{OPERATOR_NAME}}\n", encoding="utf-8"
            )
            (src / "b.md").write_text(
                "tag: " + "{{" + "{{ORG_NAME}}" + "}}" + "\n", encoding="utf-8"
            )

            with contextlib.redirect_stdout(io.StringIO()):
                count = ia._prerender_source(
                    src, {"OPERATOR_NAME": "Esteban", "ORG_NAME": "PROJECT_SLUG"}
                )

            # The innocent token renders everywhere; the composing one renders nowhere,
            # including in the file that could have taken it safely. Per-file was the
            # alternative and it is what re-opened the frozen-protected-file defect.
            self.assertEqual((src / "a.md").read_text(), "operador Esteban\n")
            self.assertIn("{{ORG_NAME}}", (src / "b.md").read_text())
            self.assertEqual(count, 1)

    def test_one_defective_file_does_not_stop_the_others_rendering(self) -> None:
        # This test asserted the OPPOSITE for one round, and the inversion is the
        # finding. Dropping the token for the whole run removed the sibling asymmetry
        # inside a file and bought blast radius instead: one composable file anywhere
        # in the tree un-rendered every file carrying that token, and a council
        # measured `AGENTS.md` frozen permanently for a target with no manifest entry.
        # The narrowest response is per file AND per token.
        with tempfile.TemporaryDirectory() as s:
            src = Path(s)
            (src / "safe.md").write_text("owner {{ORG_NAME}}\n", encoding="utf-8")
            (src / "unsafe.md").write_text(
                "tag: " + "{{" + "{{ORG_NAME}}" + "}}" + "\n", encoding="utf-8"
            )

            with contextlib.redirect_stdout(io.StringIO()):
                ia._prerender_source(src, {"ORG_NAME": "PROJECT_SLUG"})

            self.assertEqual((src / "safe.md").read_text(), "owner PROJECT_SLUG\n")
            self.assertIn("{{ORG_NAME}}", (src / "unsafe.md").read_text())


class ComposingWarningIsPrintedOncePerRunTest(unittest.TestCase):
    """An upgrade printed the block twice, byte-identical, once from each pass.

    The delivery's own reasoning for why that matters is in `_report_refused_values`:
    repetition "trains the reader to skip exactly the block that matters" — and this
    is the block that says a slot will stay raw until someone edits a file.
    """

    def test_a_token_the_source_pass_reported_is_not_reported_again(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            reported = ia._report_composing_tokens(
                {"AGENTS.md": {"ORG_NAME"}}, already={("AGENTS.md", "ORG_NAME")}
            )

        self.assertEqual(buffer.getvalue(), "")
        self.assertEqual(reported, set())

    def test_the_same_token_in_a_DIFFERENT_file_is_still_reported(self) -> None:
        # Deduplicating on the token alone threw away the new information: when the
        # operator's OWN file composes the same token as a kit file already reported,
        # they were told about the file they cannot edit and never about theirs —
        # while the message ends "if it is yours, edit it".
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            ia._report_composing_tokens(
                {"AGENTS.md": {"ORG_NAME"}}, already={("a.md", "ORG_NAME")}
            )

        self.assertIn("AGENTS.md", buffer.getvalue())

    def test_a_token_only_the_target_pass_sees_is_still_reported(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            reported = ia._report_composing_tokens(
                {"AGENTS.md": {"ORG_NAME", "PROJECT_SLUG"}},
                already={("AGENTS.md", "ORG_NAME")},
            )

        self.assertIn("PROJECT_SLUG", buffer.getvalue())
        self.assertNotIn("{{ORG_NAME}}", buffer.getvalue())
        self.assertEqual(reported, {("AGENTS.md", "PROJECT_SLUG")})

    def test_the_source_pass_hands_its_report_forward(self) -> None:
        with tempfile.TemporaryDirectory() as s:
            src = Path(s)
            (src / "doc.md").write_text(
                "tag: " + "{{" + "{{ORG_NAME}}" + "}}" + "\n", encoding="utf-8"
            )
            reported: set[str] = set()

            with contextlib.redirect_stdout(io.StringIO()):
                ia._prerender_source(src, {"ORG_NAME": "PROJECT_SLUG"}, reported=reported)

            self.assertEqual(reported, {("doc.md", "ORG_NAME")})


class FillPlaceholdersAccountingIsPerFileTest(unittest.TestCase):
    def test_a_token_filled_somewhere_is_not_reported_unfilled(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.md").write_text("org: {{ORG_NAME}}\n", encoding="utf-8")
            (root / "b.md").write_text(
                "tag: " + "{{" + "{{ORG_NAME}}" + "}}" + "\n", encoding="utf-8"
            )

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                out = ia._fill_placeholders(
                    root, ["a.md", "b.md"], known={"ORG_NAME": "ACME"}
                )

            self.assertEqual((root / "a.md").read_text(), "org: ACME\n")
            self.assertNotIn("Still unfilled", buffer.getvalue())
            self.assertEqual(out["ORG_NAME"], "ACME")

    def test_a_typed_value_survives_when_one_file_blocked_it(self) -> None:
        # `{**known, **table}` protected this by accident when the value came from
        # `known`. A value typed in this run is not in `known`, so the union strip
        # dropped it from the state while it sat rendered on disk.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.md").write_text("org: {{ORG_NAME}}\n", encoding="utf-8")
            (root / "b.md").write_text(
                "tag: " + "{{" + "{{ORG_NAME}}" + "}}" + "\n", encoding="utf-8"
            )

            with contextlib.redirect_stdout(io.StringIO()), \
                 unittest.mock.patch("sys.stdin.isatty", return_value=True), \
                 unittest.mock.patch("builtins.input", lambda _: "ACME"):
                out = ia._fill_placeholders(root, ["a.md", "b.md"], known={})

            self.assertEqual((root / "a.md").read_text(), "org: ACME\n")
            self.assertEqual(out.get("ORG_NAME"), "ACME")


class WithdrawnFilesAreRemovedFromTargetsTest(unittest.TestCase):
    """Stopping the copy does not undo the copies already made.

    `.docs/index.html` is the kit's landing page, carrying the author's donation
    section — a real PIX key, a BR Code with his civil name and city, an Ethereum
    address, and an outbound request to a QR service. The Python installer already
    refused to ship it; the shell installer copied it into every target, and three
    projects have it. The operator's ruling was that no reference may remain, and a
    file already sitting in three projects is a reference.
    """

    def test_the_withdrawn_landing_page_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".docs").mkdir()
            (root / ".docs" / "index.html").write_text("<donate>", encoding="utf-8")

            self.assertEqual(ia._remove_withdrawn(root), [".docs/index.html"])
            self.assertFalse((root / ".docs" / "index.html").exists())

    def test_a_file_the_kit_still_ships_is_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".docs").mkdir()
            (root / ".docs" / "concepts.html").write_text("concepts", encoding="utf-8")

            self.assertEqual(ia._remove_withdrawn(root), [])
            self.assertTrue((root / ".docs" / "concepts.html").exists())

    def test_a_symlink_at_that_path_is_the_projects_own_decision(self) -> None:
        # Unlinking it would remove something the kit did not put there.
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as other:
            root = Path(d)
            real = Path(other) / "their-page.html"
            real.write_text("the project's own site", encoding="utf-8")
            (root / ".docs").mkdir()
            (root / ".docs" / "index.html").symlink_to(real)

            self.assertEqual(ia._remove_withdrawn(root), [])
            self.assertTrue(real.exists())

    def test_a_target_without_it_is_a_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(ia._remove_withdrawn(Path(d)), [])

    def test_the_withdrawn_shell_installer_is_removed(self) -> None:
        # AC-30 (folding AC-6, AC-10): the shell installer and the Python installer
        # each wrote the same manifest and the same managed `.gitignore` block with no
        # shared source of truth, and diverged in ways that dropped data (a manifest
        # key one added and the other did not know about; a `.gitignore` suffix
        # guarding the operator's own name and prose). The operator's decision was
        # retirement, not reconciliation.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "scripts").mkdir()
            (root / "scripts" / "install-agents-kit.sh").write_text(
                "#!/usr/bin/env bash\n", encoding="utf-8"
            )

            self.assertEqual(
                ia._remove_withdrawn(root), ["scripts/install-agents-kit.sh"]
            )
            self.assertFalse((root / "scripts" / "install-agents-kit.sh").exists())


class ShellInstallerIsNoLongerShippedTest(unittest.TestCase):
    """AC-30: this kit stops seeding/upgrading the shell installer it now withdraws.

    Shipping and withdrawing the same path in the same release would fight itself —
    `--upgrade` re-copying what `_remove_withdrawn` just deleted.
    """

    def test_fresh_paths_no_longer_names_it(self) -> None:
        self.assertNotIn("scripts/install-agents-kit.sh", ia._FRESH_PATHS)

    def test_upgrade_paths_no_longer_names_it(self) -> None:
        self.assertNotIn("scripts/install-agents-kit.sh", ia._UPGRADE_PATHS)

    def test_it_is_named_in_withdrawn_paths(self) -> None:
        self.assertIn("scripts/install-agents-kit.sh", ia._WITHDRAWN_PATHS)
