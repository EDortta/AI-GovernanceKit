"""`configure` must be able to do what `doctor` sends the operator to do.

`doctor`'s `unfilled placeholders` check is non-advisory and names `configure` as
the remedy. Before this, on any run without a terminal, `configure` filled
nothing and reported the token still unfilled — while the answer sat in
`.governancekit-identity.json`, a file the same command had just written. Advice
in a loop, with no way out.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent


def _target(tmp: Path, *, operator: str | None) -> Path:
    (tmp / "AGENTS.md").write_text(
        "# Contract\n\nToda mensagem ao operador ({{OPERATOR_NAME}}) começa com "
        "\"{{OPERATOR_NAME}}, \".\n",
        encoding="utf-8",
    )
    if operator is not None:
        (tmp / ".governancekit-identity.json").write_text(
            json.dumps(
                {
                    "operator_name": operator,
                    "host_id": "testhost",
                    "instance_path": str(tmp),
                }
            ),
            encoding="utf-8",
        )
    return tmp


def _configure(root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "governancekit.cli", "--root", str(root), "configure", *extra],
        capture_output=True,
        text=True,
        cwd=ROOT,
        stdin=subprocess.DEVNULL,  # no TTY: the condition the defect needed
    )


class ConfigureIsBackedByStoredIdentityTest(unittest.TestCase):
    def test_the_stored_operator_name_fills_the_token_without_a_terminal(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _target(Path(tmp), operator="Esteban D.Dortta")
            completed = _configure(root)
            text = (root / "AGENTS.md").read_text(encoding="utf-8")

        self.assertNotIn("{{OPERATOR_NAME}}", text, completed.stdout + completed.stderr)
        self.assertIn("Esteban D.Dortta", text)

    def test_an_explicit_set_still_wins_over_the_stored_identity(self) -> None:
        """The identity is a default, not an override — otherwise --set becomes a lie."""
        with TemporaryDirectory() as tmp:
            root = _target(Path(tmp), operator="Stored Name")
            _configure(root, "--set", "OPERATOR_NAME=Explicit Name")
            text = (root / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("Explicit Name", text)
        self.assertNotIn("Stored Name", text)

    def test_the_unfilled_report_names_the_form_the_files_actually_contain(self) -> None:
        """Issue #7 item 3 reconciled the syntax everywhere except the one line an
        operator reads to learn what to look for. `[OPERATOR_NAME]` greps to nothing."""
        with TemporaryDirectory() as tmp:
            root = _target(Path(tmp), operator=None)
            completed = _configure(root)

        self.assertIn("{{OPERATOR_NAME}}", completed.stdout, completed.stdout)
        self.assertNotIn("[OPERATOR_NAME]", completed.stdout)


if __name__ == "__main__":
    unittest.main()


class ConfigurePersistsAnswersTest(unittest.TestCase):
    """Round 2: the fix for `configure` freezing a protected file was forward-only.

    A target configured before answers were persisted has its files already rendered,
    so the scan finds no token, `run_configure` returned early, and nothing was ever
    recorded — leaving the source un-rendered on every future upgrade and the
    protected file drifted for good. Re-running the command the operator is told to
    run has to be the way back.
    """

    def test_an_explicit_set_is_recorded_even_when_no_token_remains(self) -> None:
        from governancekit.configure import run_configure
        from governancekit.install_agents import _read_state, _state_metadata

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Already rendered by the old `configure`: no {{TOKEN}} left anywhere.
            (root / "AGENTS.md").write_text("# kit Esteban\n", encoding="utf-8")

            run_configure(root, preset={"OPERATOR_NAME": "Esteban"}, interactive=False)

            self.assertEqual(
                _state_metadata(_read_state(root)).get("OPERATOR_NAME"), "Esteban"
            )
