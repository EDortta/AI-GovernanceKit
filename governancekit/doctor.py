from __future__ import annotations

import os
import re
import shlex
import subprocess
import json
from dataclasses import dataclass, field
from pathlib import Path

_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]{2,})\}\}")


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
    '.docs-migration-bak',
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
            "docs/software-overview.md",
            "project_context_ready: yes",
        ),
        _check_ready_flag(
            repo_root,
            "docs/limits.md",
            "limits_ready: yes",
        ),
        _check_required_reading(repo_root),
        _check_content_migration(repo_root),
        _check_legacy_rule_traps(repo_root),
        _check_manifest_drift(repo_root),
        _check_concurrency(repo_root),
        _check_council_gate(repo_root),
        _check_active_issue(repo_root),
        _check_resume_next_step(repo_root),
        _check_tracked_secret_files(repo_root),
        _check_gitignore_secrets(repo_root),
        _check_gitignore_secret_coverage(repo_root),
        _check_local_reading_sources(repo_root),
        _check_local_sources_indexed(repo_root),
        _check_project_config(repo_root),
        _check_agents_integration_contract(repo_root),
        _check_host_identity(repo_root),
        _check_sibling_branch(repo_root),
        _check_security_advisories(repo_root),
        _check_codemap(repo_root),
    ]
    return DoctorResult(root=repo_root, checks=tuple(checks))


def _command(root: Path, command: str) -> str:
    return f"governancekit --root {shlex.quote(str(root.resolve()))} {command}"


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
    """Yield source files under *root*, skipping vendor/build dirs and nested
    git repositories.

    A subdirectory carrying its own ``.git`` (a submodule or vendored checkout)
    belongs to another project — its files are not this project's source and are
    skipped. Gitignored files are filtered separately by the caller, which needs
    *root* to consult git; see ``_git_ignored_paths``.
    """
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            items = list(current.iterdir())
        except (PermissionError, OSError):
            continue
        for item in items:
            # Every probe below stats the filesystem, and a directory the user
            # cannot search raises instead of answering — `.exists()` included.
            # The `iterdir` above already treats that as "skip and keep walking";
            # without the same guard here one unreadable directory aborted the
            # whole doctor run with a traceback and no verdict at all. Found in a
            # governed project holding a root-owned `drwx------` data directory.
            try:
                if item.is_symlink():
                    continue
                if item.is_dir():
                    if item.name in _CODEMAP_SKIP or item.name.endswith((".egg-info", ".dist-info")):
                        continue
                    if (item / ".git").exists():  # nested repo / submodule
                        continue
                    stack.append(item)
                elif item.is_file() and item.suffix in _CODEMAP_SOURCE_EXTENSIONS:
                    yield item
            except OSError:
                continue


def _git_ignored_paths(root: Path, paths: list[Path]) -> set[Path]:
    """Return the subset of *paths* that git ignores under *root*.

    Empty when *root* is not a git repo or git is unavailable — a deliberate
    fail-open (``design-standards.md`` §6): a scan that loses git degrades to
    checking *more* files, never fewer. The dangerous direction for a security
    scan is to silently skip; that never happens here.

    Uses ``git check-ignore -z --stdin`` in one batch call; ``-z`` sidesteps the
    quoting git otherwise applies to paths with unusual characters.
    """
    if not paths or not (root / ".git").exists():
        return set()
    rel_to_path: dict[str, Path] = {}
    for path in paths:
        try:
            rel_to_path[path.relative_to(root).as_posix()] = path
        except ValueError:
            continue
    if not rel_to_path:
        return set()
    try:
        completed = subprocess.run(
            ["git", "check-ignore", "-z", "--stdin"],
            cwd=root,
            input="\0".join(rel_to_path),
            capture_output=True,
            text=True,
        )
    except OSError:
        return set()
    # check-ignore exits 0 (some ignored), 1 (none), 128 (error). Only trust 0/1.
    if completed.returncode not in (0, 1):
        return set()
    return {rel_to_path[token] for token in completed.stdout.split("\0") if token in rel_to_path}


def _check_security_advisories(root: Path) -> CheckResult:
    """Advisory scan for the automatable security-standards anti-patterns."""
    name = "security advisories"
    hits: dict[str, int] = {}
    examples: list[str] = []
    source_files = list(_iter_source_files(root))
    ignored = _git_ignored_paths(root, source_files)
    for path in source_files:
        if path in ignored:
            continue
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
        summary = "\n".join(f"  - {label}: {count}" for label, count in sorted(hits.items()))
        detail = "\n".join(f"  - {example}" for example in examples)
        return CheckResult(
            name,
            False,
            f"review {total} advisory hit(s)\ncategories:\n{summary}\nexamples:\n{detail}",
            advisory=True,
        )
    return CheckResult(name, True, "no security anti-patterns detected", advisory=True)


