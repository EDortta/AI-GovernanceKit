from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from governancekit.doctor import run_doctor


class DoctorTests(unittest.TestCase):
    def test_valid_repository_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)

            result = run_doctor(root)

            self.assertTrue(result.ok, result.checks)

    def test_missing_limits_ready_flag_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / "docs" / "limits.md").write_text("limits_ready: no\n", encoding="utf-8")

            result = run_doctor(root)

            self.assertFalse(result.ok)
            self.assertIn("docs/limits.md", failed_check_names(result))

    def test_unfilled_template_prose_does_not_satisfy_the_flag(self) -> None:
        # Regression: the template the kit ships explains the flag in prose. A
        # substring check matched that sentence and reported a project ready while
        # its flag literally said `no`.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / "docs" / "limits.md").write_text(
                "# Agent Operational Limits\n\n"
                "## Metadata\n\n"
                "- limits_ready: no\n\n"
                "When copied into a target project, the programmer must replace these "
                "limits and set `limits_ready: yes` only after they are accurate.\n",
                encoding="utf-8",
            )

            result = run_doctor(root)

            self.assertFalse(result.ok)
            self.assertIn("docs/limits.md", failed_check_names(result))

    def test_empty_resume_next_step_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            resume = root / "docs" / "issues" / "001-bootstrap-[started]" / "RESUME.md"
            resume.write_text("# Resume\n\n## Next Step (DO THIS FIRST)\n", encoding="utf-8")

            result = run_doctor(root)

            self.assertFalse(result.ok)
            self.assertIn("RESUME.md next step", failed_check_names(result))


    def test_missing_required_reading_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / "docs" / "required-reading.md").unlink()

            result = run_doctor(root)

            self.assertFalse(result.ok)
            self.assertIn("docs/required-reading.md", failed_check_names(result))

    def test_required_reading_none_sentinel_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / "docs" / "required-reading.md").write_text(
                "# Required Reading\n\n- (none)\n", encoding="utf-8"
            )

            result = run_doctor(root)

            self.assertNotIn("docs/required-reading.md", failed_check_names(result))

    def test_required_reading_none_fails_when_legacy_agents_are_orphaned(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / ".docs-migration-bak" / "agents").mkdir(parents=True)
            (root / "docs" / "required-reading.md").write_text("- (none)\n", encoding="utf-8")

            result = run_doctor(root)

            self.assertIn("docs/required-reading.md", failed_check_names(result))
            self.assertIn("content migration", failed_check_names(result))

    def test_legacy_rule_traps_warn_without_blocking_ready_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / ".docs-migration-bak").mkdir()
            nested = root / "documents"
            nested.mkdir()
            (nested / "AGENTS.md").write_text("# legacy IDE rules\n", encoding="utf-8")

            result = run_doctor(root)

            check = next(c for c in result.checks if c.name == "legacy rule traps")
            self.assertFalse(check.passed)
            self.assertTrue(check.advisory)
            self.assertTrue(result.ok, result.checks)
            self.assertIn("documents/AGENTS.md", check.message)

    def test_required_reading_fails_for_missing_listed_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / "docs" / "required-reading.md").write_text(
                "- `docs/project-rules.md` — project rules\n", encoding="utf-8"
            )

            result = run_doctor(root)

            self.assertIn("docs/required-reading.md", failed_check_names(result))

    def test_existing_config_requires_integration_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / ".gk").mkdir(exist_ok=True)
            (root / ".gk" / "project-config.json").write_text(
                '{"config_version":1,"project_name":"Demo","project_state":"existing",'
                '"languages":[],"frameworks":[],"package_managers":[],"automation_commands":[],'
                'domains":[],"capabilities":[],"agents":[],"providers":[],"governance_files":[],'
                '"integration_status":"missing","notes":[]}\n',
                encoding="utf-8",
            )

            result = run_doctor(root)

            self.assertIn("AI-Agents integration contract", failed_check_names(result))

    def test_manifest_missing_tracked_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / ".gk").mkdir(exist_ok=True)
            (root / ".gk" / "manifest.json").write_text(
                '{"files":{".docs/agents/programmer.md":"hash"}}\n', encoding="utf-8"
            )

            result = run_doctor(root)

            self.assertIn("AI-Agents manifest", failed_check_names(result))

    def test_required_reading_only_stub_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / "docs" / "required-reading.md").write_text(
                "# Required Reading\n\n- [path]\n", encoding="utf-8"
            )

            result = run_doctor(root)

            self.assertIn("docs/required-reading.md", failed_check_names(result))

    def test_codemap_requires_current_layered_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            codemap = root / "docs" / "codemap.md"
            codemap.write_text("# Code Map\n\n## File Tree\n", encoding="utf-8")

            result = run_doctor(root)

            check = next(c for c in result.checks if c.name == "codemap")
            self.assertFalse(check.passed)
            self.assertTrue(check.advisory)
            self.assertIn("obsolete", check.message)


    def test_missing_identity_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / ".governancekit-identity.json").unlink()

            result = run_doctor(root)

            self.assertFalse(result.ok)
            self.assertIn("host identity", failed_check_names(result))

    def test_incomplete_identity_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / ".governancekit-identity.json").write_text(
                '{"operator_name": "Ann"}\n', encoding="utf-8"
            )

            result = run_doctor(root)

            self.assertFalse(result.ok)
            self.assertIn("host identity", failed_check_names(result))

    def test_complete_identity_file_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)

            result = run_doctor(root)

            self.assertNotIn("host identity", failed_check_names(result))

    def test_policy_markers_do_not_fail_placeholder_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / "AGENTS.md").write_text(
                "# AGENTS.md\n[DEFAULT] [MANDATORY] [PROHIBITED]\n",
                encoding="utf-8",
            )

            result = run_doctor(root)

            check = next(c for c in result.checks if c.name == "unfilled placeholders")
            self.assertTrue(check.passed)

    def test_placeholder_guidance_uses_configure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / "AGENTS.md").write_text("owner: {{OPERATOR_NAME}}\n", encoding="utf-8")

            result = run_doctor(root)

            check = next(c for c in result.checks if c.name == "unfilled placeholders")
            self.assertFalse(check.passed)
            self.assertIn("governancekit --root", check.message)
            self.assertIn("configure", check.message)

    def test_missing_project_config_is_advisory_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)

            result = run_doctor(root)

            check = next(c for c in result.checks if c.name == "project configuration")
            self.assertTrue(check.advisory)
            self.assertFalse(check.passed)
            self.assertTrue(result.ok, result.checks)

    def test_present_project_config_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / ".gk").mkdir(parents=True, exist_ok=True)
            (root / ".gk" / "project-config.json").write_text(
                '{"config_version":1,"project_name":"Demo","project_state":"existing","languages":["python"],'
                '"frameworks":[],"package_managers":[],"automation_commands":[],"domains":["backend"],'
                '"capabilities":["api"],"agents":["programmer"],"providers":[],"governance_files":[],'
                '"integration_status":"ok","notes":[]}\n',
                encoding="utf-8",
            )

            result = run_doctor(root)

            check = next(c for c in result.checks if c.name == "project configuration")
            self.assertTrue(check.passed)
            self.assertTrue(check.advisory)

    def test_provider_without_credential_ref_is_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / ".gk").mkdir(parents=True, exist_ok=True)
            (root / ".gk" / "project-config.json").write_text(
                '{"config_version":1,"project_name":"Demo","project_state":"existing","languages":["python"],'
                '"frameworks":[],"package_managers":[],"automation_commands":[],"domains":["backend"],'
                '"capabilities":["api"],"agents":["programmer"],'
                '"providers":[{"name":"openai","mode":"env","validation":"reference-required"}],'
                '"governance_files":[],"integration_status":"ok","notes":[]}\n',
                encoding="utf-8",
            )

            result = run_doctor(root)

            check = next(c for c in result.checks if c.name == "project configuration")
            self.assertFalse(check.passed)
            self.assertTrue(check.advisory)
            self.assertIn("credential_ref", check.message)


    def test_security_advisories_flag_antipatterns_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / "app.py").write_text(
                "import requests, subprocess\n"
                "requests.get(url, verify=False)\n"
                "subprocess.run(cmd, shell=True)\n",
                encoding="utf-8",
            )

            result = run_doctor(root)

            adv = next(c for c in result.checks if c.name == "security advisories")
            self.assertTrue(adv.advisory)
            self.assertFalse(adv.passed)
            self.assertIn("disabled TLS verification", adv.message)
            self.assertIn("shell injection risk", adv.message)
            # Advisory findings never break the overall result.
            self.assertTrue(result.ok, result.checks)

    def test_security_advisories_clean_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            (root / "app.py").write_text("x = 1\n", encoding="utf-8")

            result = run_doctor(root)

            adv = next(c for c in result.checks if c.name == "security advisories")
            self.assertTrue(adv.passed)

    def test_tracked_private_key_material_fails(self) -> None:
        import subprocess

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_repo(root)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "id_rsa").write_text("PRIVATE KEY MATERIAL\n", encoding="utf-8")
            subprocess.run(["git", "add", "id_rsa"], cwd=root, check=True)

            result = run_doctor(root)

            self.assertFalse(result.ok)
            self.assertIn("tracked secrets", failed_check_names(result))


