from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from governancekit import mailbox


def _identity(root: Path, **payload) -> None:
    (root / ".credentials").mkdir(parents=True, exist_ok=True)
    (root / ".credentials" / "identity.json").write_text(
        json.dumps({"state_version": 1, **payload}), encoding="utf-8"
    )


class EndpointsAreDerivedFromTheAddressTest(unittest.TestCase):
    """One slot, not two. `SMTP_ACCOUNT` + `SMTP_DOMAIN` asked for the same fact twice."""

    def test_a_known_provider_is_named_not_guessed(self) -> None:
        ends = mailbox.endpoints_for("someone@gmail.com")

        self.assertEqual(ends.smtp_host, "smtp.gmail.com")
        self.assertEqual(ends.imap_host, "imap.gmail.com")
        self.assertFalse(ends.derived, "a table entry must not be reported as a guess")

    def test_an_unknown_domain_falls_back_and_SAYS_it_guessed(self) -> None:
        # A guess announced as a guess is correctable; a guess announced as a fact is a
        # bug report three weeks later.
        ends = mailbox.endpoints_for("calegari@youbrtech.com.br")

        self.assertEqual(ends.smtp_host, "mail.youbrtech.com.br")
        self.assertEqual(ends.imap_host, "imap.youbrtech.com.br")
        self.assertTrue(ends.derived)

    def test_the_setup_text_says_so_too(self) -> None:
        text = "\n".join(mailbox.setup_instructions("calegari@youbrtech.com.br"))

        self.assertIn("guessed from the domain", text)
        self.assertIn(".credentials/smtp.token", text)

    def test_a_string_without_an_at_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            mailbox.endpoints_for("not-an-address")


class TheMailboxReadsTheAddressAndNeverTheSecretTest(unittest.TestCase):
    def test_the_address_comes_from_identity_values(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _identity(root, values={"OPERATOR_EMAIL": "a@gmail.com"}, refs={})

            box = mailbox.load_mailbox(root)

            self.assertEqual(box.address, "a@gmail.com")
            self.assertEqual(box.token_path, ".credentials/smtp.token")

    def test_a_legacy_SMTP_ACCOUNT_is_reused_not_re_asked(self) -> None:
        # Two targets in the park carry this, answered before the 2026-08-10 retirement
        # and orphaned since. Reusing it is the case that proves the reversal was right.
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _identity(root, values={"SMTP_ACCOUNT": "legacy@zoho.com"}, refs={})

            self.assertEqual(mailbox.load_mailbox(root).address, "legacy@zoho.com")

    def test_no_address_names_the_command_that_fixes_it(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _identity(root, values={}, refs={})

            with self.assertRaises(mailbox.MailboxError) as caught:
                mailbox.load_mailbox(root)

            self.assertIn("mail setup", str(caught.exception))

    def test_a_missing_credential_names_where_to_generate_one(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _identity(root, values={"OPERATOR_EMAIL": "a@gmail.com"}, refs={})
            box = mailbox.load_mailbox(root)

            with self.assertRaises(mailbox.MailboxError) as caught:
                mailbox.read_token(root, box)

            self.assertIn("myaccount.google.com/apppasswords", str(caught.exception))

    def test_a_symlinked_credential_is_refused(self) -> None:
        with TemporaryDirectory() as tmp, TemporaryDirectory() as outside:
            root = Path(tmp)
            real = Path(outside) / "real.token"
            real.write_text("sk-SECRET\n", encoding="utf-8")
            _identity(root, values={"OPERATOR_EMAIL": "a@gmail.com"}, refs={})
            (root / ".credentials" / "smtp.token").symlink_to(real)

            with self.assertRaises(Exception) as caught:
                mailbox.read_token(root, mailbox.load_mailbox(root))

            self.assertNotIn("sk-SECRET", str(caught.exception))


class SendingIsRefusedBeforeItIsAmbiguousTest(unittest.TestCase):
    """`sending-email.md`: email cannot be recalled, so ambiguity is asked about."""

    def test_no_recipient_is_refused(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _identity(root, values={"OPERATOR_EMAIL": "a@gmail.com"}, refs={})

            with self.assertRaises(mailbox.MailboxError) as caught:
                mailbox.send_message(root, to=[" ", ""], subject="x", body="y")

            self.assertIn("no recipient", str(caught.exception))

    def test_dry_run_validates_everything_except_the_connection(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _identity(root, values={"OPERATOR_EMAIL": "a@gmail.com"}, refs={})

            out = mailbox.send_message(
                root, to=["b@example.org"], subject="s", body="b", dry_run=True,
            )

            self.assertIn("would send", out)
            self.assertIn("smtp.gmail.com:587", out)

    def test_a_dry_run_needs_no_credential(self) -> None:
        # The whole point: check the address, the recipients and the route before the
        # operator has to produce a token.
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _identity(root, values={"OPERATOR_EMAIL": "a@gmail.com"}, refs={})

            self.assertFalse((root / ".credentials" / "smtp.token").exists())
            mailbox.send_message(
                root, to=["b@example.org"], subject="s", body="b", dry_run=True,
            )


class OverridesWinOverTheGuessTest(unittest.TestCase):
    def test_an_explicit_host_replaces_the_derived_one(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _identity(root, values={
                "OPERATOR_EMAIL": "calegari@youbrtech.com.br",
                "SMTP_OVERRIDES": {"smtp_host": "mail.provedor.com.br", "smtp_port": 465},
            }, refs={})

            ends = mailbox.load_mailbox(root).resolved()

            self.assertEqual(ends.smtp_host, "mail.provedor.com.br")
            self.assertEqual(ends.smtp_port, 465)
            self.assertEqual(ends.imap_host, "imap.youbrtech.com.br")


class TheOrphanReuseActuallyFiresTest(unittest.TestCase):
    """The claim had no artefact behind it, in the delivery that reverses a retirement
    for exactly this population.

    `load_mailbox` called `_identity` first, which raised `no mailbox configured` before
    control ever reached the legacy fallback — and a council measured that NONE of the
    six targets carrying the orphan has `.credentials/identity.json`. The fallback whose
    comment named `CodexBridge` was unreachable on `CodexBridge`.
    """

    def _orphan_target(self, root: Path, metadata: dict) -> None:
        (root / ".gk").mkdir(parents=True)
        (root / ".gk" / "operator.json").write_text(
            json.dumps({"state_version": 1, "metadata": metadata}), encoding="utf-8"
        )

    def test_a_target_with_only_the_legacy_answer_loads(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._orphan_target(
                root, {"OPERATOR_NAME": "Esteban", "SMTP_ACCOUNT": "x@gmail.com"}
            )

            box = mailbox.load_mailbox(root)

            self.assertEqual(box.address, "x@gmail.com")
            self.assertEqual(box.resolved().smtp_host, "smtp.gmail.com")

    def test_the_orphan_without_an_operator_name_beside_it_also_loads(self) -> None:
        # One of the six carries `SMTP_ACCOUNT` alone, and no fixture covered that.
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._orphan_target(root, {"SMTP_ACCOUNT": "y@zoho.com"})

            self.assertEqual(mailbox.load_mailbox(root).address, "y@zoho.com")

    def test_a_target_with_neither_still_says_what_to_run(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            with self.assertRaises(mailbox.MailboxError) as caught:
                mailbox.load_mailbox(root)

            self.assertIn("mail setup", str(caught.exception))

if __name__ == "__main__":
    unittest.main()
