"""AC-29 — `.gk/manifest.override.json`, the one local half of the state.

Operator decision (2026-08-13, PLANO-UNIFICADO of epic 014): `.gk/manifest.json`
is what the kit IS in this project — committed, shared; the override is what THIS
MACHINE knows — gitignored, per-machine. The legacy pair (`operator.json`,
`secrets.json`) is read, migrated into the override on the next write, and
deleted. These tests fix the migration, the merge order, and the property the
split exists for: nothing local ever reaches the committed half — not a value,
and not the hash of a file rendered with one (AC-22's mechanism).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from governancekit import install_agents as ia


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class LegacyPairMigrationTests(unittest.TestCase):
    def test_the_legacy_pair_is_migrated_into_the_override_and_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_json(
                root / ia._OPERATOR_FILE,
                {"state_version": 1, "metadata": {"OPERATOR_NAME": "Esteban",
                                                  "PROJECT_ROOT": str(root)}},
            )
            _write_json(
                root / ia._SECRETS_FILE,
                {"state_version": 1, "metadata": {"SMTP_ACCOUNT": "a@b.c"}},
            )

            ia._write_state(root, [], repo="r", ref="v1", metadata={})

            override = ia._read_json(root / ia._OVERRIDE_FILE)
            self.assertEqual(
                override["metadata"],
                {"OPERATOR_NAME": "Esteban", "PROJECT_ROOT": str(root),
                 "SMTP_ACCOUNT": "a@b.c"},
            )
            # Migrated means MOVED: reading the old names forever while writing the
            # new one would leave two sources of truth, the defect class AC-30 just
            # retired an installer over.
            self.assertFalse((root / ia._OPERATOR_FILE).exists())
            self.assertFalse((root / ia._SECRETS_FILE).exists())
            # And none of it reached the committed half.
            manifest = ia._read_json(root / ia._STATE_FILE)
            self.assertEqual(manifest["metadata"], {})

    def test_a_target_with_no_local_state_grows_no_override_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ia._write_state(root, [], repo="r", ref="v1",
                            metadata={"ORG_NAME": "ACME"})
            self.assertFalse((root / ia._OVERRIDE_FILE).exists())
            # A file that exists says "there is local state here"; there is none.

    def test_the_override_is_not_group_or_world_readable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ia._write_state(root, [], repo="r", ref="v1",
                            metadata={"OPERATOR_NAME": "Esteban"})
            mode = (root / ia._OVERRIDE_FILE).stat().st_mode & 0o777
            self.assertEqual(mode, 0o600)


class MergeOrderTests(unittest.TestCase):
    def test_the_override_wins_over_the_inherited_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_json(
                root / ia._STATE_FILE,
                {"state_version": 1, "repo": "r", "ref": "v1", "files": {},
                 "metadata": {"ORG_NAME": "From the shared half"}},
            )
            _write_json(
                root / ia._OVERRIDE_FILE,
                {"state_version": 1,
                 "metadata": {"ORG_NAME": "What this machine answered"}},
            )
            merged = ia._read_state(root)
            self.assertEqual(
                ia._state_metadata(merged)["ORG_NAME"], "What this machine answered"
            )

    def test_the_override_wins_over_the_legacy_pair_too(self) -> None:
        # The override is where a NEWER write landed; the pair is what it migrated
        # from. On a target where both exist (a crash between the two steps), the
        # newer answer must win.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_json(
                root / ia._OPERATOR_FILE,
                {"state_version": 1, "metadata": {"OPERATOR_NAME": "Old Answer"}},
            )
            _write_json(
                root / ia._OVERRIDE_FILE,
                {"state_version": 1, "metadata": {"OPERATOR_NAME": "New Answer"}},
            )
            merged = ia._read_state(root)
            self.assertEqual(ia._state_metadata(merged)["OPERATOR_NAME"], "New Answer")


class LocalRenderedHashRoutingTests(unittest.TestCase):
    """AC-22's mechanism: a digest derived from personal data is local state."""

    def test_a_file_rendered_with_a_local_value_is_hashed_in_the_override(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rendered = root / "AGENTS.md"
            rendered.write_text("# contract\nOperator: Esteban Calegari\n",
                                encoding="utf-8")
            impersonal = root / ".docs" / "README.md"
            impersonal.parent.mkdir(parents=True)
            impersonal.write_text("# kit docs\n", encoding="utf-8")

            ia._write_state(
                root, ["AGENTS.md", ".docs/README.md"], repo="r", ref="v1",
                metadata={"OPERATOR_NAME": "Esteban Calegari"},
            )

            manifest = ia._read_json(root / ia._STATE_FILE)
            override = ia._read_json(root / ia._OVERRIDE_FILE)
            self.assertNotIn("AGENTS.md", manifest["files"])
            self.assertIn("AGENTS.md", override["files"])
            self.assertIn(".docs/README.md", manifest["files"])
            # The oracle itself: the digest of the rendered file appears nowhere in
            # the committed half, not merely under a different key.
            self.assertNotIn(
                ia._file_sha256(rendered),
                (root / ia._STATE_FILE).read_text(encoding="utf-8"),
            )

    def test_a_legacy_tracked_entry_for_a_rendered_file_migrates_out(self) -> None:
        # The population that matters: a manifest committed BEFORE the split, with
        # the rendered hash already in the shared half. The next write must move
        # the entry, not merely stop adding new ones.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rendered = root / "AGENTS.md"
            rendered.write_text("Operator: Esteban Calegari\n", encoding="utf-8")
            digest = ia._file_sha256(rendered)
            _write_json(
                root / ia._STATE_FILE,
                {"state_version": 1, "repo": "r", "ref": "v1",
                 "metadata": {}, "files": {"AGENTS.md": digest}},
            )
            _write_json(
                root / ia._OVERRIDE_FILE,
                {"state_version": 1,
                 "metadata": {"OPERATOR_NAME": "Esteban Calegari"}},
            )

            ia._write_state(root, [], repo="r", ref="v1", metadata={})

            manifest = ia._read_json(root / ia._STATE_FILE)
            override = ia._read_json(root / ia._OVERRIDE_FILE)
            self.assertNotIn("AGENTS.md", manifest.get("files", {}))
            self.assertEqual(override["files"]["AGENTS.md"], digest)

    def test_ownership_judgement_still_sees_the_routed_hash(self) -> None:
        # The read side of the routing: `_read_state` merges the override's files,
        # so on THIS machine the upgrade still knows the kit wrote the file.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_json(
                root / ia._STATE_FILE,
                {"state_version": 1, "repo": "r", "ref": "v1", "metadata": {},
                 "files": {".docs/README.md": "aa" * 32}},
            )
            _write_json(
                root / ia._OVERRIDE_FILE,
                {"state_version": 1, "metadata": {},
                 "files": {"AGENTS.md": "bb" * 32}},
            )
            files = ia._state_files(ia._read_state(root))
            self.assertEqual(files[".docs/README.md"], "aa" * 32)
            self.assertEqual(files["AGENTS.md"], "bb" * 32)


