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

    # The bytes the "release" seeds, for these tests. Patched in rather than read from
    # the real snapshot so the fixture does not need the pinned tarball — what is under
    # test is that the planner COMPARES, not which digests the release happens to hold.
    SEEDED = {
        "README.md": "how to put tokens here\n",
        "identity.json.example": "{}\n",
    }

    def _digests(self):
        import hashlib
        # tuples, not strings: the table is a HISTORY per name, and `x in "abc"` is
        # substring matching — a str-valued mock passes for the wrong reason.
        return {n: (hashlib.sha256(c.encode()).hexdigest(),)
                for n, c in self.SEEDED.items()}

    def test_the_kits_own_scaffolding_is_removed_not_merely_listed(self) -> None:
        # Listing it as `unknown / preserve` left it on disk after a full de-adoption —
        # the finding's symptom, unchanged.
        import json as _json
        import unittest.mock as _mock

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, content in self.SEEDED.items():
                _seed(root, f".credentials/{name}", content)
            (root / ".gk").mkdir(parents=True, exist_ok=True)
            (root / ".gk" / "manifest.json").write_text(_json.dumps({
                "state_version": 1, "files": {},
                "seeded_credentials": list(self.SEEDED),
            }), encoding="utf-8")

            with _mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value=self._digests(),
            ):
                items = {i.path: i for i in build_removal_plan(root).items}

            for name in self.SEEDED:
                rel = f".credentials/{name}"
                self.assertIn(rel, items)
                self.assertEqual(items[rel].action, "remove", items[rel].evidence)
                self.assertFalse(items[rel].requires_operator_review)

    def test_a_file_the_operator_rewrote_is_not_claimed_as_the_kits(self) -> None:
        # AC-3. The planner printed "matches the file this kit seeds, byte for byte"
        # and compared no bytes: the only test was the NAME. It then set
        # `confidence=1.0` and `requires_operator_review=False` on that — the field
        # that decides whether a human looks before a file is deleted.
        import json as _json
        import unittest.mock as _mock

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, ".credentials/README.md",
                  "# Credenciais\n\nNOTA DO TIME: rotacionar chaves toda sexta.\n")
            (root / ".gk").mkdir(parents=True, exist_ok=True)
            (root / ".gk" / "manifest.json").write_text(_json.dumps({
                "state_version": 1, "files": {},
                "seeded_credentials": ["README.md"],   # the record still says so
            }), encoding="utf-8")

            with _mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value=self._digests(),
            ):
                items = {i.path: i for i in build_removal_plan(root).items}

            item = items[".credentials/README.md"]
            self.assertNotEqual(item.action, "remove", item.evidence)
            self.assertTrue(item.requires_operator_review)
            self.assertNotIn(
                "byte for byte", " ".join(item.evidence),
                "the evidence may not claim a comparison this branch did not make",
            )

    def test_a_legacy_target_without_the_record_is_still_recognised(self) -> None:
        # AC-5. The previous fix keyed on `seeded_credentials`, a manifest key a target
        # adopted before it existed can never acquire — `_seed_dir_missing` only records
        # what it COPIED, and on a target that already has the files everything falls
        # into `preserved`. Byte-identity is stronger evidence than a name in a list,
        # and the legacy target has the bytes on disk to prove it.
        import unittest.mock as _mock

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, content in self.SEEDED.items():
                _seed(root, f".credentials/{name}", content)
            _manifest(root, {})  # a manifest with NO seeded_credentials key at all

            with _mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value=self._digests(),
            ):
                items = {i.path: i for i in build_removal_plan(root).items}

            self.assertEqual(items[".credentials/README.md"].action, "remove")

    def test_the_operators_own_credential_files_are_never_candidates(self) -> None:
        # The important half: a real token must not become a removal candidate just
        # because the planner learned to look in that directory.
        #
        # AC-4: every assertion below used to sit OUTSIDE this `with`. The temporary
        # directory was already gone, `build_removal_plan` returned an empty plan,
        # `readme` was None, and the `if` guarding the only assertion that protects the
        # operator's file never ran. The test passed by observing nothing.
        import unittest.mock as _mock

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, ".credentials/README.md", "MY OWN NOTES, not the kit's\n")
            _seed(root, ".credentials/identity.json", '{"operator_name": "Esteban"}\n')
            _seed(root, ".credentials/llm/openrouter.key", "sk-real\n")
            _manifest(root, {})  # nothing recorded as seeded

            with _mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value=self._digests(),
            ):
                items = {i.path: i for i in build_removal_plan(root).items}

            paths = list(items)
            self.assertNotIn(".credentials/identity.json", paths)
            self.assertNotIn(".credentials/llm/openrouter.key", paths)

            readme = items.get(".credentials/README.md")
            self.assertIsNotNone(readme, "the assertion below must actually run")
            self.assertNotEqual(readme.action, "remove", readme.evidence)

    def test_an_unreadable_snapshot_claims_nothing(self) -> None:
        # Fail closed: without the digests there is no evidence, and this planner may
        # not claim evidence it does not have.
        import unittest.mock as _mock

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, content in self.SEEDED.items():
                _seed(root, f".credentials/{name}", content)

            with _mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value={},
            ):
                items = {i.path: i for i in build_removal_plan(root).items}

            for name in self.SEEDED:
                item = items.get(f".credentials/{name}")
                if item is not None:
                    self.assertNotEqual(item.action, "remove", item.evidence)


