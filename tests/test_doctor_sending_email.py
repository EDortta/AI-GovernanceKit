"""Item 4 of GK#7: the doctor audits §Sending Email by name.

Until now nothing did. `local sources indexed` audits the *index* the section points
at, and `_WITHDRAWN_CITATIONS` fires only when the stale prose happens to cite one of
the paths this kit once prescribed — so a target carrying a withdrawn contract that
names some other transport read as clean.

The audit is by DIGEST against the pinned release, not by reading the prose. That is
the whole design decision: a detector that asked "does this text prescribe a
transport?" would be the fifth textual detector in this kit, and the four before it
each cost a scope defect. "Is this the body the kit ships?" has an answer.
"""
from __future__ import annotations

import os
import tempfile
import unittest
import unittest.mock
from dataclasses import replace
from pathlib import Path

from governancekit.doctor import (
    _check_manifest_drift,
    _check_sending_email_contract,
    run_doctor,
)
from governancekit.kit_drift import KitSnapshot, SnapshotError

ROOT = Path(__file__).resolve().parent.parent

# The shape the section had until v1.2.0: one project's helper, one credential file,
# one SMTP account, presented as a universal contract. This is what a target that
# never upgraded still carries.
_WITHDRAWN = """## Sending Email

Use `~/.config/email/send.py` with the credentials in
`~/.config/email/credentials.conf`, account `[SMTP_ACCOUNT]`.
"""


def _canonical_body() -> str:
    """The real artifact this product ships, not a synthetic stand-in.

    A fixture written by hand would be a second place for the canonical text to
    live, and the fixture is precisely what must not drift.
    """
    return (ROOT / "AGENTS.md").read_text(encoding="utf-8")


