"""R2-2: a manifest entry that was never true must not become a deletion.

`_write_state` merges the previous manifest forward and prunes only entries whose
file has vanished. A path wrongly claimed once therefore survives every upgrade —
and `manifest.json` is the tracked half of the state, so the wrong claim is
committed and reaches every clone. In `remove-agents` such an entry used to match
its own recorded hash and become `remove` at confidence 1.0 with
`requires_operator_review: False`.

The concrete case: installs made between 2026-08-07 and 2026-08-10 recorded the
project's own `templates/` directory as kit-owned.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from governancekit.remove_agents import _is_kit_installable, build_removal_plan


def _seed(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _manifest(root: Path, entries: dict[str, str]) -> None:
    (root / ".gk").mkdir(parents=True, exist_ok=True)
    (root / ".gk" / "manifest.json").write_text(
        json.dumps({"state_version": 1, "files": entries}), encoding="utf-8"
    )


def _sha(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class PoisonedManifestEntryTest(unittest.TestCase):
    def test_a_project_path_the_kit_never_installs_is_not_removed(self) -> None:
        body = "# the project's own template, not the kit's\n"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, "templates/invoice.html", body)
            # The poison: recorded, and the hash genuinely matches.
            _manifest(root, {"templates/invoice.html": _sha(body)})

            plan = build_removal_plan(root)

        item = next(i for i in plan.items if i.path == "templates/invoice.html")
        self.assertEqual(item.action, "preserve", item.evidence)
        self.assertTrue(item.requires_operator_review)
        self.assertEqual(item.confidence, 0.0)

    def test_a_genuine_kit_path_with_a_matching_hash_is_still_removed(self) -> None:
        """The guard must not cost the command its actual job."""
        body = "# kit-owned contract\n"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, "AGENTS.md", body)
            _manifest(root, {"AGENTS.md": _sha(body)})

            plan = build_removal_plan(root)

        item = next(i for i in plan.items if i.path == "AGENTS.md")
        self.assertEqual(item.action, "remove", item.evidence)
        self.assertFalse(item.requires_operator_review)

    def test_the_ownership_question_matches_directories_by_prefix(self) -> None:
        self.assertTrue(_is_kit_installable("AGENTS.md"))
        # Both layouts: the path lists are source-relative and canonical (`docs/`),
        # while the manifest records the installed location (`.docs/`).
        self.assertTrue(_is_kit_installable("docs/agents/security.md"))
        self.assertTrue(_is_kit_installable(".docs/agents/security.md"))
        self.assertFalse(_is_kit_installable("templates/invoice.html"))
        self.assertFalse(_is_kit_installable("src/main.py"))


if __name__ == "__main__":
    unittest.main()
