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
            _stage(root, "handoff.md", "## delivery\n\nnot validated: the upgrade path\n")
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