def _carry(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class SendingEmailContractTests(unittest.TestCase):
    def test_this_repository_passes_against_its_own_shipped_contract(self) -> None:
        # The fixture case that matters most: the artifact as published.
        result = _check_sending_email_contract(ROOT)
        self.assertTrue(result.passed, result.message)
        self.assertFalse(result.advisory, "a canonical carrier is a real PASS")
        self.assertIn("AGENTS.md", result.message)

    def test_the_canonical_workflow_file_in_a_target_passes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _carry(root, ".docs/workflows/sending-email.md", _canonical_body())

            result = _check_sending_email_contract(root)

            self.assertTrue(result.passed, result.message)
            self.assertFalse(result.advisory)

    def test_a_target_still_carrying_the_withdrawn_contract_fails(self) -> None:
        # The population this check exists for: installed before v1.2.0, never
        # upgraded, and invisible to every other check because the withdrawn prose is
        # a kit file that matches its own manifest hash perfectly.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _carry(root, "AGENTS.md", _WITHDRAWN)

            result = _check_sending_email_contract(root)

            self.assertFalse(result.passed)
            self.assertIn("AGENTS.md", result.message)
            self.assertIn("install-agents --upgrade", result.message)

    def test_a_project_that_FORBIDS_the_withdrawn_transport_is_not_blocked(self) -> None:
        # The fifth textual detector, failing like the four before it. An earlier cut
        # blocked when the body named a withdrawn transport, which cannot tell "use
        # this helper" from "this helper is FORBIDDEN here": a project documenting the
        # ban was blocked for documenting it, and its only exits were to delete its own
        # prohibition or to drop it for the kit's text. Found in round 2.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _carry(
                root,
                "AGENTS.md",
                "## Sending Email\n\nThe legacy `~/.config/email/send.py` helper is "
                "FORBIDDEN here. Use the project's SES transport.\n",
            )

            result = _check_sending_email_contract(root)

            self.assertFalse(result.passed, "it is still not the body the kit ships")
            self.assertTrue(
                result.advisory,
                "a project cannot be blocked for documenting a prohibition",
            )
            self.assertNotIn("prescribes", result.message)

    def test_the_remedy_for_the_workflow_carrier_says_replace_not_merge(self) -> None:
        # Only AGENTS.md is protected. The workflow file lives in a kit directory the
        # upgrade refreshes wholesale, so the command REPLACES it and stashes the
        # project's version. The round-2 lens followed the "merge the .kit-new"
        # advice on this carrier and lost the section it had been told to merge.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _carry(root, ".docs/workflows/sending-email.md", _WITHDRAWN)

            message = _check_sending_email_contract(root).message

            self.assertIn(".gk/overwritten/", message)
            self.assertNotIn("sending-email.md.kit-new", message)

    def test_the_remedy_does_not_promise_a_repair_the_upgrade_will_not_perform(self) -> None:
        # An upgrade does NOT replace a drifted protected file — keeping it is the
        # whole point of R2-16'. What it does is put the kit's version beside it. The
        # first wording said "run --upgrade" full stop, so the pre-.gk population ran
        # it, saw no change in the verdict, and had been told nothing about the merge.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _carry(root, "AGENTS.md", _WITHDRAWN)

            message = _check_sending_email_contract(root).message

            self.assertIn("AGENTS.md.kit-new", message)
            self.assertIn("then merge it", message)

    def test_a_pending_migration_is_not_sent_to_a_command_that_raises(self) -> None:
        # `--upgrade` refuses outright while legacy contracts sit in
        # .docs-migration-bak/, and exits with a RuntimeError naming the flag it
        # wants. A remedy string that produces a traceback is worse than none.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _carry(root, "AGENTS.md", _WITHDRAWN)
            (root / ".docs-migration-bak" / "agents").mkdir(parents=True)

            message = _check_sending_email_contract(root).message

            self.assertIn("--migrate-content", message)

    def test_the_remedy_names_the_kit_new_file_when_one_is_waiting(self) -> None:
        # R2-16' keeps a drifted AGENTS.md and writes the new version beside it. For
        # that target `--upgrade` is the one remedy that changes nothing — it has
        # already run. The exit is the merge, so the message must name it.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _carry(root, "AGENTS.md", _WITHDRAWN)
            _carry(root, "AGENTS.md.kit-new", _canonical_body())

            result = _check_sending_email_contract(root)

            self.assertFalse(result.passed)
            self.assertIn("AGENTS.md.kit-new", result.message)
            self.assertNotIn(
                "install-agents --upgrade",
                result.message,
                "an upgrade that already ran is not a remedy",
            )

    def test_a_stale_carrier_is_reported_even_beside_a_canonical_one(self) -> None:
        # The section moved in v1.2.0. A half-migrated target has the canonical body
        # in the workflow file AND the withdrawn prose still in AGENTS.md, and the
        # agent reads AGENTS.md first.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _carry(root, ".docs/workflows/sending-email.md", _canonical_body())
            _carry(root, "AGENTS.md", _WITHDRAWN)

            result = _check_sending_email_contract(root)

            self.assertFalse(result.passed)
            self.assertIn("AGENTS.md", result.message)

    def test_an_absent_contract_is_reported_by_this_check_and_by_nothing_else(self) -> None:
        # The first cut passed this case in silence, on the written grounds that
        # `AI-Agents manifest` reported it. It does not: that check compares the
        # manifest's paths against disk and never looks at content, so a section that
        # was never installed has no entry to be missing from. Two council lenses
        # reproduced the silence independently. Advisory, because an absent section is
        # not a wrong section — but reported, because nothing else says it.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _carry(root, "AGENTS.md", "# AGENTS\n\nNo email section here.\n")
            (root / ".gk").mkdir()
            (root / ".gk" / "manifest.json").write_text(
                '{"files": {"AGENTS.md": "whatever"}}', encoding="utf-8"
            )

            result = _check_sending_email_contract(root)
            manifest_verdict = _check_manifest_drift(root)

            self.assertFalse(result.passed, "an absent email contract must be said once")
            self.assertTrue(result.advisory, "absent is not the same wrong as stale")
            self.assertTrue(
                manifest_verdict.passed,
                "the check this used to delegate to sees nothing here — that was the bug",
            )

    def test_a_kept_file_awaiting_merge_reports_without_blocking_the_project(self) -> None:
        # The state the installer itself creates and calls acceptable: R2-16' keeps the
        # project's file and parks the kit's beside it. The shell reports exactly this
        # and exits 0 unless the caller asks for --strict; a non-advisory verdict here
        # made validate-governance.sh abort on it, with no exit but a merge the
        # operator may be deferring on purpose.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _carry(root, "AGENTS.md", "## Sending Email\n\nOur own wording, no transport.\n")
            _carry(root, "AGENTS.md.kit-new", _canonical_body())

            result = _check_sending_email_contract(root)

            self.assertFalse(result.passed)
            self.assertTrue(result.advisory, "reported, not a STOP")
            self.assertIn("AGENTS.md.kit-new", result.message)

    def test_the_check_is_actually_registered_in_the_doctor(self) -> None:
        # Every other test here calls the private function. Unregistering it from
        # run_doctor left the whole suite green: the scope item could vanish in a
        # rebase and nothing would notice. Found by the council's claim auditor.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _carry(root, ".docs/workflows/sending-email.md", _canonical_body())

            names = [check.name for check in run_doctor(root).checks]

            self.assertIn("§Sending Email contract", names)

    @unittest.skipIf(os.geteuid() == 0, "root reads through any mode")
    def test_an_unreadable_carrier_is_reported_but_never_blocks(self) -> None:
        # Illegible is not absent and it is not drift: the check could not answer.
        # Failing non-advisorily here would fail a correct project over a permission
        # the check did not need — the 2026-08-07 lesson, one line up the stack.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _carry(root, "AGENTS.md", _canonical_body())
            (root / "AGENTS.md").chmod(0o000)
            try:
                result = _check_sending_email_contract(root)
            finally:
                (root / "AGENTS.md").chmod(0o644)

            self.assertFalse(result.passed)
            self.assertTrue(result.advisory, "unanswerable is not a verdict")
            self.assertIn("AGENTS.md", result.message)
            self.assertNotIn("not the one this kit ships", result.message)

    def test_the_comparison_follows_the_snapshot_and_not_a_literal(self) -> None:
        # The guard R2-18 bought. Move what the pinned release says and the verdict on
        # an unchanged file must move with it; a digest pasted into doctor.py would be
        # a third place for the canonical body to live, and the one nobody refreshes.
        moved = replace(KitSnapshot.load(), shared_section_sha256="0" * 64)
        with unittest.mock.patch.object(KitSnapshot, "load", classmethod(lambda cls, path=None: moved)):
            result = _check_sending_email_contract(ROOT)
        self.assertFalse(result.passed, "the check ignored the snapshot it claims to use")

    def test_an_unusable_snapshot_does_not_convict_the_project(self) -> None:
        # Nothing to compare against is not evidence that the target is wrong.
        def _raise(cls, path=None):
            raise SnapshotError("snapshot missing")

        with unittest.mock.patch.object(KitSnapshot, "load", classmethod(_raise)):
            result = _check_sending_email_contract(ROOT)

        self.assertTrue(result.passed)
        self.assertTrue(result.advisory)


