"""The install flow authors the two readiness documents, and never blocks on an LLM.

`install-agents` used to own a second generator that wrote both documents itself and
stamped them `yes`. It now runs the same step `author-context` runs — draft, discuss,
confirm — with one difference that is a recorded policy rather than a preference:

    "A project remains operable in manual mode even when no provider is configured
    yet."  — AI-Agents `.docs/agents/credentials-operations.md`, [MANDATORY]

So a missing provider is loud, and never fatal, inside an install.
"""
from __future__ import annotations

import io
import json
import unittest
import unittest.mock
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory

from governancekit import cli
from governancekit.context_authoring import flag_is_yes
from governancekit.install_agents import InstallResult


class _Tty:
    def isatty(self) -> bool:
        return True


class _NoTty:
    def isatty(self) -> bool:
        return False


def _target(tmp: str) -> Path:
    root = Path(tmp)
    (root / "README.md").write_text("# Demo\n\nBills churches monthly.\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    return root


def _install(root: Path, *extra: str) -> tuple[int, str]:
    out = io.StringIO()
    with unittest.mock.patch(
        "governancekit.install_agents.run_install_agents",
        return_value=InstallResult(target=root, upgraded=False),
    ):
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = cli.main(["--root", str(root), "install-agents", *extra])
    return code, out.getvalue()


class InstallContextStepTest(unittest.TestCase):
    def test_install_without_a_provider_still_completes_and_writes_no_flags(self) -> None:
        # The [MANDATORY] policy as an executable claim.
        with TemporaryDirectory() as tmp:
            root = _target(tmp)

            code, output = _install(root, "--non-interactive", "--accept-generated")

            self.assertEqual(code, 0, output)
            # And it says what it is doing without: the scripted path is the one a
            # fleet install takes, and the one where nobody is watching to ask.
            self.assertIn("No provider is configured", output)
            self.assertIn("openrouter", output)
            for rel, marker in (
                ("docs/software-overview.md", "project_context_ready"),
                ("docs/limits.md", "limits_ready"),
            ):
                text = (root / rel).read_text(encoding="utf-8")
                self.assertIn(f"- {marker}: no", text)
                self.assertFalse(flag_is_yes(text, marker))
            self.assertIn("The Start Gate is shut", output)

    def test_a_project_without_a_provider_is_told_what_it_is_missing(self) -> None:
        # The silence this delivery removes: three code paths skipped the LLM without
        # a word, so an operator saw a clean run and concluded this was all there was.
        with TemporaryDirectory() as tmp:
            root = _target(tmp)
            answers = iter(["n"])
            with unittest.mock.patch.object(cli.sys, "stdin", _Tty()), \
                 unittest.mock.patch("builtins.input", lambda _p: next(answers)):
                code, output = _install(root)

            # Loud, and never fatal: the interactive path is where a missing provider
            # could most easily have become a hard stop.
            self.assertEqual(code, 0, output)
            self.assertTrue((root / "docs" / "software-overview.md").is_file())
            self.assertIn("No provider is configured", output)
            self.assertIn("openrouter", output)
            self.assertIn("https://openrouter.ai/keys", output)
            self.assertIn("keyless", output)  # free does not mean keyless
            self.assertIn("config-session", output)

    def test_the_flow_never_reports_success_over_a_shut_gate(self) -> None:
        # The verdict is read off disk. The line it replaces — "existing project
        # documents preserved" — was derived from an empty write list, and printed
        # over the kit's own boilerplate.
        with TemporaryDirectory() as tmp:
            root = _target(tmp)
            docs = root / "docs"
            docs.mkdir()
            (docs / "limits.md").write_text(
                "# Limits\n\n- limits_ready: yes\n\nWe never touch payroll.\n", encoding="utf-8"
            )

            _code, output = _install(root, "--non-interactive", "--accept-generated")

            self.assertIn("docs/software-overview.md", output)
            self.assertNotIn("existing project documents preserved", output)
            # Only the unconfirmed one is named.
            shut = output.split("The Start Gate is shut")[1]
            self.assertIn("docs/software-overview.md", shut)
            self.assertNotIn("docs/limits.md:", shut)

    def test_a_configured_provider_is_never_called_without_a_yes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _target(tmp)
            (root / ".gk").mkdir()
            (root / ".gk" / "project-config.json").write_text(json.dumps({"providers": [
                {"name": "openai", "mode": "env", "credential_ref": "K",
                 "base_url": "https://example.invalid/v1", "model": "gpt-test", "role": "primary"}
            ]}), encoding="utf-8")
            answers = iter(["n"])

            def _boom(*_a, **_k):
                raise AssertionError("the provider was called without consent")

            with unittest.mock.patch.object(cli.sys, "stdin", _Tty()), \
                 unittest.mock.patch("builtins.input", lambda _p: next(answers)), \
                 unittest.mock.patch("governancekit.context_authoring.draft_documents", _boom):
                code, output = _install(root)

            self.assertEqual(code, 0)
            self.assertIn("Stopped; no provider was called.", output)
            self.assertTrue((root / "docs" / "software-overview.md").is_file())

    def test_a_provider_failure_degrades_instead_of_failing_the_install(self) -> None:
        # docs/napkin-lessons.md, 2026-08-02: a provider's unavailability must not turn
        # an installation into a failure.
        with TemporaryDirectory() as tmp:
            root = _target(tmp)
            (root / ".gk").mkdir()
            (root / ".gk" / "project-config.json").write_text(json.dumps({"providers": [
                {"name": "openai", "mode": "env", "credential_ref": "K",
                 "base_url": "https://example.invalid/v1", "model": "gpt-test", "role": "primary"}
            ]}), encoding="utf-8")
            answers = iter(["y"])

            def _fail(*_a, **_k):
                raise RuntimeError("provider unreachable")

            with unittest.mock.patch.object(cli.sys, "stdin", _Tty()), \
                 unittest.mock.patch("builtins.input", lambda _p: next(answers)), \
                 unittest.mock.patch("governancekit.context_authoring.draft_documents", _fail):
                code, output = _install(root)

            self.assertEqual(code, 0, output)
            self.assertIn("Falling back to deterministic discovery", output)
            self.assertTrue((root / "docs" / "software-overview.md").is_file())

    def test_declining_the_description_advice_does_not_leave_the_project_empty(self) -> None:
        # Inside an install, "stopped" cannot mean "left with nothing" — that is the
        # silence the whole delivery is about.
        with TemporaryDirectory() as tmp:
            root = Path(tmp)  # deliberately no README
            answers = iter(["n"])
            with unittest.mock.patch.object(cli.sys, "stdin", _Tty()), \
                 unittest.mock.patch("builtins.input", lambda _p: next(answers)):
                code, output = _install(root)

            self.assertEqual(code, 0)
            self.assertTrue((root / "docs" / "software-overview.md").is_file())
            self.assertIn("The Start Gate is shut", output)


class AuthorContextStandaloneTest(unittest.TestCase):
    def test_the_standalone_command_still_refuses_without_a_provider(self) -> None:
        # That command's whole purpose is the LLM. A command that promises one and
        # quietly does something else is the shape of defect this delivery removes.
        with TemporaryDirectory() as tmp:
            root = _target(tmp)
            err = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                code = cli.main(["--root", str(root), "author-context", "--yes"])

            self.assertEqual(code, 2)
            self.assertIn("No primary LLM provider is configured", err.getvalue())
            self.assertFalse((root / "docs" / "software-overview.md").exists())


if __name__ == "__main__":
    unittest.main()


class DisclosureAndOverwriteTest(unittest.TestCase):
    """Two ways this delivery could hand something away without meaning to."""

    def test_the_install_report_counts_credential_files_but_never_names_them(self) -> None:
        # `.gk/manifest.json` is filtered because "the paths alone say which providers a
        # programmer holds keys for". Printing them to stdout puts the same list in
        # every install log that gets pasted into an issue or a CI job — the same
        # disclosure, one screen away from the comment that forbids it.
        from governancekit.install_agents import InstallResult

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = io.StringIO()
            result = InstallResult(
                target=root, upgraded=False,
                preserved_paths=[".credentials/llm/openrouter.key", ".docs/agents/ours.md"],
            )
            with unittest.mock.patch(
                "governancekit.install_agents.run_install_agents", return_value=result
            ):
                with redirect_stdout(out), redirect_stderr(io.StringIO()):
                    cli.main(["--root", str(root), "install-agents",
                              "--skip-project-configuration"])

            output = out.getvalue()
            self.assertNotIn("openrouter", output, "the install log names a provider key")
            self.assertNotIn(".credentials/llm", output)
            self.assertIn("Kept 1 existing file(s) in .credentials/", output)
            # A project file inside a kit directory is still named — that one is the
            # operator's own document and naming it is the point.
            self.assertIn(".docs/agents/ours.md", output)

    def test_a_draft_never_replaces_project_text_without_saying_so(self) -> None:
        # The review branch says "your file is untouched"; the draft branch said
        # nothing and, under --yes, asked nothing — so prose the project wrote could be
        # overwritten with no stash. `apply_adoption_proposal` guards the same two
        # files; this path did not.
        from governancekit.context_authoring import DocumentProposal

        with TemporaryDirectory() as tmp:
            root = _target(tmp)
            (root / ".gk").mkdir()
            (root / ".gk" / "project-config.json").write_text(json.dumps({"providers": [
                {"name": "openai", "mode": "env", "credential_ref": "K",
                 "base_url": "https://example.invalid/v1", "model": "m", "role": "primary"}
            ]}), encoding="utf-8")
            docs = root / "docs"
            docs.mkdir()
            ours = docs / "software-overview.md"
            ours.write_text(
                "# Ours\n\n- project_context_ready: no\n\nStack: FastAPI, Postgres.\n",
                encoding="utf-8",
            )

            drafts = [DocumentProposal("docs/software-overview.md", "draft",
                                       content="# Generated\n\n- project_context_ready: no\n")]
            out = io.StringIO()
            with unittest.mock.patch("governancekit.context_authoring.draft_documents",
                                     return_value=drafts), \
                 unittest.mock.patch("governancekit.context_authoring.review_documents",
                                     return_value=[]), \
                 unittest.mock.patch.object(cli.sys, "stdin", _NoTty()):
                with redirect_stdout(out), redirect_stderr(io.StringIO()):
                    cli.main(["--root", str(root), "author-context", "--yes"])

            output = out.getvalue()
            self.assertIn("already holds text this kit did not write", output)
            # Accepted under --yes, but the previous version is recoverable.
            self.assertTrue((docs / "software-overview.md.pre-draft").is_file())
            self.assertIn("Stack: FastAPI, Postgres.",
                          (docs / "software-overview.md.pre-draft").read_text())


class CouncilRoundTwoOnAdoptionTest(unittest.TestCase):
    """What round 2 found in round 1's fixes. Several were regressions of the fixes."""

    def test_the_closing_verdict_does_not_claim_the_kit_wrote_a_preserved_file(self) -> None:
        # Four lines apart, the same run said `kept: … left alone` and then
        # `written from detected evidence`. The state came off disk; the CAUSE was
        # hardcoded for every entry.
        from governancekit.adoption import format_readiness_warning

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            message = format_readiness_warning(
                ["docs/software-overview.md", "docs/limits.md"], root,
                written=["docs/software-overview.md"],
            )

        self.assertIn("docs/software-overview.md: written from detected evidence", message)
        self.assertIn("docs/limits.md: yours, left untouched", message)

    def test_the_offer_does_not_claim_source_files_are_uploaded(self) -> None:
        # A cautious operator declining because they read "sources" as "my code" is a
        # decision taken on a false premise. Only the README and detected strings go.
        from governancekit.adoption import format_provider_offer

        with TemporaryDirectory() as tmp:
            offer = format_provider_offer(Path(tmp))

        self.assertIn("No source file is uploaded", offer)

    def test_the_scripted_offer_does_not_present_a_choice_that_is_not_offered(self) -> None:
        from governancekit.adoption import format_provider_offer

        with TemporaryDirectory() as tmp:
            offer = format_provider_offer(Path(tmp), about_to_write=True)

        self.assertIn("This run continues without one", offer)
        self.assertNotIn("Or continue now", offer)

    def test_a_symlinked_readme_does_not_crash_the_authoring_plan(self) -> None:
        # Ordinary in a monorepo. It raised UnsafePathError out of find_description and
        # killed the command with a traceback.
        from governancekit.context_authoring import build_authoring_plan, find_description

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "real").mkdir()
            (root / "real" / "DESC.md").write_text("# Real\n\nA project.\n", encoding="utf-8")
            (root / "README.md").symlink_to(root / "real" / "DESC.md")

            self.assertIsNone(find_description(root))
            plan = build_authoring_plan(root)  # must not raise

        self.assertTrue(plan.needs_description_advice)

    def test_the_pre_draft_backup_is_never_overwritten_by_a_later_draft(self) -> None:
        # One slot, silently reused: accepting a second draft destroyed the operator's
        # original while the message still promised a copy was kept. The path there is
        # exactly what doctor's remedy tells them to do.
        from governancekit.cli import _keep_pre_draft_copy

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            target = root / "docs" / "software-overview.md"
            target.write_text("ORIGINAL, hand written\n", encoding="utf-8")

            first = _keep_pre_draft_copy(root, "docs/software-overview.md")
            target.write_text("GENERATED DRAFT A\n", encoding="utf-8")
            second = _keep_pre_draft_copy(root, "docs/software-overview.md")

            self.assertEqual(first, second)
            self.assertEqual(
                (root / "docs" / "software-overview.md.pre-draft").read_text(),
                "ORIGINAL, hand written\n",
            )

    def test_both_kit_stashes_are_ignored_by_git(self) -> None:
        from governancekit import install_agents as ia

        entries = ia._gitignore_entries(ia._FRESH_PATHS, track_kit_docs=False)
        self.assertIn("*.kit-new", entries)
        self.assertIn("*.pre-draft", entries)

    def test_the_presets_survive_a_catalog_that_cannot_be_read(self) -> None:
        # The fix for an unimportable module turned into silence: losing the catalog
        # also lost the three endpoints that never needed it, so a project holding a
        # gemini key simply stopped being detected.
        from governancekit import llm_catalog

        def _raise():
            raise llm_catalog.CatalogError("simulated")

        original = llm_catalog.provider_offers
        llm_catalog.provider_offers = _raise
        try:
            presets = llm_catalog.presets()
        finally:
            llm_catalog.provider_offers = original

        self.assertIn("gemini", presets)
        self.assertIn("openai", presets)
        self.assertIn("nvidia", presets)
