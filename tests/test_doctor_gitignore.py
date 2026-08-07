from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from governancekit.doctor import (
    _SECRET_ADVISORY_PROBE_PATHS,
    _SECRET_PROBE_PATHS,
    _SECRET_TRACKABLE_PATHS,
    _check_gitignore_secret_coverage,
    _check_gitignore_secrets,
)
from governancekit.install_agents import (
    SECRET_IGNORE_PATTERNS,
    SECRET_TEMPLATE_NAMES,
    SECRET_TEMPLATE_SUFFIXES,
    _gitignore_entries,
)


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


class GeneratedBlockCoversWhatTheDoctorProbesTests(unittest.TestCase):
    """A3: the generator and the check were two lists, and they disagreed.

    `_gitignore_entries` emitted eighteen entries, none covering `.env`, while
    `_check_gitignore_secrets` failed the repository for exactly that — so every
    project the kit installed was born failing a mandatory gate on a file the kit
    itself had just written. Reproduced in the field on CodexBridge. These tests are
    the pin: the block the installer writes must satisfy every probe the doctor runs,
    and it must not swallow the documentation that has to stay tracked.
    """

    def _repo_with_generated_block(self, root: Path) -> None:
        _init_repo(root, "\n".join(_gitignore_entries(["AGENTS.md"])) + "\n")

    def test_every_mandatory_probe_is_covered_by_the_generated_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._repo_with_generated_block(root)

            result = _check_gitignore_secrets(root)

            self.assertTrue(result.passed, result.message)

    def test_every_advisory_probe_is_covered_by_the_generated_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._repo_with_generated_block(root)

            result = _check_gitignore_secret_coverage(root)

            self.assertTrue(result.passed, result.message)

    def test_the_generated_block_keeps_dotenv_example_tracked(self) -> None:
        # `.env.*` without the re-includes would hide the file every project commits
        # as documentation — the over-broad half of the same defect.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._repo_with_generated_block(root)

            for tracked in _SECRET_TRACKABLE_PATHS:
                completed = subprocess.run(
                    ["git", "check-ignore", "-q", "--", tracked], cwd=root
                )
                self.assertEqual(completed.returncode, 1, f"{tracked} must stay tracked")

    def test_the_mandatory_probe_list_stays_narrow(self) -> None:
        # Widening a mandatory probe turns every installed project red the moment it
        # upgrades the tool, for a hole it did not just open. New coverage lands
        # advisory first — this pins the decision so a later edit has to argue with it.
        self.assertEqual(_SECRET_PROBE_PATHS, (".env", ".credentials/secret.token"))
        self.assertTrue(_SECRET_ADVISORY_PROBE_PATHS)

    def test_secret_patterns_are_emitted_whatever_the_track_kit_docs_choice(self) -> None:
        for track in (True, False):
            entries = _gitignore_entries(["AGENTS.md", ".docs/agents"], track_kit_docs=track)
            for pattern in SECRET_IGNORE_PATTERNS:
                self.assertIn(pattern, entries, f"track_kit_docs={track}")


