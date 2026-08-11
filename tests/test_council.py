from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from governancekit.council import (
    MAX_ROUNDS,
    NO_RECORD,
    NO_TRIGGER,
    NOT_A_REPO,
    NOT_SELECTABLE,
    NOTHING_STAGED,
    OPEN_FINDINGS,
    ROUNDS_EXHAUSTED,
    SATISFIED,
    STALE_RECORD,
    WAIVED,
    CouncilError,
    CouncilRecord,
    Finding,
    Waiver,
    detect_triggers,
    evaluate,
    record_from_payload,
    staged_fingerprint,
    write_record,
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def _repo(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "council@test")
    _git(root, "config", "user.name", "council")


def _stage(root: Path, relative: str, content: str = "x\n") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(root, "add", "--", relative)


def _commit(root: Path, message: str = "seed") -> None:
    _git(root, "commit", "-q", "--no-verify", "-m", message)


def _round(**overrides) -> dict:
    payload = {
        "round": 1,
        "lenses": ["sweep skeptic", "claim auditor", "second caller"],
        "findings": [],
        "questions": [],
    }
    payload.update(overrides)
    return payload


def _record(root: Path, **overrides) -> CouncilRecord:
    fingerprint = staged_fingerprint(root)
    assert fingerprint is not None
    record = record_from_payload(
        _round(**overrides),
        fingerprint=fingerprint,
        triggers=("shared-contract",),
        recorded_at="2026-08-06T13:00:00",
    )
    write_record(root, record)
    return record


class GateStateTests(unittest.TestCase):
    def test_outside_a_repository_it_says_so_and_never_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = evaluate(Path(temporary))
            self.assertEqual(result.state, NOT_A_REPO)
            self.assertFalse(result.blocks)

    def test_nothing_staged_is_silent(self) -> None:
        # doctor runs constantly outside a commit; a gate that fired there would be
        # noise in every other flow the kit has.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            result = evaluate(root)
            self.assertEqual(result.state, NOTHING_STAGED)
            self.assertFalse(result.blocks)

    def test_ordinary_change_needs_no_council(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "src/app.py", "print('hello')\n")
            result = evaluate(root)
            self.assertEqual(result.state, NO_TRIGGER)
            self.assertFalse(result.blocks)

    def test_shared_contract_change_blocks_without_a_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, ".docs/agents/reviewer.md", "# reviewer\n")
            result = evaluate(root)
            self.assertEqual(result.state, NO_RECORD)
            self.assertTrue(result.blocks)
            self.assertIn("shared-contract", [t.name for t in result.triggers])

    def test_a_clean_round_clears_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "AGENTS.md", "# contract\n")
            _record(root)
            result = evaluate(root)
            self.assertEqual(result.state, SATISFIED)
            self.assertFalse(result.blocks)

    def test_amending_the_diff_invalidates_the_round(self) -> None:
        # The binding to the staged diff is the whole point: an unbound record
        # would make the gate a one-time formality.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "AGENTS.md", "# contract\n")
            _record(root)
            self.assertEqual(evaluate(root).state, SATISFIED)

            _stage(root, "AGENTS.md", "# contract, revised\n")
            result = evaluate(root)
            self.assertEqual(result.state, NO_RECORD)
            self.assertTrue(result.blocks)

    def test_open_finding_blocks_until_it_is_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "AGENTS.md", "# contract\n")
            finding = {
                "lens": "claim auditor",
                "trigger": "install on a clean checkout",
                "wrong_outcome": "the second copy path never receives the script",
                "location": "install_agents.py:512",
                "evidence": "not reproduced: no clean-checkout fixture",
            }
            _record(root, findings=[finding])
            result = evaluate(root)
            self.assertEqual(result.state, OPEN_FINDINGS)
            self.assertTrue(result.blocks)

            _record(root, findings=[{**finding, "closure": "tests/test_install.py::test_second_copy_path"}])
            self.assertEqual(evaluate(root).state, SATISFIED)

    def test_round_two_with_an_open_finding_escalates_instead_of_looping(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "AGENTS.md", "# contract\n")
            _record(root, **{"round": MAX_ROUNDS, "findings": [{
                "lens": "second caller",
                "trigger": "upgrade path",
                "wrong_outcome": "manifest keeps the old ref",
                "location": "install_agents.py:790",
                "evidence": "reproduction: upgrade left ref at v1.1.6",
            }]})
            result = evaluate(root)
            self.assertEqual(result.state, ROUNDS_EXHAUSTED)
            self.assertTrue(result.blocks)
            self.assertIn("operator", result.message)
            self.assertIn("do not run another round", result.message)

    def test_waiver_clears_the_gate_and_keeps_the_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "AGENTS.md", "# contract\n")
            fingerprint = staged_fingerprint(root)
            assert fingerprint is not None
            write_record(root, CouncilRecord(
                fingerprint=fingerprint,
                round=1,
                waiver=Waiver(reason="typo in a comment", recorded_at="2026-08-06T13:00:00"),
            ))
            result = evaluate(root)
            self.assertEqual(result.state, WAIVED)
            self.assertFalse(result.blocks)
            self.assertIn("typo in a comment", result.message)

    def test_stale_fingerprint_inside_the_record_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "AGENTS.md", "# contract\n")
            fingerprint = staged_fingerprint(root)
            assert fingerprint is not None
            path = root / ".gk" / "council" / f"{fingerprint}.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({
                "fingerprint": "0" * 64,
                "round": 1,
                "lenses": ["sweep skeptic"],
                "findings": [],
            }), encoding="utf-8")
            result = evaluate(root)
            self.assertEqual(result.state, STALE_RECORD)
            self.assertTrue(result.blocks)

    def test_repeated_lenses_are_rejected(self) -> None:
        # council.md §3: three members with one lens is one member with extra cost.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "AGENTS.md", "# contract\n")
            _record(root, lenses=["sweep skeptic", "sweep skeptic", "claim auditor"])
            result = evaluate(root)
            self.assertEqual(result.state, OPEN_FINDINGS)
            self.assertIn("lenses repeat", result.message)

    def test_unready_context_defers_to_the_readiness_check(self) -> None:
        # council.md §5: without project_context_ready the council cannot be selected.
        # Blocking twice for one cause teaches people to ignore both messages.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "AGENTS.md", "# contract\n")
            result = evaluate(root, context_ready=False)
            self.assertEqual(result.state, NOT_SELECTABLE)
            self.assertFalse(result.blocks)


