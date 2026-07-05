from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from governancekit.doctor import _check_tracked_secret_files


def _init_repo_with_tracked_file(root: Path, rel_path: str) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    target = root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("secret\n", encoding="utf-8")
    subprocess.run(["git", "add", rel_path], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add"], cwd=root, check=True)


class TrackedSecretFilesTests(unittest.TestCase):
    def test_tracked_dotcredentials_file_fails(self) -> None:
        # SEC-0221: install_agents seeds .credentials as a FILE (not just a
        # .credentials/ directory), so the exact name must be forbidden too.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo_with_tracked_file(root, ".credentials")

            result = _check_tracked_secret_files(root)

            self.assertFalse(result.passed)
            self.assertIn(".credentials", result.message)

    def test_tracked_env_variant_fails(self) -> None:
        # SEC-0221: .env.production etc. must be caught, not just an exact ".env".
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo_with_tracked_file(root, ".env.production")

            result = _check_tracked_secret_files(root)

            self.assertFalse(result.passed)
            self.assertIn(".env.production", result.message)

    def test_unrelated_tracked_file_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo_with_tracked_file(root, "README.md")

            result = _check_tracked_secret_files(root)

            self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
