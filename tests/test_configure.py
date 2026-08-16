from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from governancekit.configure import (
    parse_set_pairs,
    run_configure,
    run_configure_identity,
)
from governancekit.install_agents import _MAX_PLACEHOLDER_VALUE
from governancekit.identity import load_identity
from governancekit.identity import Identity, sibling_branch_conflict
from governancekit.path_safety import UnsafePathError


class ConfigureTests(unittest.TestCase):
    def test_set_pairs_parsing(self) -> None:
        self.assertEqual(
            parse_set_pairs(["OPERATOR_NAME=Ann", "GITHUB_OWNER=ann-org"]),
            {"OPERATOR_NAME": "Ann", "GITHUB_OWNER": "ann-org"},
        )
        with self.assertRaises(ValueError):
            parse_set_pairs(["NOEQUALS"])

    def test_fills_known_placeholder_without_touching_project_docs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "AGENTS.md").write_text("Hi {{OPERATOR_NAME}}\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "x.md").write_text("owner {{OPERATOR_NAME}}\n", encoding="utf-8")

            result = run_configure(root, preset={"OPERATOR_NAME": "Ann"}, interactive=False)

            self.assertEqual(result.values, {"OPERATOR_NAME": "Ann"})
            self.assertEqual(result.changed_files, ["AGENTS.md"])
            self.assertNotIn("{{OPERATOR_NAME}}", (root / "AGENTS.md").read_text())
            self.assertIn("{{OPERATOR_NAME}}", (root / "docs" / "x.md").read_text())

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
            (root / "AGENTS.md").write_text("{{OPERATOR_NAME}} {{GITHUB_OWNER}}\n", encoding="utf-8")

            result = run_configure(root, preset={"OPERATOR_NAME": "Ann"}, interactive=False)

            self.assertEqual(result.unfilled, ["GITHUB_OWNER"])

    def test_ignores_placeholders_in_migration_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            backup = root / ".docs-migration-bak"
            backup.mkdir()
            original = "owner: {{OPERATOR_NAME}}\n"
            backup_file = backup / "AGENTS.md"
            backup_file.write_text(original, encoding="utf-8")

            result = run_configure(root, preset={"OPERATOR_NAME": "Ann"}, interactive=False)

            self.assertEqual(result.found_tokens, [])
            self.assertEqual(result.changed_files, [])
            self.assertEqual(backup_file.read_text(encoding="utf-8"), original)

    def test_refuses_symlinked_managed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as outside_dir:
            root = Path(temp_dir)
            outside = Path(outside_dir) / "outside.md"
            outside.write_text("owner: {{OPERATOR_NAME}}\n", encoding="utf-8")
            (root / "AGENTS.md").symlink_to(outside)

            with self.assertRaises(UnsafePathError):
                run_configure(root, preset={"OPERATOR_NAME": "Ann"}, interactive=False)

            self.assertIn("{{OPERATOR_NAME}}", outside.read_text(encoding="utf-8"))

    def test_ignores_credential_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as outside_dir:
            root = Path(temp_dir)
            outside = Path(outside_dir) / "credential.json"
            outside.write_text('{"token": "unchanged"}\n', encoding="utf-8")
            credentials = root / ".credentials"
            credentials.mkdir()
            (credentials / "jira.json").symlink_to(outside)

            result = run_configure(root, preset={"OPERATOR_NAME": "Ann"}, interactive=False)

            self.assertEqual(result.found_tokens, [])
            self.assertEqual(outside.read_text(encoding="utf-8"), '{"token": "unchanged"}\n')


class ConfigureIdentityTests(unittest.TestCase):
    def test_all_branch_ownership_allows_any_branch(self) -> None:
        identity = Identity(sibling_path="/other", branch_ownership="all")
        self.assertEqual(sibling_branch_conflict(identity, "development"), "")
    def test_non_interactive_missing_required_does_not_save(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = run_configure_identity(
                root, preset={"operator_name": "Ann"}, interactive=False
            )
            self.assertFalse(result.saved)
            self.assertIn("host_id", result.missing_required)
            self.assertNotIn("instance_path", result.missing_required)
            self.assertIsNone(load_identity(root))

    def test_identity_prefills_existing_operator_and_checkout_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            credentials = root / ".credentials"
            credentials.mkdir()
            (credentials / "identity.json").write_text(
                '{"values": {"OPERATOR_NAME": "Esteban"}}\n', encoding="utf-8"
            )

            with patch("governancekit.configure.socket.gethostname", return_value="devel3"), patch(
                "builtins.input", return_value=""
            ):
                result = run_configure_identity(root, interactive=True)

            self.assertEqual(result.identity.operator_name, "Esteban")
            self.assertEqual(result.identity.instance_path, str(root.resolve()))
            self.assertEqual(result.identity.host_id, "devel3")
            self.assertEqual(result.identity.branch_ownership, "all")
            self.assertEqual(result.missing_required, [])

    def test_identity_does_not_follow_credential_identity_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as outside_dir:
            root, outside = Path(temp_dir), Path(outside_dir)
            (outside / "identity.json").write_text(
                '{"values": {"OPERATOR_NAME": "Outside"}}\n', encoding="utf-8"
            )
            credentials = root / ".credentials"
            credentials.mkdir()
            (credentials / "identity.json").symlink_to(outside / "identity.json")

            result = run_configure_identity(root, interactive=False)

            self.assertEqual(result.identity.operator_name, "")

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
            (root / "AGENTS.md").write_text("owner: {{OPERATOR_NAME}}\n", encoding="utf-8")

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
            (root / "AGENTS.md").write_text("owner: {{OPERATOR_NAME}}\n", encoding="utf-8")

            code = cli.main(
                ["--root", str(root), "configure", "--set", "OPERATOR_NAME=Ann",
                 "--operator-name", "Ann"]
            )

            self.assertEqual(code, 1)

    def test_bracketed_policy_markers_are_not_treated_as_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "AGENTS.md").write_text(
                "[DEFAULT] [MANDATORY] [PROHIBITED] {{ORG_NAME}}\n", encoding="utf-8"
            )

            result = run_configure(
                root,
                preset={"ORG_NAME": "Acme"},
                interactive=False,
            )

            self.assertEqual(
                (root / "AGENTS.md").read_text(encoding="utf-8"),
                "[DEFAULT] [MANDATORY] [PROHIBITED] Acme\n",
            )
            self.assertEqual(
                result.values,
                {"ORG_NAME": "Acme"},
            )


class ConfigureRenderGateTests(unittest.TestCase):
    """AC-1 — `configure` was the third writer with its own sequential replace.

    It renders the SAME files, from the SAME state, after the installer has already
    run. A gate on two of three writers is not a gate.
    """

    def test_a_value_carrying_placeholder_syntax_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text("owner: {{ORG_NAME}}\n", encoding="utf-8")

            result = run_configure(
                root,
                preset={"ORG_NAME": "{{PROJECT_SLUG}}"},
                interactive=False,
            )

            self.assertEqual(
                (root / "AGENTS.md").read_text(encoding="utf-8"), "owner: {{ORG_NAME}}\n"
            )
            self.assertEqual(result.values, {})
            self.assertIn("ORG_NAME", result.unfilled)

    def test_an_oversized_value_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text("owner: {{ORG_NAME}}\n", encoding="utf-8")

            result = run_configure(
                root,
                preset={"ORG_NAME": "x" * (_MAX_PLACEHOLDER_VALUE + 1)},
                interactive=False,
            )

            self.assertEqual(
                (root / "AGENTS.md").read_text(encoding="utf-8"), "owner: {{ORG_NAME}}\n"
            )
            self.assertEqual(result.changed_files, [])

    def test_a_refused_value_is_never_persisted_as_an_answer(self) -> None:
        # Recording it would hand the poison to the next `--upgrade`, which reads the
        # state before it renders anything.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text("owner: {{ORG_NAME}}\n", encoding="utf-8")

            run_configure(
                root, preset={"ORG_NAME": "{{PROJECT_SLUG}}"}, interactive=False
            )

            manifest = root / ".gk" / "manifest.json"
            operator = root / ".gk" / "operator.json"
            for state_file in (manifest, operator):
                if state_file.exists():
                    self.assertNotIn("{{PROJECT_SLUG}}", state_file.read_text())


class ConfigureGateIsNotConditionalOnTheTargetTests(unittest.TestCase):
    """Three council lenses found this hole independently, which is why it has its
    own class: the gate ran or did not run depending on whether the target happened
    to still carry a raw token. `configure --set` is the same command either way.
    """

    def test_an_already_rendered_target_still_gates_the_preset(self) -> None:
        # No raw `{{TOKEN}}` anywhere: `_scan` returns {} and the early-return branch
        # runs. It used to persist the preset verbatim into the SHARED manifest and
        # print "nothing to configure".
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text("owner: Acme\n", encoding="utf-8")

            run_configure(
                root,
                preset={"ORG_NAME": "{{PROJECT_SLUG}}"},
                interactive=False,
            )

            manifest = root / ".gk" / "manifest.json"
            if manifest.exists():
                self.assertNotIn("{{PROJECT_SLUG}}", manifest.read_text())

    def test_an_already_rendered_target_still_gates_an_oversized_preset(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text("owner: Acme\n", encoding="utf-8")

            run_configure(
                root,
                preset={"PROJECT_SLUG": "z" * (_MAX_PLACEHOLDER_VALUE + 1)},
                interactive=False,
            )

            manifest = root / ".gk" / "manifest.json"
            if manifest.exists():
                self.assertNotIn("zzzz", manifest.read_text())

    def test_an_explicit_set_replaces_a_value_whose_slot_is_already_rendered(self) -> None:
        # The mailbox that never emptied. A refused value stays in the shared state,
        # every colleague sees the warning forever, and `--set` used to drop the
        # replacement in silence because the token was no longer in `found`.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            # ORG_NAME's slot is gone (rendered away); PROJECT_SLUG is still raw, so
            # `found` is non-empty and the filtering branch is the one under test.
            (root / "AGENTS.md").write_text(
                "owner: Acme, slug {{PROJECT_SLUG}}\n", encoding="utf-8"
            )

            run_configure(root, preset={"ORG_NAME": "Acme"}, interactive=False)

            manifest = json.loads((root / ".gk" / "manifest.json").read_text())
            self.assertEqual(manifest["metadata"].get("ORG_NAME"), "Acme")


if __name__ == "__main__":
    unittest.main()


class ConfigureReportsWhatReachedDiskTests(unittest.TestCase):
    """Round 2 of the four-skeptic critique. Three lenses found these independently."""

    def test_an_undeclared_set_key_is_named_instead_of_dropped(self) -> None:
        # A typo used to vanish: rule 1 of the gate drops unknown keys without a word,
        # which is right for state metadata and wrong for an explicit instruction. The
        # command reported success while discarding what it was told to record.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text("owner: {{ORG_NAME}}\n", encoding="utf-8")

            # Named, and the run continues. Raising was tried for one round and a
            # council measured the cost: a legacy script carrying one stale key
            # configured NOTHING, where before it configured everything else and
            # dropped the key. Silence and abort are the same trade in opposite
            # directions; naming it without stopping is neither.
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                result = run_configure(
                    root,
                    preset={"ORG_NMAE": "Acme", "ORG_NAME": "Acme"},
                    interactive=False,
                )

            self.assertIn("ORG_NMAE", buffer.getvalue())
            self.assertEqual(result.changed_files, ["AGENTS.md"])

    def test_values_counts_only_what_reached_a_file(self) -> None:
        # `result.values` is what `cli.py` counts. Once `--set` stopped being filtered
        # by `found` (so a poisoned answer could be replaced), recording an answer for
        # a slot the target does not carry made the CLI print
        # `Filled 3 variable(s) in 1 file(s)` — a claim the disk contradicts.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text("owner: {{ORG_NAME}}\n", encoding="utf-8")

            result = run_configure(
                root,
                preset={"ORG_NAME": "Acme", "PROJECT_SLUG": "kh", "GITHUB_OWNER": "u-1"},
                interactive=False,
            )

            self.assertEqual(result.values, {"ORG_NAME": "Acme"})
            self.assertEqual(result.changed_files, ["AGENTS.md"])

    def test_the_answer_is_still_recorded_even_when_it_reached_no_file(self) -> None:
        # The mailbox must still empty: what `result.values` reports and what the
        # state records are two different questions, and conflating them is what
        # produced the wrong count.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text("owner: {{ORG_NAME}}\n", encoding="utf-8")

            run_configure(
                root,
                preset={"ORG_NAME": "Acme", "PROJECT_SLUG": "myapp"},
                interactive=False,
            )

            manifest = json.loads((root / ".gk" / "manifest.json").read_text())
            self.assertEqual(manifest["metadata"].get("PROJECT_SLUG"), "myapp")


class SetPairsNeverEchoTheValueTests(unittest.TestCase):
    """A council's LGPD lens measured a secret reaching stderr from a typo.

    Two defects met: `parse_set_pairs` interpolated the RAW argument (value included)
    into its error, and the handler meant to print it cleanly called `parser.error`
    in a scope with no `parser` — so the message arrived inside a chained traceback,
    on the command AC-1 had just made the documented remedy for every refusal.
    """

    SECRET = "TOKEN-SECRET-DO-NOT-LOG-0123456789"

    def test_a_missing_equals_does_not_echo_the_value(self) -> None:
        with self.assertRaises(ValueError) as caught:
            parse_set_pairs([f"PROJECT_SLUG {self.SECRET}"])

        self.assertNotIn(self.SECRET, str(caught.exception))

    def test_an_empty_key_does_not_echo_the_value(self) -> None:
        with self.assertRaises(ValueError) as caught:
            parse_set_pairs([f"={self.SECRET}"])

        self.assertNotIn(self.SECRET, str(caught.exception))

    def test_the_message_still_says_what_is_wrong(self) -> None:
        with self.assertRaises(ValueError) as caught:
            parse_set_pairs(["NOEQUALS"])

        self.assertIn("KEY=VALUE", str(caught.exception))


class ConfigureCliErrorIsCleanTests(unittest.TestCase):
    """The handler for a malformed `--set` called `parser.error` in a scope with no
    `parser`, so it raised `NameError` and the operator got a chained traceback with
    their own value inside it."""

    def test_a_malformed_set_exits_cleanly_without_a_traceback(self) -> None:
        import subprocess as sp

        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "AGENTS.md").write_text("owner: {{ORG_NAME}}\n", encoding="utf-8")
            proc = sp.run(
                [sys.executable, "-m", "governancekit", "--root", d,
                 "configure", "--set", "PROJECT_SLUG TOKEN-SECRET"],
                capture_output=True, text=True,
                env={**os.environ, "PYTHONPATH": str(repo)},
            )

        combined = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 2, combined)
        self.assertNotIn("Traceback", combined)
        self.assertNotIn("TOKEN-SECRET", combined)