class EvidenceNeverOmitsACheckItRanTest(unittest.TestCase):
    """Round 2 of the group critique. AC-3's rule, applied to AC-3's own module.

    The issue wrote the general rule — "nenhuma string de evidência afirma uma
    verificação que o ramo não executou. Vale para os outros ramos do mesmo arquivo" —
    and asked for a sweep. The sweep was not done, and two branches were wrong in
    opposite directions: one omitted a check it ran, the other asserted one it did not.
    """

    SEEDED = {"identity.json.example": "{}\n"}

    def _digests(self):
        import hashlib
        return {n: (hashlib.sha256(c.encode()).hexdigest(),) for n, c in self.SEEDED.items()}

    def test_a_seeded_file_the_project_references_is_not_deleted_unreviewed(self) -> None:
        # The branch COMPUTED `referenced`, stored it on the item, and emitted
        # `remove / review=False` anyway. Its twin is gated on `and not referenced`,
        # and `_referenced`'s docstring says "A hit only prevents automatic deletion".
        import json as _json
        import unittest.mock as _mock

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, content in self.SEEDED.items():
                _seed(root, f".credentials/{name}", content)
            _seed(root, "docs/onboarding.md",
                  "Copy .credentials/identity.json.example to identity.json.\n")
            (root / ".gk").mkdir(parents=True, exist_ok=True)
            (root / ".gk" / "manifest.json").write_text(
                _json.dumps({"state_version": 1, "files": {}}), encoding="utf-8")

            with _mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value=self._digests(),
            ):
                items = {i.path: i for i in build_removal_plan(root).items}

            item = items[".credentials/identity.json.example"]
            self.assertNotEqual(item.action, "remove", item.evidence)
            self.assertTrue(item.requires_operator_review)
            self.assertIn("referenced elsewhere", " ".join(item.evidence))

    def test_a_matching_hash_is_never_reported_as_differing(self) -> None:
        # `expected and hash matches and NOT referenced` — so a file whose hash matches
        # EXACTLY falls through the moment the project mentions it, and was then told
        # "current hash differs from recorded install hash".
        import hashlib

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            body = "# programmer\n"
            _seed(root, ".docs/agents/programmer.md", body)
            _seed(root, "docs/notes.md", "see .docs/agents/programmer.md\n")
            _manifest(root, {".docs/agents/programmer.md":
                             hashlib.sha256(body.encode()).hexdigest()})

            items = {i.path: i for i in build_removal_plan(root).items}

            item = items[".docs/agents/programmer.md"]
            joined = " ".join(item.evidence)
            self.assertNotIn("differs", joined, item.evidence)
            self.assertIn("still matches", joined, item.evidence)
            self.assertNotEqual(item.classification, "kit-owned-modified")

    def test_a_genuinely_modified_file_is_still_reported_as_differing(self) -> None:
        import hashlib

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, ".docs/agents/programmer.md", "# edited by the operator\n")
            _manifest(root, {".docs/agents/programmer.md":
                             hashlib.sha256(b"# programmer\n").hexdigest()})

            item = {i.path: i for i in build_removal_plan(root).items}[
                ".docs/agents/programmer.md"]

            self.assertIn("differs", " ".join(item.evidence))
            self.assertEqual(item.classification, "kit-owned-modified")