class CouncilGateDoctorTests(unittest.TestCase):
    """The one non-advisory check that only ever speaks at commit time."""

    def _repo(self, root: Path) -> None:
        write_valid_repo(root)
        # Becoming a git repository activates the secret-ignore check, which is
        # unrelated to this gate but would otherwise sink `result.ok`.
        (root / ".gitignore").write_text(".env\n.env.*\n.credentials/\n", encoding="utf-8")
        for args in (
            ("init", "-q"),
            ("config", "user.email", "council@test"),
            ("config", "user.name", "council"),
        ):
            subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)

    def test_outside_a_commit_the_gate_is_silent_and_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._repo(root)

            result = run_doctor(root)

            gate = next(check for check in result.checks if check.name == "council gate")
            self.assertTrue(gate.advisory)
            self.assertTrue(result.ok, result.checks)

    def test_a_staged_contract_change_without_a_round_fails_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._repo(root)
            (root / ".docs" / "agents").mkdir(parents=True, exist_ok=True)
            (root / ".docs" / "agents" / "reviewer.md").write_text("# reviewer\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", "--", ".docs/agents/reviewer.md"],
                cwd=root, check=True, capture_output=True,
            )

            result = run_doctor(root)

            gate = next(check for check in result.checks if check.name == "council gate")
            self.assertFalse(gate.advisory, "the gate must be able to block a commit")
            self.assertFalse(gate.passed)
            self.assertFalse(result.ok)
            self.assertIn("council gate", failed_check_names(result))

    def test_an_unreadable_record_never_wedges_the_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._repo(root)
            (root / "AGENTS.md").write_text("# contract, revised\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", "--", "AGENTS.md"], cwd=root, check=True, capture_output=True
            )
            from governancekit.council import record_path, staged_fingerprint

            fingerprint = staged_fingerprint(root)
            assert fingerprint is not None
            path = record_path(root, fingerprint)
            path.parent.mkdir(parents=True)
            path.write_text("{ not json", encoding="utf-8")

            result = run_doctor(root)

            gate = next(check for check in result.checks if check.name == "council gate")
            self.assertTrue(gate.advisory)
            self.assertTrue(gate.passed)