class TriggerDetectionTests(unittest.TestCase):
    def test_not_validated_in_the_delivery_is_a_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "handoff.md",
                   "## delivery\n\n### Checks/Tests executed\n\nnot validated: the upgrade path\n")
            names = [trigger.name for trigger in detect_triggers(root)]
            self.assertIn("not-validated", names)

    def test_prose_about_the_marker_is_not_the_marker(self) -> None:
        # Found by running the gate on this kit's own delivery: a napkin lesson that
        # tells people to write `not validated: <what>` convened a council. Same shape
        # as the readiness flag, where the template's prose satisfied the check it
        # was explaining.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "docs/napkin-lessons.md",
                   '- `Action: caso contrário escrever "not validated: <o quê>" no handoff.`\n')
            self.assertEqual([t.name for t in detect_triggers(root)], [])

    def test_a_real_not_validated_line_still_triggers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "handoff.md",
                   "## Checks/Tests executed\n\n  - not validated: the upgrade path\n")
            self.assertIn("not-validated", [t.name for t in detect_triggers(root)])

    def test_a_past_entry_is_not_this_delivery(self) -> None:
        # The first of two false positives this gate produced against its own
        # session-close. `handoff.md` is append-only: a `not validated:` written on
        # 2026-07-27 was still being read ten days later, so every commit touching the
        # file convened a council that no amount of current work could satisfy. The
        # trigger says "the delivery"; it has to read the diff, never the file.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "handoff.md",
                   "## [2026-07-27] old delivery\n\n"
                   "### Checks/Tests executed\n\n"
                   "- not validated: install from a published ref\n")
            _commit(root)
            root.joinpath("handoff.md").write_text(
                "# Handoff\n\n"
                "## [2026-08-07] today\n\n"
                "### Checks/Tests executed\n\n"
                "- pytest: 315 passed\n\n"
                "## [2026-07-27] old delivery\n\n"
                "### Checks/Tests executed\n\n"
                "- not validated: install from a published ref\n",
                encoding="utf-8")
            _git(root, "add", "--", "handoff.md")
            self.assertEqual([t.name for t in detect_triggers(root)], [])

    def test_a_line_describing_the_trigger_is_not_a_claim(self) -> None:
        # The second false positive, on the same session-close: a Blockers bullet that
        # *described* this very trigger matched it. Quoting cannot tell mention from
        # use — council.md's own Enforcement status writes a genuine claim as
        # `not validated:` in backticks — but §4's scope can: only the `Tests` section.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "handoff.md",
                   "## today\n\n"
                   "### Blockers/Risks\n\n"
                   "- `not validated:` ancorado no início da linha ainda casa crase\n\n"
                   "### Checks/Tests executed\n\n"
                   "- pytest: 315 passed\n")
            self.assertEqual([t.name for t in detect_triggers(root)], [])

    def test_a_claim_added_to_an_existing_tests_section_still_triggers(self) -> None:
        # The heading is not in the diff when a bullet is appended under it, so section
        # membership has to come from the file while only added lines are tested. Guards
        # the fix above from being over-applied into a gate that never fires.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "handoff.md",
                   "## today\n\n### Checks/Tests executed\n\n- pytest: 315 passed\n")
            _commit(root)
            root.joinpath("handoff.md").write_text(
                "## today\n\n### Checks/Tests executed\n\n"
                "- pytest: 315 passed\n"
                "- not validated: the upgrade path against a published ref\n",
                encoding="utf-8")
            _git(root, "add", "--", "handoff.md")
            self.assertIn("not-validated", [t.name for t in detect_triggers(root)])

    def test_a_flat_entry_with_no_tests_section_still_declares(self) -> None:
        # Council round 1, sweep skeptic: scoping strictly to a `Tests` section missed
        # three of the four real `not validated:` claims in the two handoff files —
        # entries written as one flat bullet list have no subsections at all. Trading a
        # loud false positive for a silent false negative is not a fix.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "handoff.md",
                   "# Handoff\n\n"
                   "## [2026-07-27] WK-20260727-context-optimization - finished\n\n"
                   "- Validation: run-checks.sh PASS\n"
                   "- Not validated: install from a published ref\n")
            self.assertIn("not-validated", [t.name for t in detect_triggers(root)])

    def test_an_entry_with_a_tests_section_scopes_to_it(self) -> None:
        # The same round: the scope has to stay narrow where the entry does have a
        # tests section, or the Blockers prose that describes the marker comes back.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "handoff.md",
                   "# Handoff\n\n"
                   "## [2026-08-07] today\n\n"
                   "### Entregue\n\n"
                   "- `not validated:` ancorado no início da linha\n\n"
                   "### Checks/Tests executed\n\n"
                   "- pytest: 347 passed\n\n"
                   "## [2026-07-27] older flat entry\n\n"
                   "- Not validated: install from a published ref\n")
            # The older entry's claim is in the file but not in this diff... it is,
            # because the whole file is new here. That is the point: a brand new file
            # is entirely a delivery. What must NOT fire is the quoted prose alone.
            self.assertIn("not-validated", [t.name for t in detect_triggers(root)])
            _commit(root)
            root.joinpath("handoff.md").write_text(
                "# Handoff\n\n"
                "## [2026-08-08] tomorrow\n\n"
                "### Blockers/Risks\n\n"
                "- `not validated:` ancorado ainda casa crase\n\n"
                "### Checks/Tests executed\n\n"
                "- pytest: 347 passed\n\n"
                "## [2026-08-07] today\n\n"
                "### Entregue\n\n"
                "- `not validated:` ancorado no início da linha\n\n"
                "### Checks/Tests executed\n\n"
                "- pytest: 347 passed\n\n"
                "## [2026-07-27] older flat entry\n\n"
                "- Not validated: install from a published ref\n",
                encoding="utf-8")
            _git(root, "add", "--", "handoff.md")
            self.assertEqual([t.name for t in detect_triggers(root)], [])

    def test_a_binary_gitattribute_cannot_silence_the_gate(self) -> None:
        # Council round 2, second caller: `--no-ext-diff --no-textconv` closed two of
        # the three ways a diff can come back unparseable; a `-diff` gitattribute makes
        # git print "Binary files differ" and was still open. Zero hunks reads exactly
        # like a clean diff, so the gate failed open on someone else's git config.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, ".gitattributes", "handoff.md -diff\n")
            _stage(root, "handoff.md",
                   "## today\n\n### Checks/Tests executed\n\n"
                   "- not validated: the upgrade path\n")
            self.assertIn("not-validated", [t.name for t in detect_triggers(root)])

    def test_a_mislevelled_entry_heading_does_not_vanish(self) -> None:
        # Council round 2, new defect: computing entry spans absorbed an entry written
        # one level too deep into the previous entry, and its body then fell outside
        # every span — neither claim nor prose, unreachable. Scoping by the innermost
        # enclosing heading has no spans to get wrong; the line is classified, and the
        # classification is explainable in one sentence.
        from governancekit.council import _claim_scope
        scope = _claim_scope("# Title\n## EntryA\n### Tests\nx\n### EntryB\ny\n")
        self.assertIn(4, scope)          # under a tests heading
        self.assertNotIn(6, scope)       # under a non-tests subsection: prose
        # And the case the span arithmetic could not reach at all is now decided.
        self.assertEqual(_claim_scope(""), frozenset())

    def test_a_configured_external_diff_cannot_silence_the_gate(self) -> None:
        # Council round 1, second caller: `diff.external` (or a GIT_EXTERNAL_DIFF
        # exported by a diff prettifier) replaces the unified diff with output this
        # parser cannot read — and an unparseable diff is indistinguishable from an
        # empty one, so the gate passed silently on exactly the delivery it guards.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _git(root, "config", "diff.external", "/bin/echo")
            _stage(root, "handoff.md",
                   "## today\n\n### Checks/Tests executed\n\n"
                   "- not validated: the upgrade path\n")
            self.assertIn("not-validated", [t.name for t in detect_triggers(root)])

    def test_a_wide_diff_is_reported_as_a_heuristic_not_a_fact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            for index in range(14):
                _stage(root, f"src/module_{index}.py", "value = 1\n")
            sweep = [t for t in detect_triggers(root) if t.name == "mechanical-sweep"]
            self.assertEqual(len(sweep), 1)
            self.assertTrue(sweep[0].heuristic)

    def test_operator_request_is_a_trigger_on_its_own(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, "src/app.py", "print('hello')\n")
            self.assertEqual(detect_triggers(root), ())
            names = [t.name for t in detect_triggers(root, operator_requested=True)]
            self.assertEqual(names, ["operator"])