class AccountingIsPerFileTooTests(unittest.TestCase):
    """Three lenses found this line independently, and it is the same line twice.

    The render was made per file, and the bookkeeping stayed per run: `table` was
    reduced by the UNION of tokens dropped in any file, and that reduced table fed the
    report AND the persistence. So the kit wrote a value into a file and recorded
    nothing — which is, word for word, the state `persist_placeholder_values` exists
    to prevent, arriving through the accounting instead of through the render.
    """

    def _target(self, root: Path) -> None:
        (root / "AGENTS.md").write_text("org: {{ORG_NAME}}\n", encoding="utf-8")
        (root / ".docs" / "agents").mkdir(parents=True)
        (root / ".docs" / "agents" / "deep.md").write_text(
            "tag: " + "{{" + "{{ORG_NAME}}" + "}}" + "\n", encoding="utf-8"
        )

    def test_an_answer_written_to_a_file_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._target(root)

            with contextlib.redirect_stdout(io.StringIO()):
                run_configure(root, preset={"ORG_NAME": "ACME"}, interactive=False)

            manifest = root / ".gk" / "manifest.json"
            self.assertTrue(manifest.exists(), "the value on disk was recorded nowhere")
            self.assertEqual(
                json.loads(manifest.read_text())["metadata"].get("ORG_NAME"), "ACME"
            )

    def test_a_slot_that_was_filled_is_not_called_unfilled(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._target(root)

            with contextlib.redirect_stdout(io.StringIO()):
                result = run_configure(
                    root, preset={"ORG_NAME": "ACME"}, interactive=False
                )

            self.assertEqual(result.values, {"ORG_NAME": "ACME"})
            self.assertEqual(result.unfilled, [])
            self.assertIn("AGENTS.md", result.changed_files)

    def test_a_token_blocked_in_every_file_is_still_unfilled(self) -> None:
        # The other half: pruning must not stop happening, only stop over-reaching.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text(
                "tag: " + "{{" + "{{ORG_NAME}}" + "}}" + "\n", encoding="utf-8"
            )

            with contextlib.redirect_stdout(io.StringIO()):
                result = run_configure(
                    root, preset={"ORG_NAME": "ACME"}, interactive=False
                )

            self.assertEqual(result.values, {})
            self.assertEqual(result.unfilled, ["ORG_NAME"])


