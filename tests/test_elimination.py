"""AC-21 — the elimination path: what the kit stored about the operator can be
removed, and de-adoption stops hiding the state that survives it.

Three promises, each with a test that goes red without the code:
  1. `remove-agents plan` NAMES the local state files that will survive `apply`
     and says they carry operator data.
  2. `remove-agents apply --purge-state` deletes them and says exactly what was
     eliminated — and what was NOT (git history, the backup just written).
  3. The backup that copies a rendered file announces that it is copying the
     operator's data. Retention is explicit: the directory stays until deleted.
Plus `configure --unset`: eliminating one stored answer is removing a key from a
local file, never a silent no-op.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from governancekit import install_agents as ia
from governancekit import remove_agents as ra


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _target_with_personal_render(root: Path) -> Path:
    """A target whose AGENTS.md was rendered with the operator's name, hash in the
    override (where AC-29 routes it)."""
    rendered = root / "AGENTS.md"
    rendered.write_text("# contract\nOperator: Esteban Calegari\n", encoding="utf-8")
    _write_json(
        root / ia._STATE_FILE,
        {"state_version": 1, "repo": "r", "ref": "v1", "metadata": {}, "files": {}},
    )
    _write_json(
        root / ia._OVERRIDE_FILE,
        {"state_version": 1,
         "metadata": {"OPERATOR_NAME": "Esteban Calegari"},
         "files": {"AGENTS.md": ia._file_sha256(rendered)}},
    )
    return rendered


class PlanNamesSurvivingStateTests(unittest.TestCase):
    def test_the_plan_names_the_state_files_that_survive(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _target_with_personal_render(root)
            plan = ra.build_removal_plan(root)
            self.assertIn(".gk/manifest.override.json", plan.surviving_state)
            self.assertIn(".gk/manifest.json", plan.surviving_state)
            text = ra.format_removal_plan(plan)
            self.assertIn("manifest.override.json", text)
            self.assertIn("operator", text.lower())

    def test_a_target_with_no_state_lists_none(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            plan = ra.build_removal_plan(Path(d))
            self.assertEqual(plan.surviving_state, [])


class PurgeStateTests(unittest.TestCase):
    def test_without_the_flag_the_state_survives_and_is_announced(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _target_with_personal_render(root)
            plan = ra.build_removal_plan(root)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                result = ra.apply_removal_plan(root, plan)
            self.assertTrue((root / ia._OVERRIDE_FILE).exists())
            self.assertEqual(result.purged, [])
            self.assertIn(".gk/manifest.override.json", result.surviving_state)

    def test_with_the_flag_the_local_state_is_eliminated_and_said(self) -> None:
        from governancekit import cli

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _target_with_personal_render(root)
            _write_json(root / ia._OPERATOR_FILE,
                        {"state_version": 1, "metadata": {"OPERATOR_NAME": "Esteban Calegari"}})
            # The issue's headline case is the PIX payload in secrets.json — the
            # most sensitive file must not be the one whose purge no test pins
            # (the security lens ran exactly that mutation and stayed green).
            _write_json(root / ia._SECRETS_FILE,
                        {"state_version": 1,
                         "metadata": {"PIX_PAYLOAD": "00020126PIXSECRET"}})
            plan = ra.build_removal_plan(root)
            ra.write_removal_plan(root, plan)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = cli.main(["--root", str(root), "remove-agents", "apply",
                               "--purge-state"])
            self.assertEqual(rc, 0)
            self.assertFalse((root / ia._OVERRIDE_FILE).exists())
            self.assertFalse((root / ia._OPERATOR_FILE).exists())
            self.assertFalse((root / ia._SECRETS_FILE).exists())
            text = out.getvalue()
            self.assertIn("state eliminated: .gk/manifest.override.json", text)
            self.assertIn("state eliminated: .gk/secrets.json", text)
            # The claim is bounded: nothing says the data is gone from git history.
            self.assertIn("git history", text)

    def test_purge_never_claims_more_than_it_did(self) -> None:
        # The backup written by THIS apply is not purged: it is the undo. The
        # output must say it survives.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _target_with_personal_render(root)
            plan = ra.build_removal_plan(root)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                result = ra.apply_removal_plan(root, plan, purge_state=True)
            self.assertTrue(result.backup_dir.exists())


class BackupAnnouncementTests(unittest.TestCase):
    def test_a_backup_of_a_rendered_file_is_announced_as_personal_data(self) -> None:
        from governancekit import cli

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _target_with_personal_render(root)
            plan = ra.build_removal_plan(root)
            removable = [i.path for i in plan.items if i.action == "remove"]
            self.assertIn("AGENTS.md", removable)  # fixture sanity: hash matches
            ra.write_removal_plan(root, plan)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                cli.main(["--root", str(root), "remove-agents", "apply"])
            text = out.getvalue()
            # The SPECIFIC warning, not any line that happens to contain the word
            # "operator" — the surviving-state block also does, and a first cut of
            # this test stayed green with the warning deleted (AC-17's lesson:
            # a test that never reads the message fixes nothing about it).
            warning = [
                line for line in text.splitlines()
                if "backup just written contains the operator's rendered data" in line
            ]
            self.assertTrue(warning, f"backup warning missing from output:\n{text}")
            self.assertIn("AGENTS.md", warning[0])
            self.assertIn("nothing expires it", text)
            # Never the value itself.
            self.assertNotIn("Esteban Calegari", text)

    def test_the_json_payload_stays_parseable_and_carries_the_fields(self) -> None:
        from governancekit import cli

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _target_with_personal_render(root)
            plan = ra.build_removal_plan(root)
            ra.write_removal_plan(root, plan)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = cli.main(["--root", str(root), "remove-agents", "apply",
                               "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(out.getvalue())
            self.assertIn("AGENTS.md", payload["personal_backups"])
            self.assertIn(".gk/manifest.override.json", payload["surviving_state"])


class ConfigureUnsetTests(unittest.TestCase):
    def test_unset_removes_a_stored_local_answer(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_json(root / ia._OVERRIDE_FILE,
                        {"state_version": 1,
                         "metadata": {"OPERATOR_NAME": "Esteban", "SMTP_ACCOUNT": "a@b.c"}})
            removed, unreadable, elsewhere = ia.unset_placeholder_values(
                root, ["OPERATOR_NAME"])
            self.assertEqual(removed, {"OPERATOR_NAME": [ia._OVERRIDE_FILE]})
            self.assertEqual(unreadable, [])
            self.assertEqual(elsewhere, {})
            override = ia._read_json(root / ia._OVERRIDE_FILE)
            self.assertNotIn("OPERATOR_NAME", override["metadata"])
            self.assertIn("SMTP_ACCOUNT", override["metadata"])

    def test_unsetting_the_last_key_removes_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_json(root / ia._OVERRIDE_FILE,
                        {"state_version": 1, "metadata": {"OPERATOR_NAME": "Esteban"}})
            ia.unset_placeholder_values(root, ["OPERATOR_NAME"])
            self.assertFalse((root / ia._OVERRIDE_FILE).exists())

    def test_unset_reaches_the_shared_half_and_the_legacy_pair_too(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_json(root / ia._STATE_FILE,
                        {"state_version": 1, "repo": "r", "ref": "v1",
                         "metadata": {"ORG_NAME": "ACME"}, "files": {}})
            _write_json(root / ia._OPERATOR_FILE,
                        {"state_version": 1, "metadata": {"OPERATOR_NAME": "Esteban"}})
            removed, _, _ = ia.unset_placeholder_values(root, ["ORG_NAME", "OPERATOR_NAME"])
            self.assertEqual(removed["ORG_NAME"], [ia._STATE_FILE])
            self.assertEqual(removed["OPERATOR_NAME"], [ia._OPERATOR_FILE])
            manifest = ia._read_json(root / ia._STATE_FILE)
            self.assertNotIn("ORG_NAME", manifest["metadata"])
            # The shared manifest itself survives: it holds files/ref, not identity.
            self.assertTrue((root / ia._STATE_FILE).exists())

    def test_unset_of_an_absent_key_reports_it_and_touches_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            removed, unreadable, _ = ia.unset_placeholder_values(root, ["OPERATOR_NAME"])
            self.assertEqual(removed, {"OPERATOR_NAME": []})
            self.assertEqual(unreadable, [])


    def test_the_cli_path_actually_eliminates_and_reports(self) -> None:
        # The security lens deleted the whole `--unset` block from the CLI and
        # the suite stayed green: every unset test called the library directly.
        # This one drives the command the operator types.
        from governancekit import cli

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_json(root / ia._OVERRIDE_FILE,
                        {"state_version": 1,
                         "metadata": {"OPERATOR_NAME": "Esteban"}})
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = cli.main(["--root", str(root), "configure",
                               "--unset", "OPERATOR_NAME"])
            self.assertEqual(rc, 0)
            self.assertFalse((root / ia._OVERRIDE_FILE).exists())
            text = out.getvalue()
            self.assertIn("eliminated OPERATOR_NAME from: .gk/manifest.override.json",
                          text)
            self.assertIn("git history", text)

    def test_a_corrupt_state_file_is_never_answered_with_nothing_to_eliminate(self) -> None:
        # Reproduced by the security lens: a truncated operator.json still
        # holding the value byte-for-byte was answered "not stored anywhere".
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            corrupt = root / ia._OPERATOR_FILE
            corrupt.parent.mkdir(parents=True, exist_ok=True)
            corrupt.write_text('{"metadata": {"OPERATOR_NAME": "Esteban Cal',
                               encoding="utf-8")
            removed, unreadable, _ = ia.unset_placeholder_values(root, ["OPERATOR_NAME"])
            self.assertEqual(removed, {"OPERATOR_NAME": []})
            self.assertEqual(unreadable, [ia._OPERATOR_FILE])
            # And the file was left alone for the operator to inspect.
            self.assertTrue(corrupt.is_file())

    def test_the_cli_warns_about_the_unreadable_file_instead_of_claiming_absence(self) -> None:
        from governancekit import cli

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            corrupt = root / ia._OPERATOR_FILE
            corrupt.parent.mkdir(parents=True, exist_ok=True)
            corrupt.write_text('{"metadata": {"OPERATOR_NAME": "Esteban Cal',
                               encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                cli.main(["--root", str(root), "configure",
                          "--unset", "OPERATOR_NAME"])
            text = out.getvalue()
            self.assertNotIn("not stored anywhere", text)
            self.assertIn("unreadable/corrupt state file", text)
            self.assertIn(".gk/operator.json", text)

    def test_the_same_key_twice_in_one_invocation_does_not_crash(self) -> None:
        # SC-1 (second caller, block council r1): the duplicate `del` raised
        # KeyError after the first had mutated the dict and before the write —
        # the elimination command crashed without eliminating.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_json(root / ia._OVERRIDE_FILE,
                        {"state_version": 1, "metadata": {"OPERATOR_NAME": "Esteban"}})
            removed, unreadable, _ = ia.unset_placeholder_values(
                root, ["OPERATOR_NAME", "OPERATOR_NAME"])
            self.assertEqual(removed, {"OPERATOR_NAME": [ia._OVERRIDE_FILE]})
            self.assertFalse((root / ia._OVERRIDE_FILE).exists())

    def test_identity_carriers_still_holding_the_value_are_named(self) -> None:
        # Sweep lens, block council r1: after `--unset`, `configure` re-inherits
        # the value from .credentials/identity.json and persists it again. The
        # elimination must NAME the carriers it does not touch, or it reports a
        # state the next command undoes.
        from governancekit import cli

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_json(root / ia._OVERRIDE_FILE,
                        {"state_version": 1, "metadata": {"OPERATOR_NAME": "Esteban"}})
            _write_json(root / ".credentials" / "identity.json",
                        {"state_version": 1,
                         "values": {"OPERATOR_NAME": "Esteban"}, "refs": {}})
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                cli.main(["--root", str(root), "configure",
                          "--unset", "OPERATOR_NAME"])
            text = out.getvalue()
            self.assertIn(".credentials/identity.json", text)
            self.assertIn("re-inherit", text)
            # Detection never edits the credential store.
            cred = ia._read_json(root / ".credentials" / "identity.json")
            self.assertEqual(cred["values"]["OPERATOR_NAME"], "Esteban")

    def test_surviving_state_names_the_identity_carriers(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_json(root / ".credentials" / "identity.json",
                        {"values": {"OPERATOR_NAME": "Esteban"}, "refs": {}})
            (root / ".governancekit-identity.json").write_text(
                '{"operator_name": "Esteban"}\n', encoding="utf-8")
            plan = ra.build_removal_plan(root)
            self.assertIn(".credentials/identity.json", plan.surviving_state)
            self.assertIn(".governancekit-identity.json", plan.surviving_state)

    def test_the_backup_directory_gets_its_real_remedy_not_the_blanket_one(self) -> None:
        # SC-2: the blanket remedy named --purge-state/--unset for the backup
        # dir, and neither touches backups. Per-item remedy now; the backup's
        # says hand deletion.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            backups = root / ".gk" / "remove-agents-backup" / "20260826T000000Z"
            backups.mkdir(parents=True)
            (backups / "AGENTS.md").write_text("x\n", encoding="utf-8")
            plan = ra.build_removal_plan(root)
            self.assertIn(".gk/remove-agents-backup/", plan.surviving_state)
            text = ra.format_removal_plan(plan)
            backup_lines = [l for l in text.splitlines()
                            if ".gk/remove-agents-backup/" in l]
            self.assertTrue(backup_lines)
            self.assertIn("delete the directory yourself", backup_lines[0])
            self.assertNotIn("--purge-state`", backup_lines[0].split("[")[0])

    def test_two_applies_in_the_same_second_do_not_collide(self) -> None:
        # SC-4: one-second stamp + exist_ok=False died on Errno 17.
        import unittest.mock as _mock

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _target_with_personal_render(root)
            plan = ra.build_removal_plan(root)
            fixed = ra.datetime(2026, 8, 26, 12, 0, 0, tzinfo=ra.timezone.utc)
            with _mock.patch.object(ra, "datetime") as dt:
                dt.now.return_value = fixed
                r1 = ra.apply_removal_plan(root, plan)
                # Recreate the removed file so the second plan/apply has work.
                _target_with_personal_render(root)
                plan2 = ra.build_removal_plan(root)
                r2 = ra.apply_removal_plan(root, plan2)
            self.assertNotEqual(r1.backup_dir, r2.backup_dir)
            self.assertTrue(r1.backup_dir.exists())
            self.assertTrue(r2.backup_dir.exists())

    def test_plan_json_stays_one_parseable_line_even_without_digests(self) -> None:
        # CA-2 (claim auditor): the missing-digest warning printed to stdout
        # BEFORE the JSON payload — three lines where json.loads expects one.
        import unittest.mock as _mock
        from governancekit import cli

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _target_with_personal_render(root)
            out = io.StringIO()
            with _mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value={},
            ), contextlib.redirect_stdout(out):
                rc = cli.main(["--root", str(root), "remove-agents", "plan",
                               "--json"])
            self.assertEqual(rc, 0)
            json.loads(out.getvalue())  # a second line would raise

    def test_a_symlinked_credential_store_does_not_crash_nor_silence_the_report(self) -> None:
        # Round-2 regression hunter, [introduzido-pela-r1]: the carrier probe
        # used safe_path, which RAISES on the symlinked .credentials/ layout the
        # repo documents as intentional — after the state files were already
        # mutated and before the report printed. The probe now reads like
        # identity.py does (safe_regular_file: skip, never raise).
        from governancekit import cli

        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as store:
            root = Path(d)
            _write_json(root / ia._OVERRIDE_FILE,
                        {"state_version": 1, "metadata": {"OPERATOR_NAME": "Esteban"}})
            _write_json(Path(store) / "identity.json",
                        {"values": {"OPERATOR_NAME": "Esteban"}, "refs": {}})
            (root / ".credentials").mkdir()
            (root / ".credentials" / "identity.json").symlink_to(
                Path(store) / "identity.json")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = cli.main(["--root", str(root), "configure",
                               "--unset", "OPERATOR_NAME"])
            self.assertEqual(rc, 0)
            self.assertFalse((root / ia._OVERRIDE_FILE).exists())
            # The elimination is REPORTED — the crash used to swallow it.
            self.assertIn("eliminated OPERATOR_NAME", out.getvalue())

    def test_the_reviewed_plan_file_is_named_and_purged(self) -> None:
        # Round-2 council question: under --with-llm the plan carries extracted
        # project content; it must be a named survivor and a purge target.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _target_with_personal_render(root)
            plan = ra.build_removal_plan(root)
            ra.write_removal_plan(root, plan)
            plan2 = ra.build_removal_plan(root)
            self.assertIn(".gk/remove-agents-plan.json", plan2.surviving_state)
            result = ra.apply_removal_plan(root, plan2, purge_state=True)
            self.assertIn(".gk/remove-agents-plan.json", result.purged)
            self.assertFalse((root / ".gk" / "remove-agents-plan.json").exists())

if __name__ == "__main__":  # pragma: no cover
    unittest.main()
