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
    _add_tracked_file(root, rel_path)


def _add_tracked_file(root: Path, rel_path: str) -> None:
    """Track one more file in an already-initialised repo."""
    target = root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("secret\n", encoding="utf-8")
    subprocess.run(["git", "add", "-f", rel_path], cwd=root, check=True)
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

    # --- templates are not secrets (WK-20260717-doctor-false-positives) ---
    # The kit itself ships `.credentials/*.example` + READMEs, and projects ship
    # `.env.example`. Failing them taught the operator to ignore the FAIL line.
    # The twin gate (AI-Agents `scripts/run-checks.sh` §4) already excludes them.

    def test_env_example_is_not_a_tracked_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo_with_tracked_file(root, ".env.example")

            result = _check_tracked_secret_files(root)

            self.assertTrue(result.passed, result.message)

    def test_nested_env_example_is_not_a_tracked_secret(self) -> None:
        # Observed in the wild: wa-hub-client/.env.example (AcheiVc, 2026-07-17).
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo_with_tracked_file(root, "client/.env.example")

            result = _check_tracked_secret_files(root)

            self.assertTrue(result.passed, result.message)

    def test_credentials_example_is_not_a_tracked_secret(self) -> None:
        # The kit's own `_FRESH_PATHS` seeds `.credentials/` with these.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo_with_tracked_file(root, ".credentials/secret.token.example")

            result = _check_tracked_secret_files(root)

            self.assertTrue(result.passed, result.message)

    def test_credentials_readme_and_gitignore_are_not_tracked_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo_with_tracked_file(root, ".credentials/README.md")
            _add_tracked_file(root, ".credentials/.gitignore")

            result = _check_tracked_secret_files(root)

            self.assertTrue(result.passed, result.message)

    def test_credentials_translated_readme_is_not_a_tracked_secret(self) -> None:
        # The kit ships .credentials/README-ptbr.md and README-es.md; the exact
        # name "README.md" is not enough — the AI-Agents source repo trips it.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo_with_tracked_file(root, ".credentials/README-ptbr.md")
            _add_tracked_file(root, ".credentials/README-es.md")

            result = _check_tracked_secret_files(root)

            self.assertTrue(result.passed, result.message)

    # --- guards against loosening too far ---
    # The exclusion is by proven-template suffix. `.env.local` is a real secret
    # and must keep failing; so must a real file inside `.credentials/`.

    def test_env_local_is_still_a_tracked_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo_with_tracked_file(root, ".env.local")

            result = _check_tracked_secret_files(root)

            self.assertFalse(result.passed)
            self.assertIn(".env.local", result.message)

    def test_real_credentials_file_is_still_a_tracked_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo_with_tracked_file(root, ".credentials/api.token")

            result = _check_tracked_secret_files(root)

            self.assertFalse(result.passed)
            self.assertIn("api.token", result.message)

    def test_example_suffix_does_not_whitelist_a_key_by_name(self) -> None:
        # `id_rsa.example` is a template; `id_rsa` is not. Naming a real key
        # `id_rsa` inside a dir must still fail even next to templates.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo_with_tracked_file(root, "deploy/id_rsa.example")
            _add_tracked_file(root, "deploy/id_rsa")

            result = _check_tracked_secret_files(root)

            self.assertFalse(result.passed)
            self.assertIn("deploy/id_rsa", result.message)
            self.assertNotIn("id_rsa.example", result.message)


if __name__ == "__main__":
    unittest.main()