class UnknownSetKeyIsNotEchoedWhenItIsNotATokenTests(unittest.TestCase):
    """Both halves of `KEY=VALUE` are free text from the operator.

    The first cut of this warning protected the VALUE — saying so in as many words —
    and printed the KEY verbatim two hundred lines below. An inverted pair puts a
    name, an e-mail or a whole secret in the key half, and `split("=", 1)` keeps
    a payload intact because it carries no `=`.
    """

    def _run(self, key: str) -> str:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text("org: {{ORG_NAME}}\n", encoding="utf-8")
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                run_configure(root, preset={key: "x"}, interactive=False)
            return buffer.getvalue()

    def test_an_inverted_pair_does_not_echo_the_operators_name(self) -> None:
        self.assertNotIn("Esteban Calegari", self._run("Esteban Calegari da Silva"))

    def test_an_inverted_pair_does_not_echo_a_pix_payload(self) -> None:
        payload = "TOKEN-SECRET-DO-NOT-LOG-0123456789"
        self.assertNotIn("TOKEN-SECRET", self._run(payload))

    def test_an_inverted_pair_does_not_echo_an_email(self) -> None:
        self.assertNotIn("@", self._run("someone@example.org"))

    def test_a_genuine_token_typo_is_still_named(self) -> None:
        # The whole point of the warning: a mistyped TOKEN must be nameable, or the
        # operator never learns why their `--set` did nothing.
        self.assertIn("ORG_NMAE", self._run("ORG_NMAE"))

    def test_the_suppressed_key_is_still_counted(self) -> None:
        out = self._run("Esteban Calegari da Silva")
        self.assertIn("not token-shaped", out)