class SeededAccessControlIsNotCleanupTest(unittest.TestCase):
    """`.credentials/.gitignore` is the rule keeping real tokens out of git."""

    def test_the_seeded_gitignore_is_never_removed_unreviewed(self) -> None:
        import hashlib
        import json as _json
        import unittest.mock as _mock

        body = "*\n!.gitignore\n!README*\n!*.example\n"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, ".credentials/.gitignore", body)
            (root / ".gk").mkdir(parents=True, exist_ok=True)
            (root / ".gk" / "manifest.json").write_text(
                _json.dumps({"state_version": 1, "files": {}}), encoding="utf-8")

            with _mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value={".gitignore": (hashlib.sha256(body.encode()).hexdigest(),)},
            ):
                item = {i.path: i for i in build_removal_plan(root).items}[
                    ".credentials/.gitignore"]

            self.assertNotEqual(item.action, "remove", item.evidence)
            self.assertTrue(item.requires_operator_review)
            self.assertIn("out of git", " ".join(item.evidence))


class LegacyRecordIsNotDestroyedByAnOrdinaryCommandTest(unittest.TestCase):
    """The reader honoured "absent ≠ empty"; the writer stamped `[]` one command later."""

    def test_an_empty_recorded_list_is_treated_as_no_record(self) -> None:
        import json as _json
        from governancekit.remove_agents import _recorded_seeded_names

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".gk").mkdir(parents=True)
            (root / ".gk" / "manifest.json").write_text(
                _json.dumps({"state_version": 1, "files": {}, "seeded_credentials": []}),
                encoding="utf-8")

            self.assertIsNone(_recorded_seeded_names(root))

    def test_write_state_does_not_stamp_an_empty_key(self) -> None:
        import json as _json
        from governancekit import install_agents as ia

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ia._write_state(root, [], repo="r", ref="v1", metadata={}, seeded=[])

            state = _json.loads((root / ".gk" / "manifest.json").read_text())
            self.assertNotIn("seeded_credentials", state)

    def test_a_target_seeded_by_an_EARLIER_release_is_still_recognised(self) -> None:
        # A target keeps the bytes it was seeded with for ever: the installer never
        # replaces an existing file there and the upgrade branch never seeds. Matching
        # only the pinned release left that population with the kit's own files on disk
        # after de-adoption — the exact symptom, measured against a file that really
        # did change between releases.
        import hashlib
        import unittest.mock as _mock

        older = "{}\n"
        newer = "{ }\n"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, ".credentials/identity.json.example", older)
            _manifest(root, {})

            history = (
                hashlib.sha256(newer.encode()).hexdigest(),   # the pinned release
                hashlib.sha256(older.encode()).hexdigest(),   # the one before it
            )
            with _mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value={"identity.json.example": history},
            ):
                item = {i.path: i for i in build_removal_plan(root).items}[
                    ".credentials/identity.json.example"]

            self.assertEqual(item.action, "remove", item.evidence)

    def test_a_string_valued_table_is_refused_instead_of_matching_a_prefix(self) -> None:
        # `"a" in "abc"` is substring matching. A table of strings rather than tuples
        # would accept a PREFIX of a digest as proof — caught in review of this change,
        # where the tests themselves mocked strings and passed for the wrong reason.
        import hashlib
        import unittest.mock as _mock

        body = "{}\n"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, ".credentials/identity.json.example", body)
            _manifest(root, {})

            with _mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value={"identity.json.example":
                              hashlib.sha256(body.encode()).hexdigest()},
            ):
                items = {i.path: i for i in build_removal_plan(root).items}

            item = items.get(".credentials/identity.json.example")
            if item is not None:
                self.assertNotEqual(item.action, "remove", item.evidence)


class TheRealSnapshotIsExercisedTest(unittest.TestCase):
    """Every other credential test mocks the digest table. That is what let a whole
    population through: nothing compared the SHIPPED snapshot against a real target."""

    def test_the_shipped_snapshot_recognises_the_release_it_pins(self) -> None:
        from governancekit.remove_agents import _seeded_credential_digests

        table = _seeded_credential_digests()
        self.assertTrue(table, "the shipped snapshot carries no credential digests")
        for name, digests in table.items():
            self.assertIsInstance(digests, tuple, f"{name} must carry a history")
            self.assertTrue(all(len(d) == 64 for d in digests), name)


