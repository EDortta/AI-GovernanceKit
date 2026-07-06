from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from governancekit.doctor import _check_gitignore_secrets


def _init_repo(root: Path, gitignore: str | None) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    if gitignore is not None:
        (root / ".gitignore").write_text(gitignore, encoding="utf-8")


class GitignoreSecretsTests(unittest.TestCase):
    def test_covering_gitignore_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo(root, ".env\n.credentials/\n")

            result = _check_gitignore_secrets(root)

            self.assertTrue(result.passed, result.message)

    def test_env_variant_glob_still_covers_dotenv(self) -> None:
        # A broad `.env*` (or `*.env`) glob must satisfy the .env probe.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo(root, ".env*\n.credentials/\n")

            result = _check_gitignore_secrets(root)

            self.assertTrue(result.passed, result.message)

    def test_missing_credentials_pattern_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo(root, ".env\n")  # .credentials/ NOT ignored

            result = _check_gitignore_secrets(root)

            self.assertFalse(result.passed)
            self.assertIn(".credentials", result.message)

    def test_no_gitignore_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo(root, None)

            result = _check_gitignore_secrets(root)

            self.assertFalse(result.passed)

    def test_non_git_directory_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)  # no git init

            result = _check_gitignore_secrets(root)

            self.assertTrue(result.passed)
            self.assertIn("not a git repository", result.message)


if __name__ == "__main__":
    unittest.main()
