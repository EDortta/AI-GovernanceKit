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


class KitNewArtifactTest(unittest.TestCase):
    """The artifact R2-16' introduced, seen by the command that de-adopts the kit.

    An upgrade that keeps a drifted protected file parks the kit's version beside it
    as `<file>.kit-new`. It is in no manifest by construction — the kit did not write
    it into place — and the council's sweep lens found both consequences.
    """

    def test_a_leftover_kit_new_does_not_speak_for_the_project(self) -> None:
        # `_referenced` reads every text file looking for a path literal. The parked
        # copy is the kit's own contract, so it cites the kit's own doc paths: every
        # one of them flipped from `remove` to `preserve`/`kit-owned-modified`,
        # carrying the evidence line "current hash differs from recorded install hash"
        # about files whose hash matched exactly. The kit quoting itself is not the
        # project depending on it.
        body = "# kit-owned contract\n"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, ".docs/agents/programmer.md", body)
            _seed(root, "AGENTS.md", "# our own AGENTS\n")
            _seed(root, "AGENTS.md.kit-new", "see .docs/agents/programmer.md\n")
            _manifest(root, {".docs/agents/programmer.md": _sha(body)})

            plan = build_removal_plan(root)

        item = next(i for i in plan.items if i.path == ".docs/agents/programmer.md")
        self.assertEqual(item.action, "remove", item.evidence)
        self.assertFalse(item.referenced)

    def test_the_parked_copy_is_inventoried_instead_of_being_left_behind(self) -> None:
        # Without this it survived de-adoption: a verbatim copy of the kit's AGENTS.md
        # left in the project root by the command whose job is to leave nothing.
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, "AGENTS.md", "# our own AGENTS\n")
            _seed(root, "AGENTS.md.kit-new", "# the kit's version, unmerged\n")
            _manifest(root, {})

            plan = build_removal_plan(root)

        self.assertIn("AGENTS.md.kit-new", [i.path for i in plan.items])


class CredentialScaffoldingTest(unittest.TestCase):
    """De-adoption must still find what the kit seeds into `.credentials/`.

    Those files used to be manifest entries. Keeping credential paths out of the
    tracked manifest — a SHA-256 of a token is a confirmation oracle — removed the only
    inventory they had, and the planner walked away from the kit's own scaffolding.
    Found by the council's second-caller lens.
    """

    def test_the_kits_own_scaffolding_is_removed_not_merely_listed(self) -> None:
        # Listing it as `unknown / preserve` left it on disk after a full de-adoption —
        # the finding's symptom, unchanged. The evidence is the installer's own record
        # of what it seeded, because the manifest deliberately holds no digest here.
        import json as _json

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, ".credentials/README.md", "how to put tokens here\n")
            _seed(root, ".credentials/identity.json.example", "{}\n")
            (root / ".gk").mkdir(parents=True, exist_ok=True)
            (root / ".gk" / "manifest.json").write_text(_json.dumps({
                "state_version": 1, "files": {},
                "seeded_credentials": ["README.md", "identity.json.example"],
            }), encoding="utf-8")

            items = {item.path: item for item in build_removal_plan(root).items}

        for rel in (".credentials/README.md", ".credentials/identity.json.example"):
            self.assertIn(rel, items)
            self.assertEqual(items[rel].action, "remove", items[rel].evidence)
            self.assertFalse(items[rel].requires_operator_review)

    def test_the_operators_own_credential_files_are_never_candidates(self) -> None:
        # The important half: a real token must not become a removal candidate just
        # because the planner learned to look in that directory.
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, ".credentials/README.md", "MY OWN NOTES, not the kit's\n")
            _seed(root, ".credentials/identity.json", '{"operator_name": "Esteban"}\n')
            _seed(root, ".credentials/llm/openrouter.key", "sk-real\n")
            _manifest(root, {})  # nothing recorded as seeded

            paths = [item.path for item in build_removal_plan(root).items]

        self.assertNotIn(".credentials/identity.json", paths)
        self.assertNotIn(".credentials/llm/openrouter.key", paths)
        # And a README the operator wrote is not removed just because the kit ships a
        # file by that name: without a seeding record there is no evidence of kit
        # authorship, so it is reviewed, never deleted.
        readme = next((i for i in build_removal_plan(root).items
                       if i.path == ".credentials/README.md"), None)
        if readme is not None:
            self.assertNotEqual(readme.action, "remove", readme.evidence)