def write_valid_repo(root: Path) -> None:
    (root / "docs" / "issues" / "001-bootstrap-[started]" / "issues").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
    (root / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    (root / "handoff.md").write_text("# Handoff\n", encoding="utf-8")
    (root / ".docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "software-overview.md").write_text(
        "project_context_ready: yes\n",
        encoding="utf-8",
    )
    (root / "docs" / "limits.md").write_text("limits_ready: yes\n", encoding="utf-8")
    (root / "docs" / "required-reading.md").write_text(
        "# Required Reading\n\n- `docs/software-overview.md` — context\n",
        encoding="utf-8",
    )

    epic = root / "docs" / "issues" / "001-bootstrap-[started]"
    (epic / "README.md").write_text("# Epic README\n", encoding="utf-8")
    (epic / "epic.md").write_text("# Epic\n", encoding="utf-8")
    (epic / "RESUME.md").write_text(
        "# Resume\n\n## Next Step (DO THIS FIRST)\n\nRun the next validation command.\n",
        encoding="utf-8",
    )
    (epic / "issues" / "001-task-[started].md").write_text("# Task\n", encoding="utf-8")
    (root / ".governancekit-identity.json").write_text(
        '{"operator_name": "Ann", "host_id": "host-a", '
        '"instance_path": "/home/ann/proj"}\n',
        encoding="utf-8",
    )


def failed_check_names(result) -> set[str]:
    return {check.name for check in result.checks if not check.passed}


if __name__ == "__main__":
    unittest.main()