class RecordPayloadTests(unittest.TestCase):
    def test_a_finding_without_all_four_parts_is_refused(self) -> None:
        with self.assertRaises(CouncilError) as caught:
            record_from_payload(
                _round(findings=[{"lens": "sweep skeptic", "trigger": "rename"}]),
                fingerprint="a" * 64,
                triggers=(),
                recorded_at="2026-08-06T13:00:00",
            )
        self.assertIn("questions", str(caught.exception))

    def test_a_round_beyond_the_cap_is_refused(self) -> None:
        with self.assertRaises(CouncilError):
            record_from_payload(
                _round(round=MAX_ROUNDS + 1),
                fingerprint="a" * 64,
                triggers=(),
                recorded_at="2026-08-06T13:00:00",
            )

    def test_the_payload_cannot_name_its_own_diff(self) -> None:
        # A round that could declare its own fingerprint could declare yesterday's.
        record = record_from_payload(
            _round(fingerprint="b" * 64),
            fingerprint="a" * 64,
            triggers=("shared-contract",),
            recorded_at="2026-08-06T13:00:00",
        )
        self.assertEqual(record.fingerprint, "a" * 64)
        self.assertEqual(record.triggers, ("shared-contract",))

    def test_lenses_are_mandatory(self) -> None:
        with self.assertRaises(CouncilError):
            record_from_payload(
                _round(lenses=[]),
                fingerprint="a" * 64,
                triggers=(),
                recorded_at="2026-08-06T13:00:00",
            )

    def test_questions_survive_the_round(self) -> None:
        # §2: a question that keeps coming back is how the next council gets its lens.
        record = record_from_payload(
            _round(questions=["why does the installer have two copy paths?"]),
            fingerprint="a" * 64,
            triggers=(),
            recorded_at="2026-08-06T13:00:00",
        )
        self.assertEqual(len(record.questions), 1)


class FindingClosureTests(unittest.TestCase):
    def test_closure_is_what_makes_a_finding_closed(self) -> None:
        finding = Finding("lens", "trigger", "outcome", "file:1", "evidence")
        self.assertFalse(finding.closed)
        self.assertTrue(
            Finding("lens", "trigger", "outcome", "file:1", "evidence", "tests/x.py::y").closed
        )


if __name__ == "__main__":
    unittest.main()
