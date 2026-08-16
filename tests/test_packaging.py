"""Data files the runtime reads must survive a build. Proven against a real wheel.

Two council lenses found this independently: `_llm_catalog.json` was added next to the
code, every test passed from the source tree, and a `pip install` of the result could
not import `scope_conversation` at all — the catalog was not in `package-data`, and the
module resolved its presets at import time, so a missing data file became an
unimportable module.

The check builds the distribution rather than reading `pyproject.toml`, because the
question is not "is the line there" but "does the file arrive".
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Every file `governancekit` reads from its own package directory at runtime.
RUNTIME_DATA = ("_kit_snapshot.json", "_llm_catalog.json")


def _build_wheel(dest: Path) -> Path | None:
    """Build into *dest* from a copy, so nothing in the worktree is touched."""
    stage = dest / "src"
    stage.mkdir()
    shutil.copytree(ROOT / "governancekit", stage / "governancekit")
    for name in ("pyproject.toml", "README.md"):
        if (ROOT / name).is_file():
            shutil.copy2(ROOT / name, stage / name)
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", str(dest)],
            cwd=stage, capture_output=True, timeout=300, text=True,
            env={**os.environ, "PIP_REQUIRE_VIRTUALENV": "false"},
        )
    except (subprocess.TimeoutExpired, OSError):
        return None  # pip genuinely unavailable: skip, not fail
    if completed.returncode != 0:
        # A build that RAN and failed is a result, not an absence. Skipping here would
        # hide exactly what this test exists to catch — a broken `pyproject.toml`.
        raise AssertionError(
            "pip wheel failed; the distribution does not build:\n"
            + (completed.stderr or completed.stdout)[-2000:]
        )
    wheels = sorted(dest.glob("*.whl"))
    return wheels[0] if wheels else None


class PackagedDataTest(unittest.TestCase):
    def test_every_runtime_data_file_is_declared_in_package_data(self) -> None:
        # Cheap and offline: the declaration must at least name each file.
        declared = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        for name in RUNTIME_DATA:
            self.assertIn(name, declared, f"{name} is not in package-data")

    def test_the_built_wheel_carries_them(self) -> None:
        # The real question. Mutation: drop `_llm_catalog.json` from package-data → red.
        with tempfile.TemporaryDirectory() as tmp:
            wheel = _build_wheel(Path(tmp))
            if wheel is None:
                self.skipTest("pip wheel unavailable in this environment")
            with zipfile.ZipFile(wheel) as archive:
                shipped = {Path(name).name for name in archive.namelist()}
            for name in RUNTIME_DATA:
                self.assertIn(name, shipped, f"{name} is missing from {wheel.name}")

    def test_a_missing_catalog_does_not_make_a_module_unimportable(self) -> None:
        # Defence in depth for the same failure: even correctly packaged, a data file
        # that cannot be read must degrade, not take the interview down with it.
        from governancekit import llm_catalog, scope_conversation

        def _raise(*_args, **_kwargs):
            raise llm_catalog.CatalogError("simulated missing catalog")

        original = llm_catalog.presets
        llm_catalog.presets = _raise
        try:
            self.assertEqual(scope_conversation._llm_presets(), {})
        finally:
            llm_catalog.presets = original


if __name__ == "__main__":
    unittest.main()