def _check_agents_integration_contract(root: Path) -> CheckResult:
    from .integration import inspect_integration_contract
    from .project_config import load_project_config

    result = inspect_integration_contract(root)
    if result.status == "ok":
        return CheckResult("AI-Agents integration contract", True, result.message)
    if result.status == "custom-repo":
        return CheckResult("AI-Agents integration contract", True, result.message, advisory=True)
    config = load_project_config(root)
    # An existing project that has completed scope configuration must not claim
    # readiness without the executable contract that binds its installed kit to
    # this runtime.  Unconfigured and custom projects retain the advisory path.
    blocking = config is not None and config.project_state == "existing"
    return CheckResult("AI-Agents integration contract", False, result.message, advisory=not blocking)


def _check_project_config(root: Path) -> CheckResult:
    from .project_config import _PROJECT_CONFIG_FILE, load_project_config, provider_warnings

    path = root / _PROJECT_CONFIG_FILE
    if not path.exists():
        return CheckResult(
            "project configuration",
            False,
            f"{_PROJECT_CONFIG_FILE} missing — run '{_command(root, 'configure-project plan')}' before structural work",
            advisory=True,
        )
    config = load_project_config(root)
    if config is None:
        return CheckResult(
            "project configuration",
            False,
            f"{_PROJECT_CONFIG_FILE} unreadable — rebuild it with '{_command(root, 'configure-project apply')}'",
            advisory=True,
        )
    return CheckResult(
        "project configuration",
        False if provider_warnings(config.providers) else True,
        (
            "; ".join(provider_warnings(config.providers))
            if provider_warnings(config.providers)
            else f"{config.project_name} ({config.project_state}) with {len(config.domains)} domain(s)"
        ),
        advisory=True,
    )


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
            f"{IDENTITY_FILENAME} missing or unreadable — run '{_command(root, 'configure')}' to "
            "collect operator_name, host_id and instance_path",
        )
    missing = identity.missing_required()
    if missing:
        return CheckResult(
            "host identity",
            False,
            f"{IDENTITY_FILENAME} incomplete — missing: {', '.join(missing)}; "
            f"run '{_command(root, 'configure')}' to complete it",
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
    """Fail if any kit placeholder token remains in installed files."""
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
            f"{rel}: {', '.join(f'{{{{{t}}}}}' for t in tokens)}"
            for rel, tokens in found.items()
        )
        return CheckResult(
            "unfilled placeholders",
            False,
            f"kit not configured — run '{_command(root, 'configure')}' to fill: {detail}",
        )
    return CheckResult("unfilled placeholders", True, "all placeholders filled")


def _check_file(root: Path, relative_path: str) -> CheckResult:
    path = root / relative_path
    if path.is_file():
        return CheckResult(relative_path, True, "found")
    return CheckResult(relative_path, False, "missing")


def _check_concurrency(root: Path) -> CheckResult:
    """Report how many working fronts are open. Advisory: concurrency is a choice.

    How many branches and worktrees run at once is the operator's decision, not a
    defect — but it must be visible before an operation is priced for one checkout
    and then meets four.
    """
    from .concurrency import survey_concurrency

    survey = survey_concurrency(root)
    if not survey.available:
        return CheckResult("concurrency", True, "not a git repository", advisory=True)
    if survey.beyond_current == 0:
        return CheckResult("concurrency", True, "nothing open beyond this checkout", advisory=True)
    detail = ", ".join(
        f"{item.branch}{'' if item.unmerged else ' (merged)'}"
        for item in survey.items
        if not item.is_current
    )
    removable = len(survey.removable)
    message = f"{survey.beyond_current} open beyond this checkout: {detail}"
    if removable:
        message += f"\n{removable} worktree(s) hold nothing unmerged and can be removed"
    return CheckResult("concurrency", True, message, advisory=True)


def _check_council_gate(root: Path) -> CheckResult:
    """Did a council run against what is staged right now?

    This is the one check that is deliberately **not** advisory, and only ever at
    the moment of a commit. ``.docs/agents/council.md`` §4 lists five mandatory
    triggers and then admits that nothing convenes them; the non-advisory verdict
    is what the ``pre-commit`` hook already filters for, so writing it here gives
    that file the teeth it says it lacks, without a new hook type.

    Outside a commit it stays quiet. A ``doctor`` run has no staged diff to judge,
    and a check that failed on absent evidence of an event that has not happened
    yet would be noise in every other flow the kit has.
    """
    from .council import CouncilError, evaluate

    context_ready = _check_ready_flag(
        root, "docs/software-overview.md", "project_context_ready: yes"
    ).passed
    try:
        result = evaluate(root, context_ready=context_ready)
    except CouncilError as error:  # a malformed record must not wedge every commit
        return CheckResult("council gate", True, f"record unreadable: {error}", advisory=True)

    if result.blocks:
        message = result.message
        # The contract says the pre-commit hook refuses. That is only true where
        # `install-hooks` was actually run — it is opt-in, and `install-agents` does
        # not call it. Say so here rather than let the promise stand unqualified.
        if not (root / ".git" / "hooks" / "pre-commit").is_file():
            message += (
                "\n(no pre-commit hook installed here, so this only blocks via doctor: "
                "run `governancekit install-hooks` to gate the commit itself)"
            )
        return CheckResult("council gate", False, message)
    # Everything that does not block is advisory, including NOT_SELECTABLE: that one
    # is real, but it belongs to the readiness check above. Failing twice for one
    # cause teaches people to ignore both messages.
    return CheckResult("council gate", True, result.message, advisory=True)


