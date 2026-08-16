from __future__ import annotations

import hashlib
import json

from governancekit import cli
import unittest

import tempfile

from pathlib import Path

from governancekit.remove_agents import apply_removal_plan, build_removal_plan, write_removal_plan


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def make_installed(root, *, content: str = "kit\n"):
    target = root / ".docs" / "agents" / "programmer.md"
    target.parent.mkdir(parents=True)
    target.write_text(content, encoding="utf-8")
    state = root / ".gk"
    state.mkdir()
    (state / "manifest.json").write_text(
        json.dumps({"files": {".docs/agents/programmer.md": digest("kit\n")}}), encoding="utf-8"
    )
    return target


def test_plan_classifies_exact_manifest_file_as_removable(tmp_path) -> None:
    make_installed(tmp_path)

    plan = build_removal_plan(tmp_path)

    item = next(item for item in plan.items if item.path == ".docs/agents/programmer.md")
    assert item.classification == "kit-owned-unchanged"
    assert item.action == "remove"
    assert plan.provider["status"] == "not-invoked"


def test_plan_preserves_modified_or_unknown_files(tmp_path) -> None:
    make_installed(tmp_path, content="kit plus project decision\n")
    custom = tmp_path / ".docs" / "project-notes.md"
    custom.write_text("project content\n", encoding="utf-8")

    plan = build_removal_plan(tmp_path)
    by_path = {item.path: item for item in plan.items}

    assert by_path[".docs/agents/programmer.md"].classification == "kit-owned-modified"
    assert by_path[".docs/agents/programmer.md"].requires_operator_review
    assert by_path[".docs/project-notes.md"].classification == "unknown"
    assert by_path[".docs/project-notes.md"].action == "preserve"


def test_apply_creates_backup_before_removing_only_verified_files(tmp_path) -> None:
    target = make_installed(tmp_path)
    plan = build_removal_plan(tmp_path)

    result = apply_removal_plan(tmp_path, plan)

    assert result.removed == [".docs/agents/programmer.md"]
    assert not target.exists()
    assert (result.backup_dir / ".docs/agents/programmer.md").read_text(encoding="utf-8") == "kit\n"
    manifest = json.loads((result.backup_dir / "restore-manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"] == result.removed


def test_cli_plan_writes_json_and_apply_uses_it(tmp_path, capsys) -> None:
    make_installed(tmp_path)

    assert cli.main(["--root", str(tmp_path), "remove-agents", "plan", "--json"]) == 0
    plan_output = json.loads(capsys.readouterr().out)
    assert plan_output["plan_path"].endswith(".gk/remove-agents-plan.json")
    assert cli.main(["--root", str(tmp_path), "remove-agents", "apply", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["removed"] == [".docs/agents/programmer.md"]


def test_plan_output_cannot_escape_root(tmp_path) -> None:
    make_installed(tmp_path)
    plan = build_removal_plan(tmp_path)
    try:
        write_removal_plan(tmp_path, plan, tmp_path.parent / "escape.json")
    except Exception as exc:
        assert "outside --root" in str(exc)
    else:
        raise AssertionError("expected output outside root to be refused")


def test_llm_extraction_moves_project_content_only_after_explicit_acceptance(tmp_path) -> None:
    target = make_installed(tmp_path, content="generic kit\nLOCAL DECISION\n")
    (tmp_path / ".gk/project-config.json").write_text(
        json.dumps({"providers": [{"name": "test", "mode": "env", "credential_ref": "TEST_KEY", "base_url": "https://example.invalid/v1", "model": "test", "role": "primary"}]}),
        encoding="utf-8",
    )
    plan = build_removal_plan(
        tmp_path, with_llm=True,
        extractor=lambda *_args: ("LOCAL DECISION\n", "generic kit\n", 0.9),
    )
    item = next(item for item in plan.items if item.path == ".docs/agents/programmer.md")
    assert item.action == "extract-project-content"
    try:
        apply_removal_plan(tmp_path, plan)
    except ValueError as exc:
        assert "--accept-project-extractions" in str(exc)
    else:
        raise AssertionError("explicit acceptance must be required")
    result = apply_removal_plan(tmp_path, plan, accept_project_extractions=True)
    assert target.read_text(encoding="utf-8") == "generic kit\n"
    extracted = tmp_path / item.project_destination
    assert extracted.read_text(encoding="utf-8") == "LOCAL DECISION\n"
    assert str(item.project_destination) in (tmp_path / "docs/required-reading.md").read_text(encoding="utf-8")
    assert result.extracted == [item.project_destination]


class PlanAndApplyAgreeTest(unittest.TestCase):
    """AC-2 — `apply` removed nothing it had just printed `remove:` for.

    The plan grew a class (`kit-seeded-unchanged`) and `apply` kept filtering on the
    old one, so the operator read `remove: .credentials/README.md`, ran the apply, and
    the file was still there. It was the open QUESTION of the round that produced the
    defect — "apply do remove-agents não exercitado de ponta a ponta" — written down
    and not followed.
    """

    SEEDED = {"README.md": "how to put tokens here\n"}

    def _digests(self):
        import hashlib
        # tuples, not strings: the table is a HISTORY per name, and `x in "abc"` is
        # substring matching — a str-valued mock passes for the wrong reason.
        return {n: (hashlib.sha256(c.encode()).hexdigest(),)
                for n, c in self.SEEDED.items()}

    def test_everything_the_plan_says_remove_is_actually_removed(self) -> None:
        import hashlib
        import json
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".credentials").mkdir(parents=True)
            for name, content in self.SEEDED.items():
                (root / ".credentials" / name).write_text(content, encoding="utf-8")
            (root / "AGENTS.md").write_text("# kit\n", encoding="utf-8")
            (root / ".gk").mkdir(exist_ok=True)
            (root / ".gk" / "manifest.json").write_text(json.dumps({
                "state_version": 1,
                "seeded_credentials": list(self.SEEDED),
                "files": {
                    "AGENTS.md": hashlib.sha256(b"# kit\n").hexdigest(),
                },
            }), encoding="utf-8")

            with mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value=self._digests(),
            ):
                plan = build_removal_plan(root)
                promised = sorted(i.path for i in plan.items if i.action == "remove")
                apply_removal_plan(root, plan)

            self.assertIn(".credentials/README.md", promised)
            for rel in promised:
                self.assertFalse(
                    (root / rel).exists(),
                    f"the plan printed `remove: {rel}` and the apply left it on disk",
                )

    def test_nothing_the_plan_preserves_is_touched(self) -> None:
        import json
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".credentials").mkdir(parents=True)
            (root / ".credentials" / "identity.json").write_text("{}\n", encoding="utf-8")
            (root / ".gk").mkdir(exist_ok=True)
            (root / ".gk" / "manifest.json").write_text(
                json.dumps({"state_version": 1, "files": {}}), encoding="utf-8"
            )

            with mock.patch(
                "governancekit.remove_agents._seeded_credential_digests",
                return_value=self._digests(),
            ):
                plan = build_removal_plan(root)
                apply_removal_plan(root, plan)

            self.assertTrue((root / ".credentials" / "identity.json").exists())