class TheDigestHistoryIsLoadBearingTest(unittest.TestCase):
    """The property that carries AC-5, and that no test asserted.

    A council mutated the history back to a single digest and the WHOLE suite stayed
    green: the four `.credentials/` tests mock the table, and the `kit_drift` tests
    cover absence, malformed input and the old single-string shape — a truncation to
    one element satisfies all three. Every target adopted before those bytes last
    changed would have become unremovable residue again, silently.

    Two directions on purpose: matching only the newest element and matching only the
    oldest are different mutations, and one test cannot catch both.
    """

    def _plan_with(self, body: str, history: tuple[str, ...]) -> str:
        import unittest.mock as _mock

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, ".credentials/identity.json.example", body)
            _manifest(root, {})
            with _mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value={"identity.json.example": history},
            ):
                items = {i.path: i for i in build_removal_plan(root).items}
            return items[".credentials/identity.json.example"].action

    def test_a_match_on_the_OLDEST_digest_is_recognised(self) -> None:
        import hashlib

        older, newer = "{}\n", "{ }\n"
        history = (
            hashlib.sha256(newer.encode()).hexdigest(),   # newest first
            hashlib.sha256(older.encode()).hexdigest(),
        )
        self.assertEqual(self._plan_with(older, history), "remove")

    def test_a_match_on_the_NEWEST_digest_is_recognised(self) -> None:
        import hashlib

        older, newer = "{}\n", "{ }\n"
        history = (
            hashlib.sha256(newer.encode()).hexdigest(),
            hashlib.sha256(older.encode()).hexdigest(),
        )
        self.assertEqual(self._plan_with(newer, history), "remove")

    def test_the_SHIPPED_snapshot_really_carries_a_history(self) -> None:
        # Unmocked, against the real package. Every other credential test patches the
        # table, which is what let the whole earlier-release population through: a mock
        # proves the comparison works and says nothing about the table being complete.
        from governancekit.remove_agents import _seeded_credential_digests

        table = _seeded_credential_digests()

        self.assertTrue(table, "the shipped snapshot carries no credential digests")
        multi = {n: d for n, d in table.items() if len(d) > 1}
        self.assertTrue(
            multi,
            "no name carries more than one digest — either the derivation across "
            "KNOWN_TARBALL_SHA256 broke, or the history was truncated",
        )


class TheFailClosedWarningIsPrintedOncePerRunTest(unittest.TestCase):
    """It was printed once per CANDIDATE: 75 blocks and 17 KB on a realistic target."""

    def test_the_missing_snapshot_warning_appears_once(self) -> None:
        import contextlib as _ctx
        import io as _io
        import unittest.mock as _mock

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("README.md", "identity.json.example", "jira.json.example"):
                _seed(root, f".credentials/{name}", "x\n")
            for i in range(12):
                _seed(root, f".docs/agents/doc{i}.md", "x\n")
            _manifest(root, {})

            buffer = _io.StringIO()
            with _mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value={},
            ), _ctx.redirect_stdout(buffer):
                build_removal_plan(root)

            self.assertEqual(
                buffer.getvalue().count("no kit snapshot digests"), 1,
                buffer.getvalue()[:400],
            )