def _check_ready_flag(root: Path, relative_path: str, flag: str) -> CheckResult:
    """Check the readiness flag as a metadata LINE, never as a substring.

    The template the kit ships explains the flag in prose — "set `limits_ready: yes`
    only after they are accurate" — so a substring test matches an untouched template
    and reports a project ready when its flag literally says ``no``. The shell
    installer has always anchored this check; this is the same contract.
    """
    path = root / relative_path
    if not path.is_file():
        return CheckResult(relative_path, False, "missing")

    marker = flag.split(":", 1)[0].strip()
    pattern = re.compile(rf"^-?[ \t]*{re.escape(marker)}[ \t]*:[ \t]*yes[ \t]*$", re.MULTILINE)
    content = path.read_text(encoding="utf-8")
    if pattern.search(content):
        return CheckResult(relative_path, True, f"contains `{flag}`")
    return CheckResult(relative_path, False, f"does not contain `{flag}`")


_REQUIRED_READING_REL = "docs/required-reading.md"

# Template / unfilled lines that do not count as real reading entries.
_REQUIRED_READING_STUBS: frozenset[str] = frozenset({
    "[path]", "<doc>", "<path>", "...", "tbd", "todo",
})
_REQUIRED_READING_PATH_RE = re.compile(r"`([^`]+)`")
_MIGRATION_BACKUP_DIR = ".docs-migration-bak"


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

    entries: list[str] = []
    explicit_none = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line.startswith(("- ", "* ")):
            continue
        item = line[2:].strip()
        if item.lower() in {"(none)", "none"}:
            explicit_none = True
            continue
        if item and item.lower() not in _REQUIRED_READING_STUBS:
            entries.append(item)

    if explicit_none and _has_project_knowledge_signals(root):
        return CheckResult(
            _REQUIRED_READING_REL,
            False,
            "declares '- (none)' despite migrated or project-specific documentation — "
            "list the contracts agents must read",
        )
    if explicit_none:
        return CheckResult(_REQUIRED_READING_REL, True, "explicitly declares no required reading")

    if entries:
        missing = _required_reading_missing_paths(root, entries)
        if missing:
            return CheckResult(
                _REQUIRED_READING_REL,
                False,
                f"lists missing document(s): {', '.join(missing)}",
            )
        return CheckResult(_REQUIRED_READING_REL, True, f"lists {len(entries)} required document(s)")
    return CheckResult(
        _REQUIRED_READING_REL,
        False,
        "no concrete entries — list the docs to read, or '- (none)'",
    )


def _has_project_knowledge_signals(root: Path) -> bool:
    """Return whether an empty index would hide known project documentation."""
    backup = root / _MIGRATION_BACKUP_DIR
    return (
        (backup / "agents").is_dir()
        or (root / "docs" / "guides").is_dir()
        or (root / "docs" / "usage").is_dir()
    )


def _required_reading_missing_paths(root: Path, entries: list[str]) -> list[str]:
    missing: list[str] = []
    for entry in entries:
        match = _REQUIRED_READING_PATH_RE.search(entry)
        if not match:
            continue
        rel = Path(match.group(1))
        candidate = (root / rel).resolve()
        if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
            missing.append(match.group(1))
    return missing


def _check_content_migration(root: Path) -> CheckResult:
    backup_agents = root / _MIGRATION_BACKUP_DIR / "agents"
    project_rules = root / "docs" / "project-rules.md"
    project_rules_dir = root / "docs" / "project-rules"
    if backup_agents.is_dir() and not project_rules.exists() and not project_rules_dir.is_dir():
        return CheckResult(
            "content migration",
            False,
            f"{_MIGRATION_BACKUP_DIR}/agents contains legacy contracts but docs/project-rules* is missing — "
            f"run '{_command(root, 'install-agents --upgrade --migrate-content')}'",
        )
    return CheckResult("content migration", True, "no orphaned legacy agent contracts")


