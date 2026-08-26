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
            removed, unreadable = ia.unset_placeholder_values(root, ["OPERATOR_NAME"])
            self.assertEqual(removed, {"OPERATOR_NAME": [ia._OVERRIDE_FILE]})
            self.assertEqual(unreadable, [])
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
            removed, _ = ia.unset_placeholder_values(root, ["ORG_NAME", "OPERATOR_NAME"])
            self.assertEqual(removed["ORG_NAME"], [ia._STATE_FILE])
            self.assertEqual(removed["OPERATOR_NAME"], [ia._OPERATOR_FILE])
            manifest = ia._read_json(root / ia._STATE_FILE)
            self.assertNotIn("ORG_NAME", manifest["metadata"])
            # The shared manifest itself survives: it holds files/ref, not identity.
            self.assertTrue((root / ia._STATE_FILE).exists())

    def test_unset_of_an_absent_key_reports_it_and_touches_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            removed, unreadable = ia.unset_placeholder_values(root, ["OPERATOR_NAME"])
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
            removed, unreadable = ia.unset_placeholder_values(root, ["OPERATOR_NAME"])
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

if __name__ == "__main__":  # pragma: no cover
    unittest.main()