class TheSharedManifestCannotReachCredentialsTest(unittest.TestCase):
    """AC-25 — the worst finding of this council.

    `_candidate_paths` started at `set(manifest)`, and the manifest is the SHARED,
    committed half of the state. An entry planted by a teammate made the operator's
    private key directory a candidate; with `--with-llm` the planner read the file and
    handed its CONTENT to the extractor, which sent it to the provider — the same
    provider whose key was being read. `_configured_llm`'s docstring says "never its
    secret": the code avoided leaking it as a credential and shipped it as content.
    """

    SECRET = "REAL-OPERATOR-TOKEN-DO-NOT-SEND-ANYWHERE"

    def _poisoned(self, root: Path) -> None:
        import hashlib
        import json as _json

        _seed(root, ".credentials/llm/openrouter.key", self.SECRET + "\n")
        _seed(root, ".credentials/identity.json",
              '{"operator":"Esteban Calegari","id":"REDACTED"}\n')
        (root / ".gk").mkdir(parents=True, exist_ok=True)
        (root / ".gk" / "manifest.json").write_text(_json.dumps({
            "state_version": 1,
            "files": {
                # A hash the attacker cannot know — which is the point: the mismatch is
                # what routed the file into the branch that READS it.
                ".credentials/llm/openrouter.key": hashlib.sha256(b"whatever").hexdigest(),
                ".credentials/identity.json": hashlib.sha256(b"whatever").hexdigest(),
            },
        }), encoding="utf-8")

    def test_a_planted_manifest_entry_cannot_make_a_key_a_candidate(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._poisoned(root)

            paths = [i.path for i in build_removal_plan(root).items]

            self.assertNotIn(".credentials/llm/openrouter.key", paths)
            self.assertNotIn(".credentials/identity.json", paths)

    def test_no_credential_content_ever_reaches_the_extractor(self) -> None:
        # The layer that exists because the first layer failed once.
        seen: list[str] = []

        def _spy(root: Path, rel: str, content: str, provider: dict) -> tuple:
            seen.append(content)
            return ("", "", 0.0)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._poisoned(root)
            (root / ".gk" / "project-config.json").write_text(
                '{"providers": [{"name": "openrouter", "role": "primary", '
                '"mode": "file-ref", "credential_ref": ".credentials/llm/openrouter.key", '
                '"base_url": "https://openrouter.ai/api/v1", "model": "x"}]}',
                encoding="utf-8")

            build_removal_plan(root, with_llm=True, extractor=_spy)

            self.assertFalse(
                any(self.SECRET in payload for payload in seen),
                "the operator's API key was handed to the extractor",
            )
            self.assertFalse(any("id" in payload for payload in seen))

    def test_the_plausibility_guard_refuses_that_directory(self) -> None:
        from governancekit.remove_agents import _is_kit_installable

        # It answered "yes, plausible" for the private key directory, because the
        # installer seeds `.credentials/` and the guard matches by prefix. Kit
        # authorship there is proved by bytes, never by a path claim.
        self.assertFalse(_is_kit_installable(".credentials/llm/openrouter.key"))
        self.assertFalse(_is_kit_installable(".credentials/identity.json"))
        self.assertFalse(_is_kit_installable(".credentials"))

    def test_the_seeded_scaffolding_is_still_reachable(self) -> None:
        # The door that must stay open: the snapshot table, and only it.
        import hashlib
        import unittest.mock as _mock

        body = "how to put tokens here\n"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, ".credentials/README.md", body)
            _manifest(root, {})

            with _mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value={"README.md": (hashlib.sha256(body.encode()).hexdigest(),)},
            ):
                paths = [i.path for i in build_removal_plan(root).items]

            self.assertIn(".credentials/README.md", paths)


class TheExtractorGuardHoldsWhenSelectionFailsTest(unittest.TestCase):
    """The second layer is load-bearing exactly when the first one is not.

    A mutation that reopens the candidate set is caught by the test above; a mutation
    that removes THIS guard is invisible while the first layer holds — which is the
    definition of a guard that only matters after a regression. So the regression is
    simulated: `_candidate_paths` is forced to offer the path, as it did before AC-25.
    """

    SECRET = "REAL-OPERATOR-TOKEN-DO-NOT-SEND-ANYWHERE"

    def test_no_credential_content_reaches_the_extractor_even_if_selection_offers_it(self) -> None:
        import hashlib
        import json as _json
        import unittest.mock as _mock

        seen: list[str] = []

        def _spy(root: Path, rel: str, content: str, provider: dict) -> tuple:
            seen.append(content)
            return ("", "", 0.0)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, ".credentials/llm/openrouter.key", self.SECRET + "\n")
            (root / ".gk").mkdir(parents=True, exist_ok=True)
            (root / ".gk" / "manifest.json").write_text(_json.dumps({
                "state_version": 1,
                "files": {".credentials/llm/openrouter.key":
                          hashlib.sha256(b"whatever").hexdigest()},
            }), encoding="utf-8")
            (root / ".gk" / "project-config.json").write_text(
                '{"providers": [{"name": "openrouter", "role": "primary", '
                '"mode": "file-ref", "credential_ref": ".credentials/llm/openrouter.key", '
                '"base_url": "https://openrouter.ai/api/v1", "model": "x"}]}',
                encoding="utf-8")

            # Simulate the first layer regressing: selection offers the path again.
            with _mock.patch(
                "governancekit.remove_agents._candidate_paths",
                return_value=[".credentials/llm/openrouter.key"],
            ):
                build_removal_plan(root, with_llm=True, extractor=_spy)

            self.assertEqual(
                seen, [],
                "the extractor was handed content from .credentials/ — the second "
                "layer exists for precisely this case",
            )