class GeneratedBlockMatchesRealGitSemanticsTests(unittest.TestCase):
    """Patterns are not the contract; what git actually ignores is.

    `.credentials/` as a bare directory pattern reads correctly and behaves wrongly:
    git never descends into an excluded directory, so the nested `!README.md` the kit
    seeds can never fire and the scaffolding becomes permanently untrackable. Only a
    real `git check-ignore` catches that, which is why this table exists.
    """

    CASES = {
        ".env": True,
        ".env.local": True,
        ".env.production": True,
        ".envrc": True,
        ".npmrc": True,
        ".netrc": True,
        "sub/.env": True,
        ".credentials/secret.token": True,
        "a.key": True,
        "a.pem": True,
        "docs/notes.key": True,
        ".env.example": False,
        ".env.sample": False,
        ".env.dist": False,
        ".env.missing": False,
        "sub/.env.example": False,
        ".credentials/README.md": False,
        ".credentials/README-ptbr.md": False,
        ".credentials/identity.json.example": False,
        ".credentials/.gitignore": False,
        ".credentials/.keep": False,
        "a.pub": False,
        "README.md": False,
    }

    def test_git_agrees_with_the_intent_of_every_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo(root, "\n".join(_gitignore_entries(["AGENTS.md"])) + "\n")
            for probe, should_be_ignored in self.CASES.items():
                ignored = subprocess.run(
                    ["git", "check-ignore", "-q", "--", probe], cwd=root
                ).returncode == 0
                self.assertEqual(ignored, should_be_ignored, probe)

    def test_the_block_re_includes_everything_the_doctor_calls_a_template(self) -> None:
        # The other direction of the A3 defect: a file the tracked-secrets check
        # forgives must not be a file the ignore block makes untrackable.
        from governancekit.doctor import _is_secret_template

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo(root, "\n".join(_gitignore_entries(["AGENTS.md"])) + "\n")
            for probe in (
                *(f".env{suffix}" for suffix in SECRET_TEMPLATE_SUFFIXES),
                *SECRET_TEMPLATE_NAMES,
                ".credentials/README.md",
                ".credentials/.keep",
                ".credentials/token.example",
            ):
                if not _is_secret_template(probe):
                    continue
                ignored = subprocess.run(
                    ["git", "check-ignore", "-q", "--", probe], cwd=root
                ).returncode == 0
                self.assertFalse(ignored, f"{probe} is a template but the block hides it")


class ShellInstallerWritesTheSameBlockTests(unittest.TestCase):
    """Two installers, one contract — the A3 defect, one level up.

    `scripts/install-agents-kit.sh` in the companion AI-Agents checkout is the other
    install path. It wrote `.gk/.gitignore` and `.credentials/.gitignore` and never
    touched the project's own file, so a shell-installed project failed the mandatory
    `gitignore secrets` gate from birth — and the failure message named a Python
    command it had never run. Fixing only the Python side would have left half the
    park broken while the issue read as closed.
    """

    def _shell_block(self) -> list[str]:
        script = (
            Path(__file__).resolve().parents[2]
            / "Agents" / "scripts" / "install-agents-kit.sh"
        )
        if not script.is_file():
            self.skipTest("companion AI-Agents checkout is not available")
        text = script.read_text(encoding="utf-8")
        start = text.index("write_root_gitignore_secrets() {")
        body = text[start:]
        opening = body.index("cat <<'IGN'\n") + len("cat <<'IGN'\n")
        return body[opening:body.index("\nIGN", opening)].splitlines()

    def test_the_shell_block_lists_exactly_the_python_patterns(self) -> None:
        self.assertEqual(sorted(self._shell_block()), sorted(SECRET_IGNORE_PATTERNS))


class AlreadyTrackedSecretTests(unittest.TestCase):
    def test_a_tracked_dotenv_gets_the_remedy_that_works(self) -> None:
        # `git check-ignore` calls a TRACKED file "not ignored", because exclude rules
        # do not apply to tracked paths. The check used to blame the pattern and send
        # the operator to rewrite a block that was already correct, while the credential
        # stayed in history — the worst case got the one remedy that cannot work.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo(root, "\n".join(_gitignore_entries(["AGENTS.md"])) + "\n")
            (root / ".env").write_text("TOKEN=live\n", encoding="utf-8")
            subprocess.run(["git", "add", "-f", "--", ".env"], cwd=root, check=True)

            result = _check_gitignore_secrets(root)

            self.assertFalse(result.passed)
            self.assertIn("git rm --cached", result.message)
            self.assertNotIn("install-agents --upgrade", result.message)


class AdvisoryCoverageTests(unittest.TestCase):
    def test_a_dotenv_only_rule_is_flagged_but_does_not_fail_the_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo(root, ".env\n.credentials/\n")

            mandatory = _check_gitignore_secrets(root)
            advisory = _check_gitignore_secret_coverage(root)

            self.assertTrue(mandatory.passed, mandatory.message)
            self.assertFalse(advisory.passed)
            self.assertTrue(advisory.advisory)
            self.assertIn(".env.local", advisory.message)

    def test_swallowing_the_example_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_repo(root, ".env*\n.credentials/\n*.pem\n*.key\n")

            advisory = _check_gitignore_secret_coverage(root)

            self.assertFalse(advisory.passed)
            self.assertIn(".env.example", advisory.message)


if __name__ == "__main__":
    unittest.main()
