"""B3: reading sources that live outside the checkout.

`docs/required-reading.md` calls itself the single index and indexed only tracked
files. On 2026-08-04 an agent that had read the whole contract could not find a
project's e-mail recipients, because they live under `~/.config/` and no index
mentioned them — it was not possible to discover the file by reading what the contract
says to read. These tests pin both halves: the index may now carry local entries, and
their absence is detectable instead of being found by incident.
"""
from __future__ import annotations

import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from governancekit.doctor import (
    _check_local_reading_sources,
    _check_local_sources_indexed,
    _local_sources,
)

_HEADER = "| Caminho | Obrigatório | O que é |\n|---|---|---|\n"


def _index(root: Path, rows: str, *, extra: str = "") -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "required-reading.md").write_text(
        "# Required Reading\n\n"
        "## Deste projeto\n\n- `docs/project-rules.md` — regras\n\n"
        "## Fontes locais (fora do checkout)\n\n"
        f"{_HEADER}{rows}\n"
        "## Por área\n\n- (none)\n" + extra,
        encoding="utf-8",
    )


class ParsingTests(unittest.TestCase):
    def test_the_header_row_is_not_an_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _index(root, "")
            self.assertEqual(_local_sources(root), [])

    def test_rows_outside_the_section_are_not_entries(self) -> None:
        # The reading index is full of tables. Only the local-sources one counts, or
        # every `docs/limits.md` row becomes a path the doctor expects on disk.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _index(
                root,
                "| `~/.config/USER.md` | opcional | perfil |\n",
                extra="\n## Outra tabela\n\n| `~/nao-indexado.md` | obrigatório | x |\n",
            )
            self.assertEqual([s.path for s in _local_sources(root)], ["~/.config/USER.md"])

    def test_a_row_without_a_purpose_is_a_note_not_an_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _index(root, "| `~/x.md` |  |  |\n")
            self.assertEqual(_local_sources(root), [])

    def test_optional_is_recognised_in_both_languages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _index(
                root,
                "| `~/a.md` | opcional | x |\n"
                "| `~/b.md` | optional | y |\n"
                "| `~/c.md` | obrigatório | z |\n",
            )
            self.assertEqual(
                [(s.path, s.optional) for s in _local_sources(root)],
                [("~/a.md", True), ("~/b.md", True), ("~/c.md", False)],
            )


class ExistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._home = tempfile.TemporaryDirectory()
        self._patch = unittest.mock.patch.dict(os.environ, {"HOME": self._home.name})
        self._patch.start()
        self.addCleanup(self._patch.stop)
        self.addCleanup(self._home.cleanup)

    def test_a_missing_required_source_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _index(root, "| `~/absent.md` | obrigatório | a regra que falta |\n")

            result = _check_local_reading_sources(root)

            self.assertFalse(result.passed)
            self.assertFalse(result.advisory)
            self.assertIn("absent.md", result.message)

    def test_a_missing_optional_source_only_hints(self) -> None:
        # A fresh clone on another machine must not be a fatal error — the issue's own
        # risk note. Optional is how the index says "this may legitimately be absent".
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _index(root, "| `~/absent.md` | opcional | perfil do operador |\n")

            result = _check_local_reading_sources(root)

            self.assertTrue(result.passed)
            self.assertTrue(result.advisory)
            self.assertIn("absent.md", result.message)

    def test_a_present_source_passes_without_reading_it(self) -> None:
        # The whole point of these files is that their content stays out of the
        # repository. The check must never open them.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (Path(self._home.name) / "recipients.md").write_text(
                "ceo@example.com\n", encoding="utf-8"
            )
            _index(root, "| `~/recipients.md` | obrigatório | agenda de destinatários |\n")

            result = _check_local_reading_sources(root)

            self.assertTrue(result.passed)
            self.assertNotIn("ceo@example.com", result.message)

    def test_an_unstattable_source_does_not_take_the_doctor_down(self) -> None:
        # Council, adversarial user: a credential mounted 0400 under a root-owned
        # directory — the ordinary shape of a Docker or Kubernetes secret — raised
        # PermissionError straight out of the check list, killing every other check
        # and exiting on a traceback instead of a verdict.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _index(root, "| `~/locked/secret.conf` | obrigatório | credencial |\n")

            with unittest.mock.patch.object(
                Path, "exists", side_effect=PermissionError(13, "Permission denied")
            ):
                result = _check_local_reading_sources(root)

            self.assertTrue(result.passed, result.message)

    def test_a_path_outside_the_home_is_rejected_not_probed(self) -> None:
        # An indexed row is operator-local by definition. `docs/required-reading.md`
        # is tracked and anyone can propose a row; a row naming /etc/shadow would turn
        # doctor's own message into an existence probe of whatever machine runs it.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _index(root, "| `/etc/shadow` | obrigatório | sonda |\n")

            result = _check_local_reading_sources(root)

            self.assertTrue(result.advisory)
            self.assertIn("cannot read", result.message)
            self.assertEqual(_local_sources(root), [])

    def test_traversal_out_of_the_home_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _index(root, "| `~/../../etc/shadow` | obrigatório | sonda |\n")

            self.assertEqual(_local_sources(root), [])