class APlanFromAnotherVersionIsRefusedTest(unittest.TestCase):
    """A plan written before AC-2/AC-3 records the OLD branches' verdicts.

    Under the previous code that plan was a no-op; under this one `apply` deletes.
    Its `.credentials/README.md` entry carries `matches the file this kit seeds, byte
    for byte` — the string AC-3 exists to abolish — for a file nobody compared, and
    `apply` used to trust it verbatim. Changing what a persisted artefact MEANS
    without versioning it is the defect AC-12 names.
    """

    def test_a_plan_written_by_an_older_kit_is_refused_by_name(self) -> None:
        import json
        from governancekit.remove_agents import PLAN_VERSION, load_removal_plan

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".gk").mkdir(parents=True)
            # The literal 2, not `PLAN_VERSION - 1`: a relative version always
            # mismatches, so the test passed under a mutation that put the version
            # back where it was. It has to name the release whose plans must be
            # refused, which is the one that wrote the false evidence string.
            self.assertGreater(PLAN_VERSION, 2, "plans from v2 must stay refused")
            (root / ".gk" / "remove-agents-plan.json").write_text(json.dumps({
                "schema_version": 2,
                "root": str(root.resolve()),
                "created_at": "2026-08-12T00:00:00+00:00",
                "items": [],
            }), encoding="utf-8")

            with self.assertRaises(ValueError) as caught:
                load_removal_plan(root)

            message = str(caught.exception)
            self.assertIn("another version of the kit", message)
            self.assertNotIn("project root", message,
                             "a version mismatch used to be blamed on the root")

    def test_a_current_plan_still_loads(self) -> None:
        from governancekit.remove_agents import load_removal_plan, write_removal_plan

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("# kit\n", encoding="utf-8")
            plan = build_removal_plan(root)
            write_removal_plan(root, plan)

            self.assertEqual(load_removal_plan(root).schema_version, plan.schema_version)