def _check_legacy_rule_traps(root: Path) -> CheckResult:
    """Surface rule files outside the canonical, indexed load path.

    A completed content migration may intentionally retain its backup for audit,
    so neither finding blocks readiness.  They remain visible because IDEs can
    load a nested ``documents/AGENTS.md`` while GovernanceKit only indexes the
    root contract and ``docs/required-reading.md``.
    """
    findings: list[str] = []
    if (root / _MIGRATION_BACKUP_DIR).is_dir():
        findings.append(f"{_MIGRATION_BACKUP_DIR}/ retained for audit")
    nested_agents = root / "documents" / "AGENTS.md"
    if nested_agents.is_file():
        findings.append("documents/AGENTS.md may be loaded by IDE rules outside required-reading")
    if findings:
        return CheckResult("legacy rule traps", False, "; ".join(findings), advisory=True)
    return CheckResult("legacy rule traps", True, "no legacy rule files outside the canonical load path", advisory=True)


def _check_manifest_drift(root: Path) -> CheckResult:
    path = root / ".gk" / "manifest.json"
    if not path.is_file():
        return CheckResult("AI-Agents manifest", True, "no install manifest recorded", advisory=True)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        files = state.get("files", {})
    except (OSError, json.JSONDecodeError):
        return CheckResult("AI-Agents manifest", False, "unreadable .gk/manifest.json")
    if not isinstance(files, dict):
        return CheckResult("AI-Agents manifest", False, "manifest files must be an object")
    missing = sorted(rel for rel in files if not (root / rel).is_file())
    if missing:
        shown = ", ".join(missing[:8])
        suffix = "" if len(missing) <= 8 else f" (+{len(missing) - 8} more)"
        return CheckResult("AI-Agents manifest", False, f"{len(missing)} tracked path(s) missing: {shown}{suffix}")
    return CheckResult("AI-Agents manifest", True, "all tracked kit paths present")


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


from .install_agents import (  # noqa: E402 - kept beside its only consumer
    CREDENTIALS_DOC_NAMES,
    SECRET_TEMPLATE_NAMES,
    SECRET_TEMPLATE_SUFFIXES,
)

_TEMPLATE_SUFFIXES = SECRET_TEMPLATE_SUFFIXES


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
    # Conventional marker/template names. They communicate absence or an example,
    # rather than carrying a runtime environment value.
    if name in SECRET_TEMPLATE_NAMES:
        return True
    if not path.startswith(".credentials/"):
        return False
    # Doc/scaffolding files the kit seeds into .credentials/ — never secrets. The same
    # names drive the `!.credentials/...` re-includes in the generated ignore block.
    return any(
        name.startswith(doc[:-1]) if doc.endswith("*") else name == doc
        for doc in CREDENTIALS_DOC_NAMES
    )


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
#
# Every probe must be covered by the block the installer writes — the two used to be
# separate lists and drifted, so the kit failed every project it installed on `.env`.
# `test_every_mandatory_probe_is_covered_by_the_generated_block` pins them together.
#
# This list stays at two. Widening a MANDATORY probe turns every already-installed
# project red the moment it upgrades the tool, for a hole it did not just open — the
# same mistake the G1 critique caught yesterday, where a coherence check would have
# failed the whole park before the remedy existed. New coverage arrives advisory
# (below) and is promoted only once the installed park has had an upgrade to take it.
_SECRET_PROBE_PATHS = (".env", ".credentials/secret.token")

# Real holes that are not yet mandatory: `.env` alone does not cover `.env.local`, and
# a stray private key is the same secret by another name.
_SECRET_ADVISORY_PROBE_PATHS = (
    ".env.local",
    ".env.production",
    "private.key",
    "server.pem",
)

# The counterpart: paths that must stay OUT of the block. `.env.example` is the file
# every project commits as documentation, and an over-broad `.env.*` swallows it —
# a secrets rule that hides the example teaches operators to edit the managed block.
_SECRET_TRACKABLE_PATHS = (".env.example", ".env.sample")


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
        # `git check-ignore` reports an ALREADY TRACKED file as not ignored, because
        # exclude rules do not apply to tracked paths. Blaming the pattern there sends
        # the operator to rewrite a block that is already correct, while the credential
        # stays in the history — the one case where this check matters most got the one
        # remedy that cannot work.
        tracked = [path for path in uncovered if _is_tracked(root, path)]
        if tracked:
            return CheckResult(
                name,
                False,
                f"secret paths are already tracked, so .gitignore cannot help: "
                f"{', '.join(tracked)}. Untrack with "
                f"`git rm --cached {' '.join(tracked)}` and rotate what was committed.",
            )
        return CheckResult(
            name,
            False,
            f".gitignore does not cover secret paths: {', '.join(uncovered)}. "
            f"Run {_command(root, 'install-agents --upgrade')} to rewrite the managed block.",
        )

    return CheckResult(name, True, "secret paths (.env, .credentials/) are gitignored")


def _is_tracked(root: Path, relative_path: str) -> bool:
    try:
        completed = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative_path],
            cwd=root,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return completed.returncode == 0