class SpellingCannotDefeatTheCredentialGuardTest(unittest.TestCase):
    """The first cut of AC-25 was walked through with two extra characters.

    Layers 1 and 3 compared the RAW manifest string with `startswith`, and the
    filesystem normalises what the string does not: `./.credentials/llm/openrouter.key`
    is the same file and does not start with `.credentials/`. Both guards missed it
    together, because they were the same comparison written twice.
    """

    SECRET = "REAL-OPERATOR-TOKEN-DO-NOT-SEND-ANYWHERE"

    SPELLINGS = (
        ".credentials/llm/openrouter.key",
        "./.credentials/llm/openrouter.key",
        ".//.credentials/llm/openrouter.key",
        ".credentials/./llm/openrouter.key",
        ".credentials/../.credentials/llm/openrouter.key",
    )

    def _target(self, root: Path, spelling: str) -> None:
        import hashlib
        import json as _json

        _seed(root, ".credentials/llm/openrouter.key", self.SECRET + "\n")
        (root / ".gk").mkdir(parents=True, exist_ok=True)
        (root / ".gk" / "manifest.json").write_text(_json.dumps({
            "state_version": 1,
            "files": {spelling: hashlib.sha256(b"whatever").hexdigest()},
        }), encoding="utf-8")
        (root / ".gk" / "project-config.json").write_text(
            '{"providers": [{"name": "openrouter", "role": "primary", '
            '"mode": "file-ref", "credential_ref": ".credentials/llm/openrouter.key", '
            '"base_url": "https://openrouter.ai/api/v1", "model": "x"}]}',
            encoding="utf-8")

    def test_no_spelling_of_the_path_reaches_the_extractor(self) -> None:
        for spelling in self.SPELLINGS:
            with self.subTest(spelling=spelling):
                seen: list[str] = []

                def _spy(root: Path, rel: str, content: str, provider: dict) -> tuple:
                    seen.append(content)
                    return ("", "", 0.0)

                with TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    self._target(root, spelling)

                    build_removal_plan(root, with_llm=True, extractor=_spy)

                    self.assertFalse(
                        any(self.SECRET in payload for payload in seen),
                        f"the key leaked through the spelling {spelling!r}",
                    )

    def test_no_spelling_of_the_path_becomes_a_candidate(self) -> None:
        for spelling in self.SPELLINGS:
            with self.subTest(spelling=spelling):
                with TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    self._target(root, spelling)

                    paths = [i.path for i in build_removal_plan(root).items]

                    self.assertNotIn(spelling, paths)
                    self.assertNotIn(".credentials/llm/openrouter.key", paths)

    def test_an_absolute_entry_pointing_back_inside_is_caught(self) -> None:
        import hashlib
        import json as _json

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, ".credentials/llm/openrouter.key", self.SECRET + "\n")
            absolute = str((root / ".credentials" / "llm" / "openrouter.key").resolve())
            (root / ".gk").mkdir(parents=True, exist_ok=True)
            (root / ".gk" / "manifest.json").write_text(_json.dumps({
                "state_version": 1,
                "files": {absolute: hashlib.sha256(b"whatever").hexdigest()},
            }), encoding="utf-8")

            paths = [i.path for i in build_removal_plan(root).items]

            self.assertNotIn(absolute, paths)

    def test_a_neighbouring_name_is_not_swept_up(self) -> None:
        # The guard must not be so eager that it eats a real project directory.
        from governancekit.remove_agents import _under_credentials

        for innocent in ("docs/x", ".credentialsX/x", "..credentials/x", "credentials/x"):
            self.assertFalse(_under_credentials(innocent), innocent)


