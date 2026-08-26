"""Fase 1 da épica 014 — as dissoluções: AC-20 e AC-13, um teste cada.

The PLANO-UNIFICADO predicted that the `manifest.override.json` split would shrink
AC-20, AC-22 and AC-13 from three fixes into one test each, asserting the property
the split exists for: nothing of the operator's reaches the committed file. This
module carries AC-20 and AC-13; AC-22's test lives with the routing it verifies,
in `test_manifest_override.py` (`LocalRenderedHashRoutingTests`,
`StickyProvenanceTests`).

Each test is the ISSUE's reproduction, inverted: the exact input that used to leak
now provably does not.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from governancekit import install_agents as ia
from governancekit.configure import run_configure


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class AC20SharedManifestCarriesThirdPartyDataTest(unittest.TestCase):
    """AC-20 — a colleague's personal and financial data, committed into the shared
    manifest, must not enter this machine's render table nor survive the next write.

    The issue's scenario: a teammate's manifest arrives by `git pull` carrying
    their OPERATOR_NAME and PIX data. The victim upgrades. Three doors mattered:
    the logical state, the render table (what reaches files), and the next write.
    """

    def test_inherited_personal_data_reaches_no_render_and_no_next_write(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_json(
                root / ia._STATE_FILE,
                {"state_version": 1, "repo": "r", "ref": "v1", "files": {},
                 "metadata": {
                     "ORG_NAME": "ACME",  # legitimate shared context, must survive
                     "OPERATOR_NAME": "COLEGA FULANO",
                     "SMTP_ACCOUNT": "colega@example.org",
                     "PIX_HOLDER_NAME": "COLEGA FULANO DE TAL",
                     "PIX_PAYLOAD": "00020126PIXDOCOLEGA",
                 }},
            )

            # Door 1 — the logical state: operator-local names are filtered on read.
            state_meta = ia._state_metadata(ia._read_state(root))
            self.assertNotIn("OPERATOR_NAME", state_meta)
            self.assertNotIn("SMTP_ACCOUNT", state_meta)
            self.assertEqual(state_meta["ORG_NAME"], "ACME")

            # Door 2 — the render table (the ONE table all three writers use,
            # AC-23): the withdrawn donation slots are not declared, so even the
            # values that pass the read filter can never reach a file.
            table, _refused = ia._render_table(state_meta)
            self.assertNotIn("PIX_HOLDER_NAME", table)
            self.assertNotIn("PIX_PAYLOAD", table)
            self.assertNotIn("OPERATOR_NAME", table)
            self.assertEqual(table.get("ORG_NAME"), "ACME")

            # Door 3 — the next write: discarded names are dropped (and said),
            # inherited operator names never return to the tracked half.
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                ia._write_state(root, [], repo="r", ref="v1", metadata={})
            manifest_text = (root / ia._STATE_FILE).read_text(encoding="utf-8")
            for leaked in ("COLEGA FULANO DE TAL", "00020126PIXDOCOLEGA",
                           "PIX_HOLDER_NAME", "PIX_PAYLOAD", "OPERATOR_NAME"):
                self.assertNotIn(leaked, manifest_text)
            self.assertIn("ACME", manifest_text)
            self.assertIn("dropped", out.getvalue())


class AC13ConfigureSetCannotReachTheTrackedManifestTest(unittest.TestCase):
    """AC-13 — `configure --set DB_PASSWORD=hunter2` on a rendered target used to
    print `nothing to configure`, exit 0, and write the secret into the TRACKED
    manifest. The gate now runs unconditionally; this fixes the issue's own repro.
    """

    def test_an_undeclared_key_is_named_and_never_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            # Already rendered: no raw {{TOKEN}} anywhere — the early-return path.
            (root / "AGENTS.md").write_text("owner: ACME\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                run_configure(root, preset={"DB_PASSWORD": "hunter2"},
                              interactive=False)
            # Named as ignored — not silence, not success.
            self.assertIn("DB_PASSWORD", out.getvalue())
            # And NOTHING was written: no state file anywhere carries the value.
            gk = root / ".gk"
            if gk.exists():
                for state_file in gk.rglob("*.json"):
                    self.assertNotIn("hunter2",
                                     state_file.read_text(encoding="utf-8"))
                    self.assertNotIn("DB_PASSWORD",
                                     state_file.read_text(encoding="utf-8"))

    def test_a_declared_operator_key_lands_local_never_tracked(self) -> None:
        # The rescue path (`ade371f5#5`) must keep working — a rendered target
        # still records an explicit answer — but into the OVERRIDE, never the
        # tracked half.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text("hello Esteban\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                run_configure(root, preset={"OPERATOR_NAME": "Esteban"},
                              interactive=False)
            override = ia._read_json(root / ia._OVERRIDE_FILE)
            self.assertEqual(override["metadata"].get("OPERATOR_NAME"), "Esteban")
            manifest = ia._read_json(root / ia._STATE_FILE)
            self.assertNotIn("OPERATOR_NAME", manifest.get("metadata", {}))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