if __name__ == "__main__":
    unittest.main()


class HostIdentityRemedyTest(unittest.TestCase):
    """Round 2, operator lens: `configure && doctor` must be able to terminate.

    Off a TTY the bare command prompts for nothing, exits 0 and changes nothing, so a
    remedy naming it leaves the check red forever — the same defect this delivery
    fixed one check over, only quieter (exit 0 instead of a traceback).
    """

    def test_the_remedy_names_the_flags_that_work_without_a_terminal(self) -> None:
        from governancekit.doctor import _check_host_identity

        with tempfile.TemporaryDirectory() as d:
            result = _check_host_identity(Path(d))

            self.assertFalse(result.passed)
            self.assertIn("--operator-name", result.message)
            self.assertIn("--host-id", result.message)
            self.assertIn("--instance-path", result.message)


class ReadinessDocumentOwnershipTest(unittest.TestCase):
    """Whose words are in the two readiness documents — a question nothing asked.

    The flag checks answer "did someone say ready?". A target installed before
    2026-08-12 carries the KIT's own overview in its docs/, because the installer
    seeds from the kit's copies and the adoption flow that should have replaced them
    skipped its write on a prose match. Advisory: the fleet must not start failing CI
    over a message, and an operator's `yes` outranks any heuristic.
    """

    def _seed(self, root: Path, flag: str) -> None:
        (root / "docs").mkdir(parents=True, exist_ok=True)
        (root / "docs" / "software-overview.md").write_text(
            f"# Software Overview\n\n- project_context_ready: {flag}\n\n"
            "## Install-Time Role\n\nWhen copied into a target project, the programmer "
            "must replace this content with that project's actual context.\n",
            encoding="utf-8",
        )

    def test_the_kits_own_text_is_reported(self) -> None:
        from governancekit.doctor import _check_readiness_documents_are_the_projects_own

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._seed(root, "no")

            result = _check_readiness_documents_are_the_projects_own(root)

            self.assertFalse(result.passed)
            self.assertTrue(result.advisory)
            self.assertIn("describes the kit, not this project", result.message)

    def test_kit_text_that_declares_itself_ready_is_named_as_such(self) -> None:
        from governancekit.doctor import _check_readiness_documents_are_the_projects_own

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._seed(root, "yes")

            result = _check_readiness_documents_are_the_projects_own(root)

            self.assertIn("no operator confirmed that content", result.message)
            self.assertTrue(result.advisory, "the fleet must not start failing over this")

    def test_a_project_that_wrote_its_own_documents_passes(self) -> None:
        from governancekit.doctor import _check_readiness_documents_are_the_projects_own

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "software-overview.md").write_text(
                "# Overview\n\n- project_context_ready: yes\n\nWe bill churches monthly.\n",
                encoding="utf-8",
            )

            self.assertTrue(_check_readiness_documents_are_the_projects_own(root).passed)

    def test_a_confirmed_document_that_quotes_the_phrase_is_not_reclassified(self) -> None:
        # The guard against "fixing" this inside classify_document: READY means an
        # operator said so, and their word must beat a heuristic.
        from governancekit.context_authoring import DocState, classify_document

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._seed(root, "yes")

            self.assertIs(
                classify_document(root, "docs/software-overview.md"), DocState.READY
            )

    def test_the_check_is_registered_in_the_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            names = [c.name for c in run_doctor(Path(d)).checks]
            self.assertIn("readiness documents", names)

    def test_generated_content_is_not_reported_as_the_kits_own_description(self) -> None:
        # The two mandatory flag checks already name a `no` flag. This check exists to
        # add what they cannot say — that the document describes the KIT — and a
        # generated document does not: it is thin, not misdescribed. Saying it twice,
        # in worse words, is how an operator learns to skim.
        from governancekit.doctor import _check_readiness_documents_are_the_projects_own

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "software-overview.md").write_text(
                "# Software Overview\n\n- project_context_ready: no\n\n"
                "## Evidence-based proposal\n\n- Project: demo\n- Detected stack: python\n",
                encoding="utf-8",
            )

            result = _check_readiness_documents_are_the_projects_own(root)

            self.assertTrue(result.passed, result.message)

    def test_generated_content_that_declares_itself_ready_is_still_reported(self) -> None:
        from governancekit.doctor import _check_readiness_documents_are_the_projects_own

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "software-overview.md").write_text(
                "# Software Overview\n\n- project_context_ready: yes\n\n"
                "## Evidence-based proposal\n\n- Project: demo\n",
                encoding="utf-8",
            )

            result = _check_readiness_documents_are_the_projects_own(root)

            self.assertFalse(result.passed)
            self.assertIn("no operator confirmed", result.message)

    def test_the_remedy_for_a_machine_written_yes_is_not_a_command_that_skips_it(self) -> None:
        # `author-context` maps READY to "skip", by design — an operator's word beats a
        # heuristic. So naming it as the way out of a machine-written `yes` sends this
        # population to a command that prints "nothing to do" and changes nothing. The
        # exit is the flag line, and the message has to say so.
        from governancekit.doctor import _check_readiness_documents_are_the_projects_own

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "software-overview.md").write_text(
                "# Software Overview\n\n- project_context_ready: yes\n\n"
                "## Evidence-based proposal\n\n- Project: demo\n",
                encoding="utf-8",
            )

            message = _check_readiness_documents_are_the_projects_own(root).message

            self.assertIn("`- project_context_ready: no`", message)
            self.assertIn("skips the file", message)


