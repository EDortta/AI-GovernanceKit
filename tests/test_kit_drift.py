"""The gate that replaces "change it there first, then mirror it here".

Three things about the other kit are stated in this repository, and until this
file existed nothing checked any of them. Each test below is one of the drift
directions that actually happened or nearly happened on 2026-08-11.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from governancekit import __version__
from governancekit.install_agents import DEFAULT_REF
from governancekit.integration import _matches_range
from governancekit.kit_drift import (
    KitSnapshot,
    digest_shared_section,
    extract_shared_section,
)

ROOT = Path(__file__).resolve().parent.parent


class KitDriftGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = KitSnapshot.load()

    def test_the_snapshot_describes_the_release_this_runtime_pins(self) -> None:
        """Bumping DEFAULT_REF without refreshing the snapshot must not pass.

        The snapshot is only evidence about the release it was read from. Left
        stale behind a pin bump it becomes the opposite: a confident statement
        about a release nobody looked at.
        """
        self.assertEqual(
            self.snapshot.agents_ref,
            DEFAULT_REF,
            "snapshot describes AI-Agents "
            f"{self.snapshot.agents_ref} but this runtime pins {DEFAULT_REF} — "
            "run scripts/refresh-kit-snapshot.py",
        )

    def test_this_runtime_satisfies_the_range_the_pinned_contract_declares(self) -> None:
        """The near-miss of 2026-08-11, as a red test.

        A version bump here is only publishable if the contract that ships in
        every governed project still accepts it. Bumping to 0.3.0 against a
        contract declaring `>=0.2.2,<0.3.0` would have made every `existing`
        project report the integration contract as incompatible — non-advisory,
        which the contract's §8b turns into a STOP.
        """
        self.assertTrue(
            _matches_range(__version__, self.snapshot.governancekit_version_range),
            f"GovernanceKit {__version__} is outside "
            f"{self.snapshot.governancekit_version_range}, the range AI-Agents "
            f"{self.snapshot.agents_ref} declares. Publishing this pair makes every "
            "governed project on that contract report `incompatible`.",
        )

    def test_the_shared_section_here_still_matches_its_origin(self) -> None:
        """Either copy of the section drifting must go red.

        `AGENTS.md` here carries a copy of a section authored in AI-Agents. The
        note under it asks the next person to change the origin first and mirror
        it — which is prose, and prose is what let this same section drift into
        prescribing one machine's mechanism as a universal contract.
        """
        local = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(
            digest_shared_section(local),
            self.snapshot.shared_section_sha256,
            "the §Sending Email body in AGENTS.md no longer matches the one in "
            f"AI-Agents {self.snapshot.agents_ref}. Change the origin "
            "(.docs/workflows/sending-email.md there) first, mirror it here, then "
            "run scripts/refresh-kit-snapshot.py.",
        )


class SharedSectionExtractionTest(unittest.TestCase):
    """The comparison is only as good as the rule that decides what is compared."""

    _BODY = "Email transport is project-specific.\n\nAsk before sending."

    def test_the_origin_note_is_not_part_of_the_canonical_body(self) -> None:
        """The note exists only in the copy; demanding it upstream inverts the gate."""
        with_note = f"## Sending Email\n\n{self._BODY}\n\nOne origin: authored in AI-Agents.\n"
        self.assertEqual(extract_shared_section(with_note), self._BODY)

    def test_a_horizontal_rule_ends_the_section(self) -> None:
        """In AI-Agents the section is followed by `---` and a checklist."""
        carrier = f"# Sending Email\n\nPreamble.\n\n---\n\n## Sending Email\n\n{self._BODY}\n\n---\n\n## Checklist\n\n- [ ] item\n"
        self.assertEqual(extract_shared_section(carrier), self._BODY)

    def test_the_two_carriers_agree_under_one_rule(self) -> None:
        """Same body, different surrounding files, same extraction."""
        as_agents_md = f"## Sending Email\n\n{self._BODY}\n\nOne origin: x.\n"
        as_workflow = f"# Sending Email\n\nLoad only when needed.\n\n---\n\n## Sending Email\n\n{self._BODY}\n\n---\n\n## Checklist\n"
        self.assertEqual(
            extract_shared_section(as_agents_md), extract_shared_section(as_workflow)
        )

    def test_a_deleted_section_fails_the_comparison_instead_of_raising(self) -> None:
        """Deletion is drift too, and must be caught by the same assertion.

        Raising here would let a caller catch-and-skip its way past the one case
        where the section is gone entirely.
        """
        deleted = "# Something else\n\nNo section.\n"
        present = f"## Sending Email\n\n{self._BODY}\n"
        self.assertEqual(extract_shared_section(deleted), "")
        self.assertNotEqual(
            digest_shared_section(deleted),
            digest_shared_section(present),
            "a carrier that lost the section must not hash like one that still has it",
        )


if __name__ == "__main__":
    unittest.main()