def _ignored(root: Path, probe: str) -> bool | None:
    """True when git ignores *probe*, False when it does not, None when git cannot say."""
    try:
        completed = subprocess.run(
            ["git", "check-ignore", "-q", "--", probe],
            cwd=root,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    return None


# ── B3: reading sources that live outside the checkout ────────────────────────────
#
# `docs/required-reading.md` calls itself "the single index", and it indexed only files
# in the repository. Real operating rules live outside it on purpose — a recipient list
# or a credential agenda must not be tracked. On 2026-08-04 an agent that had read the
# whole contract could not find a project's e-mail recipients, because they live under
# `~/.config/` and nothing the contract told it to read mentioned the file.
#
# What is indexed is the path and one line of purpose. Never the content: the reason
# these files are outside the repository is that their content must not be copied into
# it, and an index that quotes them would defeat the arrangement it exists to describe.
_LOCAL_SOURCES_HEADING_RE = re.compile(
    r"^[ \t]{0,3}#{2,4}[ \t]+.*\b(fontes locais|local sources)\b", re.IGNORECASE
)
_ANY_HEADING_RE = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+\S")
# Tolerant on purpose: leading indentation, backticks optional, and any number of
# trailing columns. A stricter row regex made every table-authoring slip parse as zero
# rows, and zero rows is reported as "no local sources indexed" — a clean green that
# is indistinguishable from a required entry the check never saw.
_LOCAL_SOURCE_ROW_RE = re.compile(
    r"^[ \t]*\|\s*`?([^`|]+?)`?\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*(?:\|.*)?\|\s*$"
)
_OPTIONAL_WORDS = ("opcional", "optional")
_INDEX_REL = "docs/required-reading.md"

# An indexed source is an operator-local file. Restricting the shape keeps the index
# from becoming an existence oracle: `docs/required-reading.md` is tracked and anyone
# can propose a row, and a row naming `/etc/shadow` would turn doctor's own message
# into a probe of whatever machine runs it.
_HOME_RELATIVE_RE = re.compile(r"^(~/|\$\{?(?:HOME|XDG_[A-Z_]+)\}?/)")


@dataclass(frozen=True)
class LocalSource:
    path: str
    optional: bool
    purpose: str

    @property
    def expanded(self) -> Path:
        return Path(os.path.expandvars(self.path)).expanduser()

    def exists(self) -> bool:
        """`.exists()` that cannot take the whole `doctor` down with it.

        pathlib re-raises anything outside ENOENT/ENOTDIR/ELOOP, so a credential
        mounted 0400 under a root-owned directory — the ordinary shape of a Docker or
        Kubernetes secret — raised PermissionError straight out of the check list. One
        unreadable row killed every other check and the process exited on a traceback
        instead of a verdict. A gate that crashes reports nothing at all.
        """
        try:
            return self.expanded.exists()
        except OSError:
            # Unreadable is not absent: the operator has the file, this process
            # cannot stat it. Treating it as present keeps the check from failing a
            # correct setup for a permission it never needed.
            return True


def _parse_local_sources(root: Path) -> tuple[list[LocalSource], list[str]]:
    """Return the indexed local sources, and the rows that could not be read.

    Rows are `| path | obrigatório/opcional | purpose |`. The second value is the
    reason this returns a pair: a table the parser cannot read used to be reported as
    an empty table, so a required entry that a stray column or a missing backtick
    hid from the parser produced a clean green. Unreadable and absent must not look
    the same — that is how a gate stops gating without anyone noticing.
    """
    index = root / _INDEX_REL
    if not index.is_file():
        return [], []
    inside = False
    seen_table_line = False
    found: list[LocalSource] = []
    rejected: list[str] = []
    for line in index.read_text(encoding="utf-8", errors="replace").splitlines():
        if _ANY_HEADING_RE.match(line):
            inside = bool(_LOCAL_SOURCES_HEADING_RE.match(line))
            continue
        if not inside or not line.strip():
            continue
        if not line.lstrip().startswith("|"):
            continue
        row = _LOCAL_SOURCE_ROW_RE.match(line)
        if not row:
            seen_table_line = True
            rejected.append(line.strip())
            continue
        path, requirement, purpose = (group.strip() for group in row.groups())
        if set(path) <= {"-", ":", " "}:  # the |---|---| separator
            continue
        if path.lower() in {"caminho", "path"}:  # the header row
            continue
        # Only a DATA row counts as "this section has a table". The flag used to be set
        # on the header and the separator too, which made a header-only table — the
        # exact scaffold the kit now seeds into every new project — report as
        # "a table but no readable rows". A project that declares nothing is a valid
        # state, and the kit must not accuse its own starter of being malformed.
        # Council round 2 of AI-Agents#5.
        seen_table_line = True
        if not purpose:
            rejected.append(line.strip())
            continue
        if not _HOME_RELATIVE_RE.match(path) or ".." in Path(path).parts:
            rejected.append(line.strip())
            continue
        found.append(LocalSource(
            path=path,
            optional=any(word in requirement.lower() for word in _OPTIONAL_WORDS),
            purpose=purpose,
        ))
    # Unreachable by construction now that the flag marks data rows only: every data
    # row lands in `found` or in `rejected`. Kept as a tripwire — if a future branch
    # adds a third outcome, this says so instead of silently reporting zero sources.
    if seen_table_line and not found and not rejected:
        rejected.append("the section has a table but no readable rows")
    return found, rejected


def _local_sources(root: Path) -> list[LocalSource]:
    return _parse_local_sources(root)[0]


def _check_local_reading_sources(root: Path) -> CheckResult:
    """Every indexed local source exists — required ones fail, optional ones hint."""
    name = "local reading sources"
    sources, rejected = _parse_local_sources(root)
    if rejected:
        shown = "; ".join(rejected[:2])
        return CheckResult(
            name,
            False,
            f"{_INDEX_REL} has rows under `Fontes locais` this check cannot read, so "
            f"they are not being verified: {shown}. Rows are "
            f"`| ~/path | obrigatório\\|opcional | purpose |`, and the path must be "
            f"under the operator's home.",
            advisory=True,
        )
    if not sources:
        return CheckResult(name, True, "no local sources indexed", advisory=True)

    missing_required = [s.path for s in sources if not s.optional and not s.exists()]
    missing_optional = [s.path for s in sources if s.optional and not s.exists()]

    if missing_required:
        return CheckResult(
            name,
            False,
            f"{_INDEX_REL} indexes local sources that are absent here: "
            f"{', '.join(missing_required)}. Provide them, or mark the row `opcional` "
            f"if the work can proceed without it.",
        )
    if missing_optional:
        return CheckResult(
            name,
            True,
            f"optional local sources absent on this machine: {', '.join(missing_optional)}",
            advisory=True,
        )
    return CheckResult(name, True, f"{len(sources)} local source(s) indexed and present")


# A path that looks like an operator-local file: `~/...`, or `$HOME/...`, or an
# XDG-style state directory. Deliberately narrow — an absolute path under `/etc` or
# `/opt` is usually a deployment target, not something an agent is told to read.
#
# Backticks are NOT required. They were, and the council found the hole: AGENTS.md
# cites the 2026-08-04 incident file inside a ```bash fence, unquoted, four times.
# Isolating that citation made the check report "every local path is indexed" — so
# the fix closed the incident only because the same file happened to appear in an
# adjacent table too. Showing a path in a shell example is the most natural way to
# document "run this", and a detector that only sees prose misses the documentation
# people actually write.
_LOCAL_PATH_RE = re.compile(
    r"[`\s(\"']((?:~|\$\{?(?:HOME|XDG_[A-Z_]+)\}?)/[^`\s)\"',;]+)"
)
_CONTRACT_GLOBS = (
    "AGENTS.md",
    "CLAUDE.md",
    # Maintained mirrors of the same contract for other tool ecosystems. They carry
    # the same citations, and a local path added to only one of them would otherwise
    # never be seen.
    "GEMINI.md",
    ".cursorrules",
    ".github/copilot-instructions.md",
    ".amazonq/rules/*.md",
    "docs/*.md",
    ".docs/**/*.md",
)

# History, not instructions. `handoff.md` and the napkin record what happened, quoting
# paths from past sessions; scanning them produced `~/AGENTS.md` and `~/docs/limits.md`
# — artefacts of the 2026-08-04 home-shadow incident being *described*. Same
# mention-versus-use confusion that has cost this kit four detectors.
_CONTRACT_SCAN_SKIP = frozenset({
    "handoff.md", "napkin-lessons.md", "required-reading.md",
})


def _looks_like_a_directory(candidate: str) -> bool:
    """Filter the noise out of the citation scan before it reaches the operator.

    A contract naming `~/.config/` is telling you where a family of things lives, not
    handing you a file to read. Left in, four of the first seven hits on this very
    repository were directory prefixes — and noise in an advisory is not neutral: it
    teaches the operator to skim past the three real hits beside it, which here were
    the exact files from the 2026-08-04 incident.
    """
    if candidate.endswith("/"):
        return True
    # `~/.local/bin/awt` is invoked, not read. This is a *reading* index; a helper on
    # PATH belongs in the workflow that installs it, and listing it here would teach
    # that the index is a catalogue of everything rather than of what to read.
    if "bin" in Path(candidate).parts[:-1]:
        return True
    expanded = Path(os.path.expandvars(candidate)).expanduser()
    try:
        if expanded.is_dir():
            return True
        exists = expanded.exists()
    except OSError:
        # Unreadable says nothing about shape; fall through to the suffix heuristic
        # rather than letting a permission error out of an advisory check.
        exists = False
    # Absent from this machine: fall back to shape. A leaf with no suffix reads as a
    # directory far more often than as a file worth indexing. This makes the advisory
    # machine-dependent — CI, which has no operator state, sees fewer hits than the
    # operator's own laptop. Accepted: the alternative is either shape-only (which
    # misses every extensionless credential file that does exist) or no filter at all
    # (four of the first seven hits were directory prefixes).
    return not exists and not expanded.suffix


def _is_kit_owned(relative_path: str) -> bool:
    """Is this contract the kit's to replace, or the project's to write?

    The distinction decides whether a citation is evidence of a stale kit file or of a
    project exercising the rule that it must declare its own transport. `docs/` is the
    project's territory by the ownership rule no upgrade crosses; `AGENTS.md`, the
    adapter mirrors and `.docs/` are the kit's.
    """
    return not relative_path.startswith("docs/")


# Paths the kit ITSELF once prescribed in a contract and has since revoked. A citation
# of one of these is evidence of a stale contract in the target, never of a missing
# index row — see the branch in `_check_local_sources_indexed`.
_WITHDRAWN_CITATIONS: frozenset[str] = frozenset({
    "~/.config/email/send.py",
    "~/.config/email/credentials.conf",
})


def _check_local_sources_indexed(root: Path) -> CheckResult:
    """Advisory: a local path cited by a contract should be in the reading index.

    This is the half of B3 that is a detector, and detectors in this kit have a
    record: four scope defects in a row. So it hints, never fails. A path named in
    prose is not always a rule source — it can be an example, a migration note, or the
    very row in the index that declares it — and the cost of being wrong here is an
    operator learning to skim `doctor` output.
    """
    name = "local sources indexed"
    indexed = {source.path for source in _local_sources(root)}
    # Every citer, not the first. `setdefault` let whichever file the glob reached
    # first speak for the path: a legacy AGENTS.md then masked the project's own
    # declaration of the same transport, and the operator was told "do NOT index those"
    # about a path their own docs declare — with no way to clear it. Council round 2.
    cited_by: dict[str, list[str]] = {}
    for pattern in _CONTRACT_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file() or path.name in _CONTRACT_SCAN_SKIP:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for match in _LOCAL_PATH_RE.finditer(text):
                candidate = match.group(1)
                if _looks_like_a_directory(candidate):
                    continue
                cited_by.setdefault(candidate, []).append(
                    path.relative_to(root).as_posix()
                )

    # One citer decides nothing on its own. A path is WITHDRAWN-evidence only when a
    # KIT-OWNED file cites it; it is a project declaration when any project-owned file
    # does. Both can be true at once, and then both are reported.
    def _first_citer(path: str) -> str:
        return cited_by[path][0]

    withdrawn = sorted(
        path for path, wheres in cited_by.items()
        if path in _WITHDRAWN_CITATIONS and any(_is_kit_owned(w) for w in wheres)
    )
    project_declared = {
        path for path, wheres in cited_by.items()
        if any(not _is_kit_owned(w) for w in wheres)
    }
    unindexed = sorted(path for path in cited_by if path not in indexed)
    if not unindexed and not withdrawn:
        return CheckResult(name, True, "every local path a contract cites is indexed",
                           advisory=True)

    # A citation can come from a contract the kit has WITHDRAWN. Telling the operator to
    # index it is telling them to finish the corruption: these exact paths are the email
    # transport that AI-Agents#5 retired, and a target whose AGENTS.md was locally edited
    # keeps the old contract (protected files are never overwritten) with the corrected
    # one waiting unread in AGENTS.md.kit-new. Decidable by path, not by heuristic —
    # this set holds only what the kit itself once prescribed and has since revoked.
    # Council round 2 of AI-Agents#5.
    # Three corrections the council of this delivery reproduced, all in one branch:
    #
    # 1. It is decided by WHO CITES, not by path alone. A project naming that helper in
    #    its OWN docs is declaring its transport, which the contract requires; only a
    #    KIT-OWNED contract citing it is evidence of a stale file. Path-only matching
    #    told a legitimate project "do NOT add these to your index" — forbidding the
    #    one action §Sending Email step 1 demands — and sent it to an upgrade that
    #    never writes docs/, so the state it complained about could not be exited.
    # 2. It no longer RETURNS. The first cut swallowed every other unindexed path,
    #    including the recipient-list file whose absence from the index IS the
    #    2026-08-04 incident this whole check exists for.
    # 3. It is independent of indexing. The operator who followed the OLD advice and
    #    indexed the withdrawn path saw a clean PASS while still carrying the retired
    #    contract — the population the wrong message created was the one left blind.
    stale_sentence = ""
    if withdrawn:
        where = sorted({
            w for path in withdrawn for w in cited_by[path] if _is_kit_owned(w)
        })
        stale_sentence = (
            f"{', '.join(where)} still prescribes an email transport this kit has "
            f"WITHDRAWN ({', '.join(withdrawn)}) — do NOT index those; adopt the "
            f"`.kit-new` version beside it, or run `install-agents --upgrade`."
        )
        # A path the PROJECT also declares stays in the ordinary list: indexing it is
        # the right thing for the project's own copy, even while the kit's stale
        # contract is reported beside it.
        unindexed = [
            path for path in unindexed
            if path not in set(withdrawn) or path in project_declared
        ]

    if not unindexed:
        # R2-13: the sentence used to be written as a suffix and reused verbatim here,
        # so the operator's only line began with an orphan "SEPARATELY:".
        return CheckResult(name, False, stale_sentence, advisory=True)

    stale_note = f" SEPARATELY: {stale_sentence}" if stale_sentence else ""
    shown = ", ".join(f"{path} (in {_first_citer(path)})" for path in unindexed[:4])
    more = f" (+{len(unindexed) - 4} more)" if len(unindexed) > 4 else ""
    # `docs/` is the project's territory and `--upgrade` never writes prose there, so
    # a project installed before B3 will not receive the section from an upgrade — by
    # design, not by omission. This message is the delivery mechanism, and it fires
    # exactly when the section is needed: when a contract names a local file that
    # reading the index cannot lead you to. Say how to add it, or the hint is a
    # complaint.
    how = (
        f" Add a `## Fontes locais` section to {_INDEX_REL} with rows "
        f"`| ~/path | obrigatório\\|opcional | purpose |` — path and purpose only, "
        f"never content."
        if not _has_local_sources_section(root) else ""
    )
    return CheckResult(
        name,
        False,
        f"local paths cited by a contract but absent from {_INDEX_REL}: "
        f"{shown}{more}.{how}{stale_note}",
        advisory=True,
    )


def _has_local_sources_section(root: Path) -> bool:
    index = root / _INDEX_REL
    if not index.is_file():
        return False
    return any(
        _LOCAL_SOURCES_HEADING_RE.match(line)
        for line in index.read_text(encoding="utf-8", errors="replace").splitlines()
    )


def _check_gitignore_secret_coverage(root: Path) -> CheckResult:
    """Advisory: the secret patterns beyond the two mandatory probes, both ways.

    Two failures live here, and the quiet one is the second. Under-coverage leaves a
    real hole — `.env` ignored while `.env.local` is not is a common way to commit a
    credential. Over-coverage hides `.env.example`, so the block looks like it is
    working while the project silently loses the file it documents its configuration
    with; an operator who notices edits the managed block, and then the next upgrade
    overwrites the edit.

    Advisory on purpose. Both directions are real, and neither justifies failing a
    repository that was correct under the rules it was installed with.
    """
    name = "gitignore secret coverage"
    if not (root / ".git").exists():
        return CheckResult(name, True, "not a git repository", advisory=True)

    uncovered = [p for p in _SECRET_ADVISORY_PROBE_PATHS if _ignored(root, p) is False]
    swallowed = [p for p in _SECRET_TRACKABLE_PATHS if _ignored(root, p) is True]

    problems: list[str] = []
    if uncovered:
        problems.append(f"not ignored: {', '.join(uncovered)}")
    if swallowed:
        problems.append(f"ignored but must stay tracked: {', '.join(swallowed)}")
    if problems:
        return CheckResult(
            name,
            False,
            f"{'; '.join(problems)}. "
            f"{_command(root, 'install-agents --upgrade')} rewrites the managed block.",
            advisory=True,
        )

    return CheckResult(
        name, True, "secret variants covered and .env.example stays tracked", advisory=True
    )


def _count_newer_source_files(root: Path, since: float) -> int:
    """Count source files under root modified after timestamp since."""
    count = 0
    try:
        items = list(root.iterdir())
    except PermissionError:
        return 0
    for item in items:
        if item.is_symlink():
            continue
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
            f"docs/codemap.md missing — run '{_command(root, 'map')}' to generate it",
            advisory=True,
        )
    try:
        content = codemap.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return CheckResult("codemap", False, f"docs/codemap.md unreadable: {error}", advisory=True)
    required_sections = ("## Summary", "## Governance", "## Ignored Paths", "## File Tree")
    missing_sections = [section for section in required_sections if section not in content]
    if missing_sections:
        return CheckResult(
            "codemap",
            False,
            "docs/codemap.md uses an obsolete or incomplete format (missing: "
            + ", ".join(missing_sections)
            + f") — run '{_command(root, 'map')}'",
            advisory=True,
        )
    since = codemap.stat().st_mtime
    stale_count = _count_newer_source_files(root, since)
    if stale_count:
        return CheckResult(
            "codemap",
            False,
            f"docs/codemap.md is stale ({stale_count} source file(s) changed) — run '{_command(root, 'map')}'",
            advisory=True,
        )
    return CheckResult("codemap", True, "docs/codemap.md is up to date")
