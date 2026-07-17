from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_PLACEHOLDER_RE = re.compile(r"\[([A-Z][A-Z0-9_]{2,})\]")


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
        _check_unfilled_placeholders(repo_root),
        _check_file(repo_root, "AGENTS.md"),
        _check_file(repo_root, "README.md"),
        _check_file(repo_root, "handoff.md"),
        _check_ready_flag(
            repo_root,
            ".docs/software-overview.md",
            "project_context_ready: yes",
        ),
        _check_ready_flag(
            repo_root,
            ".docs/limits.md",
            "limits_ready: yes",
        ),
        _check_required_reading(repo_root),
        _check_active_issue(repo_root),
        _check_resume_next_step(repo_root),
        _check_tracked_secret_files(repo_root),
        _check_gitignore_secrets(repo_root),
        _check_host_identity(repo_root),
        _check_sibling_branch(repo_root),
        _check_security_advisories(repo_root),
        _check_codemap(repo_root),
    ]
    return DoctorResult(root=repo_root, checks=tuple(checks))


# ── security advisories (security-standards §1–§4, §7–§11) ────────────────────────
#
# Heuristic, line-based scans for the automatable rules. These are ADVISORY: they
# WARN and never fail, so a consumer project's `doctor` stays PASS while the risk
# is surfaced. Each hit is a prompt to review, not a verdict — false positives are
# expected (e.g. a legitimate 0.0.0.0 bind behind a firewall).
_SECURITY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("disabled TLS verification", re.compile(
        r"verify\s*=\s*False|rejectUnauthorized\s*:\s*false|CURLOPT_SSL_VERIFYPEER"
        r"|sslmode=disable|StrictHostKeyChecking[=\s]+no")),
    ("secret in URL/query", re.compile(
        r"[?&](token|key|secret|senha|password|access_token|api_key)=")),
    ("shell injection risk", re.compile(r"shell\s*=\s*True|os\.system\(")),
    ("non-CSPRNG for secrets/ids", re.compile(r"Math\.random\(")),
    ("weak password hash", re.compile(
        r"hashlib\.(md5|sha1)\b|createHash\(\s*['\"](md5|sha1)['\"]")),
    ("bind on 0.0.0.0", re.compile(r"0\.0\.0\.0")),
    ("curl|bash installer", re.compile(r"curl\s+[^|]*\|\s*(sudo\s+)?(ba)?sh\b")),
    ("unfiltered archive extract", re.compile(r"\.extractall\(")),
)

# This module *defines* the patterns above as string literals, so scanning it would
# self-match. Skip it (a consumer project never has GovKit's own source in-tree).
_SECURITY_SCAN_SKIP_FILES: frozenset[str] = frozenset({"doctor.py"})

_SECURITY_MAX_EXAMPLES = 8


def _iter_source_files(root: Path):
    """Yield source files under *root*, skipping vendor/build dirs."""
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            items = list(current.iterdir())
        except (PermissionError, OSError):
            continue
        for item in items:
            if item.is_dir():
                if item.name not in _CODEMAP_SKIP and not item.name.endswith((".egg-info", ".dist-info")):
                    stack.append(item)
            elif item.is_file() and item.suffix in _CODEMAP_SOURCE_EXTENSIONS:
                yield item


def _check_security_advisories(root: Path) -> CheckResult:
    """Advisory scan for the automatable security-standards anti-patterns."""
    name = "security advisories"
    hits: dict[str, int] = {}
    examples: list[str] = []
    for path in _iter_source_files(root):
        if path.name in _SECURITY_SCAN_SKIP_FILES:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            for label, pattern in _SECURITY_PATTERNS:
                if not pattern.search(line):
                    continue
                # extractall is fine when it passes a member filter.
                if label == "unfiltered archive extract" and "filter=" in line:
                    continue
                hits[label] = hits.get(label, 0) + 1
                if len(examples) < _SECURITY_MAX_EXAMPLES:
                    examples.append(f"{path.relative_to(root)}:{lineno} [{label}]")

    if hits:
        total = sum(hits.values())
        summary = ", ".join(f"{label} ×{count}" for label, count in sorted(hits.items()))
        detail = "; ".join(examples)
        return CheckResult(
            name,
            False,
            f"review {total} advisory hit(s): {summary} — e.g. {detail}",
            advisory=True,
        )
    return CheckResult(name, True, "no security anti-patterns detected", advisory=True)