class UnreadableTableTests(unittest.TestCase):
    """Council, sweep skeptic: five ordinary table slips made the gate a silent green.

    A required row the parser cannot see reported "no local sources indexed" — the
    same message as a project that declared none. Unreadable and absent must not look
    alike, or the gate stops gating with nobody noticing.
    """

    SLIPS = {
        "extra column": "| `~/absent.md` | obrigatório | motivo | extra |\n",
        "no backticks": "| ~/absent.md | obrigatório | motivo |\n",
        "indented heading": None,  # handled below, it is not a row
        "no purpose": "| `~/absent.md` | obrigatório |  |\n",
    }

    def test_an_unreadable_row_is_reported_not_ignored(self) -> None:
        for label, rows in self.SLIPS.items():
            if rows is None:
                continue
            with self.subTest(label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                _index(root, rows)
                result = _check_local_reading_sources(root)
                if label in {"extra column", "no backticks"}:
                    # These now parse — the row regex was loosened on purpose.
                    self.assertEqual(
                        [s.path for s in _local_sources(root)], ["~/absent.md"], label
                    )
                else:
                    self.assertFalse(result.passed, label)
                    self.assertIn("cannot read", result.message)

    def test_an_indented_heading_still_opens_the_section(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "docs").mkdir(parents=True)
            (root / "docs" / "required-reading.md").write_text(
                " ## Fontes locais\n\n"
                "| Caminho | Obrigatório | O que é |\n|---|---|---|\n"
                "| `~/x.md` | opcional | perfil |\n",
                encoding="utf-8",
            )
            self.assertEqual([s.path for s in _local_sources(root)], ["~/x.md"])

    def test_no_section_at_all_is_silent(self) -> None:
        # Every project installed before B3 has no such section. It must not turn red.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "docs").mkdir()
            (root / "docs" / "required-reading.md").write_text("# Required Reading\n")

            result = _check_local_reading_sources(root)

            self.assertTrue(result.passed)
            self.assertTrue(result.advisory)


class CompletenessTests(unittest.TestCase):
    def test_the_incident_shape_is_detected(self) -> None:
        # 2026-08-04, reconstructed: the contract names a local file, and the index
        # does not carry it. Reading the contract cannot lead you to the file.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _index(root, "| `~/.config/USER.md` | opcional | perfil |\n")
            (root / "AGENTS.md").write_text(
                "Envie por `~/.config/email/send.py`, com `~/.config/email/recipients.conf`.\n",
                encoding="utf-8",
            )

            result = _check_local_sources_indexed(root)

            self.assertFalse(result.passed)
            self.assertTrue(result.advisory, "a detector in this kit hints before it fails")
            self.assertIn("send.py", result.message)

    def test_indexing_the_cited_path_closes_it(self) -> None:
        # The example path is deliberately NOT the retired email helper: that one is in
        # `_WITHDRAWN_CITATIONS`, where indexing is the wrong remedy and the check stays
        # loud on purpose. Using it here tested the generic property through the one
        # path that is an exception to it.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _index(
                root,
                "| `~/.config/acme/roster.json` | opcional | lista de plantão |\n",
            )
            (root / "AGENTS.md").write_text(
                "Consulte `~/.config/acme/roster.json`.\n", encoding="utf-8"
            )

            self.assertTrue(_check_local_sources_indexed(root).passed)

    def test_a_citation_only_inside_a_code_fence_is_still_a_citation(self) -> None:
        # Council, sweep skeptic — the decisive one. The detector required backticks,
        # and AGENTS.md names the 2026-08-04 incident file four times inside a ```bash
        # fence, unquoted. Isolating that citation made the check report "everything is
        # indexed": the fix closed the incident only because the same file happened to
        # appear in an adjacent table too. Showing a path in a shell example is the
        # most natural way to document "run this".
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _index(root, "| `~/.config/USER.md` | opcional | perfil |\n")
            (root / "AGENTS.md").write_text(
                "Envie assim:\n\n```bash\npython3 ~/.config/email/send.py --to lista\n```\n",
                encoding="utf-8",
            )

            result = _check_local_sources_indexed(root)

            self.assertFalse(result.passed)
            self.assertIn("send.py", result.message)

    def test_a_mirror_contract_is_scanned_too(self) -> None:
        # `.cursorrules`, `GEMINI.md` and `.github/copilot-instructions.md` are
        # maintained mirrors of the same contract for other tool ecosystems, carrying
        # the same citations. A local path added to only one of them was invisible.
        for mirror in ("GEMINI.md", ".cursorrules", ".github/copilot-instructions.md"):
            with self.subTest(mirror), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                _index(root, "")
                target = root / mirror
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("Leia `~/.config/regra-do-cursor.md`.\n", encoding="utf-8")

                self.assertFalse(_check_local_sources_indexed(root).passed, mirror)

    def test_history_files_are_not_contracts(self) -> None:
        # `handoff.md` and the napkin *describe* what happened, quoting paths from past
        # sessions — scanning them surfaced `~/AGENTS.md` and `~/docs/limits.md`, which
        # are the 2026-08-04 home-shadow incident being narrated, not a rule source.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _index(root, "")
            (root / "docs" / "napkin-lessons.md").write_text(
                "O `~/AGENTS.md` instalado no home era herdado por walk-up.\n",
                encoding="utf-8",
            )

            self.assertTrue(_check_local_sources_indexed(root).passed)

    def test_an_executable_on_path_is_not_a_reading_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _index(root, "")
            (root / "docs" / "workflow.md").write_text(
                "Crie o symlink para ~/.local/bin/awt e rode `awt`.\n", encoding="utf-8"
            )

            self.assertTrue(_check_local_sources_indexed(root).passed)

    def test_a_directory_citation_is_not_a_reading_source(self) -> None:
        # Four of the first seven hits against the real AI-Agents contract were
        # directory prefixes. Noise in an advisory is not neutral: it teaches the
        # operator to skim past the real hits beside it.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _index(root, "")
            (root / "AGENTS.md").write_text(
                "Credenciais vivem em `~/.config/`, o estado em `$XDG_STATE_HOME/ai-agents/`, "
                "e o perfil em `~/.config/algum-diretorio`.\n",
                encoding="utf-8",
            )

            self.assertTrue(_check_local_sources_indexed(root).passed)

    def test_the_index_does_not_cite_itself(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _index(root, "| `~/.config/USER.md` | opcional | perfil |\n")

            self.assertTrue(_check_local_sources_indexed(root).passed)


class WithdrawnAndEmptyTableTests(unittest.TestCase):
    """Council round 2 of AI-Agents#5 — two hints that were actively harmful."""

    def test_a_table_with_no_rows_is_a_valid_declaration_of_nothing(self) -> None:
        # The kit seeds exactly this scaffold into every new project. Reading it as
        # "a table but no readable rows" made the kit accuse its own starter of being
        # malformed, on day one, in every install.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _index(root, "")

            result = _check_local_reading_sources(root)

            self.assertTrue(result.passed, result.message)
            self.assertEqual(result.message, "no local sources indexed")
            self.assertNotIn("cannot read", result.message)

    def test_a_genuinely_malformed_row_is_still_rejected(self) -> None:
        # The relaxation above must not blind the check to a real broken row.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _index(root, "| `~/.config/thing.conf` |  |\n")

            result = _check_local_reading_sources(root)

            self.assertFalse(result.passed)
            self.assertIn("cannot read", result.message)

    def test_a_withdrawn_transport_citation_is_not_a_missing_index_row(self) -> None:
        # A target whose AGENTS.md was locally edited keeps the OLD contract; the
        # corrected one waits in AGENTS.md.kit-new. Telling the operator to index the
        # cited path is telling them to finish the corruption AI-Agents#5 undid.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _index(root, "")
            (root / "AGENTS.md").write_text(
                "[MANDATORY] Sempre use `~/.config/email/send.py` para enviar.\n",
                encoding="utf-8",
            )

            result = _check_local_sources_indexed(root)

            self.assertFalse(result.passed)
            self.assertIn("WITHDRAWN", result.message)
            self.assertIn("kit-new", result.message)
            self.assertNotIn("Add a `## Fontes locais` section", result.message)

    def test_an_ordinary_uncited_path_still_gets_the_indexing_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _index(root, "")
            (root / "AGENTS.md").write_text(
                "Leia `~/.config/algum-perfil.md` antes.\n", encoding="utf-8",
            )

            result = _check_local_sources_indexed(root)

            self.assertFalse(result.passed)
            self.assertIn("algum-perfil.md", result.message)
            self.assertNotIn("WITHDRAWN", result.message)

    def test_indexing_a_withdrawn_path_does_not_close_it(self) -> None:
        # The operator who followed the OLD advice and indexed the retired transport
        # saw a clean PASS while still carrying the retired contract. The population
        # the wrong message created was the one the first fix left blind.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _index(root, "| `~/.config/email/send.py` | opcional | transporte |\n")
            (root / "AGENTS.md").write_text(
                "[MANDATORY] Envie por `~/.config/email/send.py`.\n", encoding="utf-8",
            )

            result = _check_local_sources_indexed(root)

            self.assertFalse(result.passed)
            self.assertIn("WITHDRAWN", result.message)

    def test_a_project_declaring_that_path_as_its_own_is_not_accused(self) -> None:
        # docs/ is the project's territory. A project naming the helper there is
        # declaring its transport, which the contract requires — not carrying a stale
        # kit file. Deciding by path alone told it "do NOT add these to your index",
        # forbidding the one action §Sending Email step 1 demands.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _index(root, "")
            (root / "docs" / "project-rules.md").write_text(
                "Este projeto envia release mail por `~/.config/email/send.py`.\n",
                encoding="utf-8",
            )

            result = _check_local_sources_indexed(root)

            self.assertNotIn("WITHDRAWN", result.message)
            self.assertIn("send.py", result.message)

    def test_a_withdrawn_citation_never_silences_a_genuinely_missing_row(self) -> None:
        # The first cut returned early, dropping every other unindexed path — including
        # the recipient-list file whose absence from the index IS the 2026-08-04
        # incident this check exists for.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _index(root, "")
            (root / "AGENTS.md").write_text(
                "Envie por `~/.config/email/send.py`; lista em "
                "`~/.config/acme/recipients.conf`.\n",
                encoding="utf-8",
            )

            result = _check_local_sources_indexed(root)

            self.assertFalse(result.passed)
            self.assertIn("recipients.conf", result.message)
            self.assertIn("WITHDRAWN", result.message)


if __name__ == "__main__":
    unittest.main()