class ReadinessFlagRemedyTest(unittest.TestCase):
    def test_a_document_with_no_flag_line_is_told_to_add_one(self) -> None:
        # The short hand-written overview: the kit deliberately refuses to overwrite it,
        # so it fails a mandatory check on every run. Nothing said the fix is one line
        # the operator adds — permanently red with no stated way out.
        from governancekit.doctor import _check_ready_flag

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "limits.md").write_text(
                "# Limits\n\nWe never touch payroll.\n", encoding="utf-8"
            )

            result = _check_ready_flag(root, "docs/limits.md", "limits_ready: yes")

            self.assertFalse(result.passed)
            self.assertIn("has no `limits_ready` line", result.message)
            self.assertIn("- limits_ready: yes", result.message)

    def test_a_document_whose_flag_says_no_is_told_who_sets_it(self) -> None:
        from governancekit.doctor import _check_ready_flag

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "limits.md").write_text(
                "# Limits\n\n- limits_ready: no\n", encoding="utf-8"
            )

            message = _check_ready_flag(root, "docs/limits.md", "limits_ready: yes").message

            self.assertIn("the kit never sets it for you", message)

    def test_the_source_kit_is_not_told_its_own_documents_describe_someone_else(self) -> None:
        # In the AI-Agents checkout those files describe the kit because the kit IS the
        # project, and their `yes` is legitimate. The check was reading its own shipped
        # template as a defect. Fixture is the real repository.
        from governancekit.doctor import _check_readiness_documents_are_the_projects_own

        agents = Path("/home/esteban/Sync/Projects/AI/Agents")
        if not (agents / "templates" / "required-reading.template.md").is_file():
            self.skipTest("the AI-Agents checkout is not available here")

        result = _check_readiness_documents_are_the_projects_own(agents)

        self.assertTrue(result.passed, result.message)
        self.assertIn("source kit", result.message)