def _check_host_identity(root: Path) -> CheckResult:
    """Fail when per-host identity is missing or incomplete.

    Enforces the per-host identity contract: no host should operate a governed
    project without verifiable operator/host/instance identity.
    """
    from .identity import IDENTITY_FILENAME, load_identity

    identity = load_identity(root)
    if identity is None:
        return CheckResult(
            "host identity",
            False,
            f"{IDENTITY_FILENAME} missing — run 'governancekit configure' to "
            "collect operator_name, host_id and instance_path",
        )
    missing = identity.missing_required()
    if missing:
        return CheckResult(
            "host identity",
            False,
            f"{IDENTITY_FILENAME} incomplete — missing: {', '.join(missing)}; "
            "run 'governancekit configure' to complete it",
        )
    return CheckResult(
        "host identity",
        True,
        f"{identity.operator_name}@{identity.host_id} ({identity.instance_path})",
    )


def _check_sibling_branch(root: Path) -> CheckResult:
    """Advisory: warn when the current branch may collide with a sibling instance."""
    from .identity import current_branch, load_identity, sibling_branch_conflict

    identity = load_identity(root)
    if identity is None or not identity.sibling_path.strip():
        return CheckResult("sibling branch", True, "no sibling instance declared", advisory=True)
    branch = current_branch(root)
    conflict = sibling_branch_conflict(identity, branch)
    if conflict:
        return CheckResult("sibling branch", False, conflict, advisory=True)
    return CheckResult("sibling branch", True, f"branch '{branch}' clear of sibling ownership", advisory=True)


_PLACEHOLDER_SCAN_PATHS = [
    "AGENTS.md",
    "CLAUDE.md",
    ".cursorrules",
    ".windsurfrules",
    "GEMINI.md",
    ".github/copilot-instructions.md",
]


def _check_unfilled_placeholders(root: Path) -> CheckResult:
    """Fail if any [PLACEHOLDER] tokens remain in installed kit files."""
    found: dict[str, list[str]] = {}
    for rel in _PLACEHOLDER_SCAN_PATHS:
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        tokens = _PLACEHOLDER_RE.findall(text)
        if tokens:
            found[rel] = sorted(set(tokens))

    if found:
        detail = "; ".join(
            f"{rel}: {', '.join(f'[{t}]' for t in tokens)}"
            for rel, tokens in found.items()
        )
        return CheckResult(
            "unfilled placeholders",
            False,
            f"kit not configured — run 'governancekit install-agents' to fill: {detail}",
        )
    return CheckResult("unfilled placeholders", True, "all placeholders filled")


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


_REQUIRED_READING_REL = "docs/required-reading.md"

# Template / unfilled lines that do not count as real reading entries.
_REQUIRED_READING_STUBS: frozenset[str] = frozenset({
    "[path]", "<doc>", "<path>", "...", "tbd", "todo",
})


