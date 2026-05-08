from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    message: str
    advisory: bool = False


@dataclass(frozen=True)
class DoctorResult:
    root: Path
    checks: tuple[CheckResult, ...]

    @property
    def ok(self) -> bool:
        return all(check.passed for check in self.checks if not check.advisory)


_CODEMAP_SKIP: frozenset[str] = frozenset({
    '.git', '__pycache__', 'node_modules',
    '.tox', '.venv', 'venv', 'env',
    'dist', 'build',
    '.mypy_cache', '.pytest_cache', '.ruff_cache',
})

_CODEMAP_SOURCE_EXTENSIONS: frozenset[str] = frozenset({
    '.py', '.js', '.ts', '.jsx', '.tsx', '.mjs',
    '.go', '.rb', '.java', '.rs',
    '.c', '.cpp', '.cc', '.h', '.hpp',
    '.sh', '.bash',
})


def run_doctor(root: Path) -> DoctorResult:
    repo_root = root.resolve()
    checks = [
        _check_file(repo_root, "AGENTS.md"),
        _check_file(repo_root, "README.md"),
        _check_file(repo_root, "handoff.md"),
        _check_ready_flag(
            repo_root,
            "docs/software-overview.md",
            "project_context_ready: yes",
        ),
        _check_ready_flag(
            repo_root,
            "docs/limits.md",
            "limits_ready: yes",
        ),
        _check_active_issue(repo_root),
        _check_resume_next_step(repo_root),
        _check_tracked_secret_files(repo_root),
        _check_codemap(repo_root),
    ]
    return DoctorResult(root=repo_root, checks=tuple(checks))


def _check_file(root: Path, relative_path: str) -> CheckResult:
    path = root / relative_path
    if path.is_file():
        return CheckResult(relative_path, True, "found")
    return CheckResult(relative_path, False, "missing")


def _check_ready_flag(root: Path, relative_path: str, flag: str) -> CheckResult:
    path = root / relative_path
    if not path.is_file():
        return CheckResult(relative_path, False, "missing")

    content = path.read_text(encoding="utf-8")
    if flag in content:
        return CheckResult(relative_path, True, f"contains `{flag}`")
    return CheckResult(relative_path, False, f"does not contain `{flag}`")


def _check_active_issue(root: Path) -> CheckResult:
    issues_root = root / "docs" / "issues"
    if not issues_root.is_dir():
        return CheckResult("docs/issues", False, "missing")

    epic_dirs = sorted(path for path in issues_root.iterdir() if path.is_dir() and not path.name == "templates")
    for epic_dir in epic_dirs:
        required = [
            epic_dir / "README.md",
            epic_dir / "epic.md",
            epic_dir / "RESUME.md",
            epic_dir / "issues",
        ]
        if all(path.exists() for path in required) and any((epic_dir / "issues").glob("*.md")):
            return CheckResult("docs/issues active epic", True, f"found `{epic_dir.name}`")

    return CheckResult(
        "docs/issues active epic",
        False,
        "no epic found with README.md, epic.md, RESUME.md, and at least one task",
    )


def _check_resume_next_step(root: Path) -> CheckResult:
    resume_files = sorted((root / "docs" / "issues").glob("*/RESUME.md"))
    if not resume_files:
        return CheckResult("RESUME.md next step", False, "no resume file found")

    active_resume = _prefer_started_resume(resume_files)
    content = active_resume.read_text(encoding="utf-8")
    marker = "## Next Step (DO THIS FIRST)"
    count = content.count(marker)
    if count != 1:
        return CheckResult("RESUME.md next step", False, f"expected exactly one marker, found {count}")

    after_marker = content.split(marker, 1)[1].strip()
    if not after_marker:
        return CheckResult("RESUME.md next step", False, "next step is empty")

    first_line = after_marker.splitlines()[0].strip()
    if not first_line or first_line.lower() in {"continue work", "todo", "tbd"}:
        return CheckResult("RESUME.md next step", False, "next step is not actionable")

    return CheckResult("RESUME.md next step", True, f"found in `{active_resume.relative_to(root)}`")


def _prefer_started_resume(resume_files: list[Path]) -> Path:
    for resume_file in resume_files:
        if "[started]" in resume_file.parent.name:
            return resume_file
    return resume_files[0]


def _check_tracked_secret_files(root: Path) -> CheckResult:
    if not (root / ".git").exists():
        return CheckResult("tracked secrets", True, "not a git repository")

    try:
        completed = subprocess.run(
            ["git", "ls-files"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        return CheckResult("tracked secrets", False, f"could not inspect git index: {error}")

    forbidden_prefixes = (".credentials/",)
    forbidden_names = (".env",)
    forbidden_suffixes = (".token",)
    tracked_files = completed.stdout.splitlines()
    offenders = [
        path
        for path in tracked_files
        if path.startswith(forbidden_prefixes)
        or Path(path).name in forbidden_names
        or path.endswith(forbidden_suffixes)
    ]
    if offenders:
        return CheckResult("tracked secrets", False, f"forbidden tracked files: {', '.join(offenders)}")

    return CheckResult("tracked secrets", True, "no forbidden tracked secret paths")


def _count_newer_source_files(root: Path, since: float) -> int:
    """Count source files under root modified after timestamp since."""
    count = 0
    try:
        items = list(root.iterdir())
    except PermissionError:
        return 0
    for item in items:
        if item.is_dir():
            if item.name not in _CODEMAP_SKIP and not item.name.endswith(('.egg-info', '.dist-info')):
                count += _count_newer_source_files(item, since)
        elif item.is_file() and item.suffix in _CODEMAP_SOURCE_EXTENSIONS:
            if item.stat().st_mtime > since:
                count += 1
    return count


def _check_codemap(root: Path) -> CheckResult:
    codemap = root / "docs" / "codemap.md"
    if not codemap.is_file():
        return CheckResult(
            "codemap",
            False,
            "docs/codemap.md missing — run 'governancekit map' to generate it",
            advisory=True,
        )
    since = codemap.stat().st_mtime
    stale_count = _count_newer_source_files(root, since)
    if stale_count:
        return CheckResult(
            "codemap",
            False,
            f"docs/codemap.md is stale ({stale_count} source file(s) changed) — run 'governancekit map'",
            advisory=True,
        )
    return CheckResult("codemap", True, "docs/codemap.md is up to date")