class StickyProvenanceTests(unittest.TestCase):
    """A digest describes the content it was computed FROM, not the disk of today.

    The first cut scanned the file as it currently sits, and a council lens
    measured the two doors that opens: delete the rendered file, or rewrite it
    clean, and the OLD digest — derived from the personal value — fell through
    to the tracked manifest. Once local, an entry moves to the shared half only
    on fresh evidence: re-hashed this run, and provably clean.
    """

    def _personalized_target(self, root: Path) -> tuple[Path, str]:
        rendered = root / "AGENTS.md"
        rendered.write_text("Operator: Esteban Calegari\n", encoding="utf-8")
        ia._write_state(root, ["AGENTS.md"], repo="r", ref="v1",
                        metadata={"OPERATOR_NAME": "Esteban Calegari"})
        digest = ia._read_json(root / ia._OVERRIDE_FILE)["files"]["AGENTS.md"]
        return rendered, digest

    def test_a_deleted_file_does_not_surrender_its_digest_to_the_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rendered, digest = self._personalized_target(root)
            rendered.unlink()
            ia._write_state(root, [], repo="r", ref="v1", metadata={})
            manifest_text = (root / ia._STATE_FILE).read_text(encoding="utf-8")
            self.assertNotIn(digest, manifest_text)

    def test_a_clean_rewrite_does_not_publish_the_old_personalized_digest(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rendered, digest = self._personalized_target(root)
            rendered.write_text("clean\n", encoding="utf-8")
            # NOT re-installed: the old digest is merged from the previous state
            # and still describes the personalized bytes.
            ia._write_state(root, [], repo="r", ref="v1", metadata={})
            manifest_text = (root / ia._STATE_FILE).read_text(encoding="utf-8")
            self.assertNotIn(digest, manifest_text)

    def test_a_fresh_hash_of_provably_clean_content_may_move_to_the_shared_half(self) -> None:
        # The downgrade door stays open — otherwise one personalized render
        # quarantines the file for ever, and the team never regains the shared
        # baseline after the render is undone.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rendered, _ = self._personalized_target(root)
            rendered.write_text("clean template\n", encoding="utf-8")
            ia._write_state(root, ["AGENTS.md"], repo="r", ref="v1", metadata={})
            manifest = ia._read_json(root / ia._STATE_FILE)
            self.assertIn("AGENTS.md", manifest["files"])
            override = ia._read_json(root / ia._OVERRIDE_FILE)
            self.assertNotIn("AGENTS.md", override.get("files", {}))


class DoctorReadsBothHalvesTests(unittest.TestCase):
    def test_a_missing_override_tracked_file_fails_the_manifest_check(self) -> None:
        # Reading only `.gk/manifest.json` certified exactly the files AC-29
        # routes away from it: a deleted rendered AGENTS.md still got
        # "all tracked kit paths present".
        from governancekit import doctor

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rendered = root / "AGENTS.md"
            rendered.write_text("Operator: Esteban Calegari\n", encoding="utf-8")
            ia._write_state(root, ["AGENTS.md"], repo="r", ref="v1",
                            metadata={"OPERATOR_NAME": "Esteban Calegari"})
            self.assertTrue(doctor._check_manifest_drift(root).passed)
            rendered.unlink()
            result = doctor._check_manifest_drift(root)
            self.assertFalse(result.passed)
            self.assertIn("AGENTS.md", result.message)


class GitignoreTests(unittest.TestCase):
    def test_the_state_dir_gitignore_covers_the_override(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ia._write_state(root, [], repo="r", ref="v1",
                            metadata={"OPERATOR_NAME": "Esteban"})
            rules = (root / ia._STATE_DIR / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("manifest.override.json\n", rules)
            # The legacy pair stays listed for the un-migrated, mixed-version fleet.
            self.assertIn("operator.json\n", rules)
            self.assertIn("secrets.json\n", rules)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