def _check_required_reading(root: Path) -> CheckResult:
    """Ensure the project lists the docs an agent must read before an issue.

    Passes when ``docs/required-reading.md`` exists and either declares an explicit
    ``- (none)`` sentinel or lists at least one concrete document.
    """
    path = root / _REQUIRED_READING_REL
    if not path.is_file():
        return CheckResult(
            _REQUIRED_READING_REL,
            False,
            "missing — list project docs agents must read before an issue "
            "(use '- (none)' if there are none)",
        )

    entries = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line.startswith(("- ", "* ")):
            continue
        item = line[2:].strip()
        if item.lower() in {"(none)", "none"}:
            return CheckResult(_REQUIRED_READING_REL, True, "explicitly declares no required reading")
        if item and item.lower() not in _REQUIRED_READING_STUBS:
            entries.append(item)

    if entries:
        return CheckResult(_REQUIRED_READING_REL, True, f"lists {len(entries)} required document(s)")
    return CheckResult(
        _REQUIRED_READING_REL,
        False,
        "no concrete entries — list the docs to read, or '- (none)'",
    )


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


_TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist")


def _is_secret_template(path: str) -> bool:
    """True when *path* is a template shipped on purpose, not a real secret.

    The kit itself seeds `.credentials/` with `*.example` + README files (incl.
    translated `README-ptbr.md`), and projects ship `.env.example`; failing
    those trains the reader to ignore the FAIL line, which is worse than not
    checking. The twin gate in AI-Agents (`scripts/run-checks.sh` §4) already
    excludes exactly these.

    Deliberately narrow: the exclusion is a proven-template suffix, never a
    prefix. `.env.local` and `.env.production` are real secrets and must not
    match here (SEC-0221).
    """
    name = Path(path).name
    if name.endswith(_TEMPLATE_SUFFIXES):
        return True
    if not path.startswith(".credentials/"):
        return False
    # Doc/scaffolding files the kit seeds into .credentials/ — never secrets.
    return name == ".gitignore" or name.startswith("README")


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

    # security-standards §1: private key material is never tracked. Only
    # unambiguously-private artifacts are hard failures here; ambiguous ones
    # (.pem/.key can be public certs) are surfaced by the advisory scan instead.
    forbidden_prefixes = (".credentials/",)
    forbidden_names = (".env", ".credentials", "id_rsa", "id_ed25519")
    forbidden_suffixes = (".token", ".ppk", ".pfx", ".ovpn")
    tracked_files = completed.stdout.splitlines()
    offenders = [
        path
        for path in tracked_files
        if not _is_secret_template(path)
        and (
            path.startswith(forbidden_prefixes)
            or Path(path).name in forbidden_names
            or Path(path).name.startswith(".env")
            or path.endswith(forbidden_suffixes)
        )
    ]
    if offenders:
        return CheckResult("tracked secrets", False, f"forbidden tracked files: {', '.join(offenders)}")

    return CheckResult("tracked secrets", True, "no forbidden tracked secret paths")


# Representative secret paths that .gitignore MUST cover so credentials cannot be
# tracked in the first place (preventive counterpart to _check_tracked_secret_files).
# The kit's convention: secrets live only in .env or .credentials/ (security
# standards §1). We probe one path per convention with `git check-ignore`.
_SECRET_PROBE_PATHS = (".env", ".credentials/secret.token")


def _check_gitignore_secrets(root: Path) -> CheckResult:
    name = "gitignore secrets"
    if not (root / ".git").exists():
        return CheckResult(name, True, "not a git repository")

    uncovered: list[str] = []
    for probe in _SECRET_PROBE_PATHS:
        try:
            completed = subprocess.run(
                ["git", "check-ignore", "-q", "--", probe],
                cwd=root,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            return CheckResult(name, False, f"could not run git check-ignore: {error}")
        # 0 = ignored (good), 1 = not ignored, anything else = git error.
        if completed.returncode == 1:
            uncovered.append(probe)
        elif completed.returncode != 0:
            return CheckResult(
                name,
                False,
                f"git check-ignore failed on {probe}: {completed.stderr.strip()}",
            )

    if uncovered:
        return CheckResult(
            name,
            False,
            f".gitignore does not cover secret paths: {', '.join(uncovered)}",
        )

    return CheckResult(name, True, "secret paths (.env, .credentials/) are gitignored")


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