class TheGuardWorksWithoutARootToResolveAgainstTest(unittest.TestCase):
    """`_is_kit_installable` has no root, so string normalisation is all it has.

    A mutation that reverted the guard to a raw `startswith` stayed GREEN: every
    spelling test passes a root, and resolution catches them all on its own. The
    normalisation branch is load-bearing exactly where there is nothing to resolve —
    and that is the branch that decides whether a poisoned manifest entry with a
    matching hash can be deleted without review.
    """

    def test_every_spelling_is_refused_with_no_root(self) -> None:
        from governancekit.remove_agents import _under_credentials

        for spelling in (
            ".credentials/llm/openrouter.key",
            "./.credentials/llm/openrouter.key",
            ".//.credentials/llm/openrouter.key",
            ".credentials/./llm/openrouter.key",
            ".credentials/../.credentials/llm/openrouter.key",
            ".credentials",
            "./.credentials",
        ):
            with self.subTest(spelling=spelling):
                self.assertTrue(_under_credentials(spelling), spelling)

    def test_the_plausibility_guard_refuses_every_spelling(self) -> None:
        from governancekit.remove_agents import _is_kit_installable

        for spelling in (
            ".credentials/llm/openrouter.key",
            "./.credentials/llm/openrouter.key",
            ".credentials/../.credentials/identity.json",
        ):
            with self.subTest(spelling=spelling):
                self.assertFalse(_is_kit_installable(spelling), spelling)

    def test_a_path_that_cannot_be_resolved_is_refused_not_allowed(self) -> None:
        # "I cannot tell" is not a reason to let something through, and this is the
        # guard on the operator's private key directory.
        import unittest.mock as _mock
        from governancekit.remove_agents import _under_credentials

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with _mock.patch.object(
                Path, "resolve", side_effect=OSError("cannot resolve")
            ):
                self.assertTrue(_under_credentials("docs/whatever.md", root))


class TheManifestClaimIsDroppedAtTheSourceTest(unittest.TestCase):
    """Filtering only the CANDIDATE set left the claim alive in the manifest dict.

    The loop reads `expected = manifest.get(rel)` off that dict, so a claim the
    selection had just refused was still honoured for classification. Three lenses
    measured the same consequence from different directions — a legacy target losing
    its removal and being told its own genuine record was forged, and a planted
    canonical entry making the scaffolding permanently un-removable.
    """

    def _legacy_target(self, root: Path) -> dict:
        import hashlib
        import json as _json
        import unittest.mock as _mock

        bodies = {
            "README.md": "how to put tokens here\n",
            "identity.json.example": "{}\n",
        }
        files = {}
        for name, body in bodies.items():
            _seed(root, f".credentials/{name}", body)
            # A LEGACY manifest: `_write_state` really hashed this directory into
            # `files` until the writer learned not to.
            files[f".credentials/{name}"] = hashlib.sha256(body.encode()).hexdigest()
        (root / ".gk").mkdir(parents=True, exist_ok=True)
        (root / ".gk" / "manifest.json").write_text(
            _json.dumps({"state_version": 1, "files": files}), encoding="utf-8")
        return {n: (hashlib.sha256(b.encode()).hexdigest(),) for n, b in bodies.items()}

    def test_a_legacy_manifest_entry_does_not_block_removal(self) -> None:
        import unittest.mock as _mock

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            digests = self._legacy_target(root)

            with _mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value=digests,
            ):
                items = {i.path: i for i in build_removal_plan(root).items}

            item = items[".credentials/README.md"]
            self.assertEqual(item.action, "remove", item.evidence)
            self.assertEqual(item.classification, "kit-seeded-unchanged")

    def test_no_evidence_calls_a_genuine_installer_record_forged(self) -> None:
        import unittest.mock as _mock

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            digests = self._legacy_target(root)

            with _mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value=digests,
            ):
                items = {i.path: i for i in build_removal_plan(root).items}

            for rel, item in items.items():
                if rel.startswith(".credentials/"):
                    self.assertNotIn(
                        "poisoned claim", " ".join(item.evidence),
                        f"{rel}: the installer's own record was called forged",
                    )

    def test_a_planted_canonical_entry_cannot_make_scaffolding_unremovable(self) -> None:
        # The digest is public — the file ships in the release — so anyone can plant a
        # canonical entry with a MATCHING hash. Denial through the channel this issue
        # exists to declare untrusted.
        import unittest.mock as _mock

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            digests = self._legacy_target(root)

            with _mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value=digests,
            ):
                items = {i.path: i for i in build_removal_plan(root).items}

            self.assertEqual(items[".credentials/README.md"].action, "remove")

    def test_the_manifest_reader_drops_the_claim_itself(self) -> None:
        from governancekit.remove_agents import _manifest_files

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._legacy_target(root)

            self.assertEqual(
                [k for k in _manifest_files(root) if "credentials" in k], [],
                "the claim must be dropped once, at the source",
            )
