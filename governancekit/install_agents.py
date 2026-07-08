from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REPO = "EDortta/AI-Agents"
# Pinned to a tagged release (not the mutable "main" branch) so installs are
# reproducible and can be checksum-verified. Bump alongside KNOWN_TARBALL_SHA256
# when a new AI-Agents release is adopted.
DEFAULT_REF = "v1.0.2"

# codeload.github.com tarball SHA-256 for (repo, ref) pairs we can vouch for.
# Only the upstream default repo/ref is pinned here; a custom --repo/--ref
# (e.g. a fork, or "main" for early access) is downloaded without verification,
# same as before this table existed.
KNOWN_TARBALL_SHA256: dict[tuple[str, str], str] = {
    (REPO, "v1.0.2"): "8746c817426deedef9384b8feeb6f4a3cae739f8599f9c71c0fec02722fea5ed",
}

# ── layout: kit lives in .docs/, project owns docs/ ──────────────────────────────
#
# Kit paths are written canonically as ``docs/…``. In the DESTINATION they map to
# ``.docs/…`` via ``_dest_rel`` so the host project's own ``docs/`` is never touched.
# In the SOURCE tree they are resolved via ``_resolve_src``, which reads from
# ``.docs/…`` when the source repo has been restructured and falls back to ``docs/…``
# for a legacy source — so both source layouts install correctly.
_SRC_DOC_PREFIX = "docs/"
_DST_DOC_PREFIX = ".docs/"

# Kit-owned documentation refreshed by --docs-only / --upgrade (source-relative).
# Overwritten wholesale on every upgrade — never put project-filled content here.
_KIT_DOC_PATHS: list[str] = [
    "docs/agents",
    "docs/workflows",
    "docs/articles",
    "docs/icons",
    "docs/issues/templates",
    "docs/issues/README.md",
]

# Kit-provided templates that the PROJECT fills in (readiness flags, overview text).
# Seeded on a fresh install (with flags reset) but NEVER overwritten on --upgrade,
# so the project's answers survive. They live under .docs/ (kit location).
_KIT_SEED_PATHS: list[str] = [
    "docs/software-overview.md",
    "docs/limits.md",
]

# Project-owned starter files: seeded once into docs/ (the project's territory) and
# never overwritten. They stay in docs/, not .docs/.
_PROJECT_SEED_PATHS: list[str] = [
    "docs/required-reading.md",
    "docs/napkin-lessons.md",
]

# Paths copied in a fresh install (source-relative). Replaces the old wholesale
# ``docs`` copy with explicit doc paths so the source repo's own active issues /
# project docs are never seeded into a brand-new project.
_FRESH_PATHS: list[str] = [
    "AGENTS.md",
    ".cursorrules",
    "CLAUDE.md",
    ".windsurfrules",
    "GEMINI.md",
    ".github/copilot-instructions.md",
    ".credentials",
    *_KIT_DOC_PATHS,
    *_KIT_SEED_PATHS,
    *_PROJECT_SEED_PATHS,
    "handoff.md",
    "new-tag.sh",
    "scripts/install-agents-kit.sh",
    "scripts/agent-worktree.sh",
]

# Paths replaced during --upgrade (dirs wholesale, files individually). Excludes the
# seed paths so project-filled overview/limits/required-reading/napkin survive.
_UPGRADE_PATHS: list[str] = [
    "AGENTS.md",
    ".cursorrules",
    "CLAUDE.md",
    ".windsurfrules",
    "GEMINI.md",
    ".github/copilot-instructions.md",
    "new-tag.sh",
    "scripts/install-agents-kit.sh",
    "scripts/agent-worktree.sh",
    *_KIT_DOC_PATHS,
]

# Alias kept for --docs-only callers and tests.
_DOCS_PATHS = _KIT_DOC_PATHS

# The project's documentation territory. Created on fresh install, never overwritten.
_PROJECT_DOCS_DIR = "docs"
_PROJECT_DOCS_README = """# Project Documentation

This folder is **yours**. The AI-Agents / GovernanceKit installer creates it once
and never touches it again — put project-specific documentation here freely and
track it in git.

Kit-managed documentation lives under `.docs/` (plus `AGENTS.md` and the per-tool
rule files) and is overwritten by `governancekit install-agents --upgrade` /
`--docs-only`. Do not edit kit-managed files by hand; record project knowledge here
instead.

List the documents an agent must read before analysing or implementing an issue in
`docs/required-reading.md`.
"""

# Kit-owned doc paths that legacy projects keep in docs/ and must be migrated to
# .docs/ (source/dest share the trailing name). Includes the seed templates.
# NB: HTML landing pages (index.html/concepts.html) are intentionally EXCLUDED. The
# legacy kit never shipped them under docs/, so a docs/index.html in a target project
# is the project's own page — migrating it would hide their site under .docs/.
_LEGACY_KIT_DOC_NAMES: list[str] = [
    "agents",
    "workflows",
    "articles",
    "icons",
    "software-overview.md",
    "limits.md",
]

_MIGRATION_BACKUP_DIR = ".docs-migration-bak"
_CONFIG_FILE = ".governancekit"

_GITIGNORE_BEGIN = "# AI-Agents kit — managed by governancekit install-agents"
_GITIGNORE_END = "# end AI-Agents kit"


@dataclass
class InstallResult:
    target: Path
    upgraded: bool
    paths_installed: list[str] = field(default_factory=list)
    gitignore_updated: bool = False
    gitignore_path: Path | None = None
    awt_installed: bool = False
    awt_message: str | None = None
    migrated: bool = False
    migration_notes: list[str] = field(default_factory=list)
    track_kit_docs: bool = False


def _dest_rel(src_rel: str) -> str:
    """Map a canonical path to its destination-relative path.

    Kit-owned docs move from ``docs/`` to ``.docs/``. Project-owned seed files keep
    living in ``docs/``. Everything else is unchanged.
    """
    if src_rel in _PROJECT_SEED_PATHS:
        return src_rel
    if src_rel == "docs":
        return ".docs"
    if src_rel.startswith(_SRC_DOC_PREFIX):
        return _DST_DOC_PREFIX + src_rel[len(_SRC_DOC_PREFIX):]
    return src_rel


def _resolve_src(src_root: Path, rel: str) -> Path:
    """Resolve where a kit path actually lives in the downloaded source tree.

    Paths are canonical (``docs/…``). A restructured source repo stores kit-owned
    docs under ``.docs/…`` while project-owned seeds (``required-reading.md``,
    ``napkin-lessons.md``) stay in ``docs/…``. This prefers the ``.docs/`` location
    when present and falls back to ``docs/`` — so the installer reads correctly from
    both a restructured source and a legacy one.
    """
    if rel not in _PROJECT_SEED_PATHS and rel.startswith(_SRC_DOC_PREFIX):
        dotted = src_root / (_DST_DOC_PREFIX + rel[len(_SRC_DOC_PREFIX):])
        if dotted.exists():
            return dotted
    return src_root / rel


def run_install_agents(
    root: Path,
    *,
    ref: str = DEFAULT_REF,
    repo: str = REPO,
    force: bool = False,
    upgrade: bool = False,
    docs_only: bool = False,
    track: bool | None = None,
    install_awt: bool = False,
) -> InstallResult:
    """Download and install AI-Agents kit into *root*.

    Kit-owned documentation is installed under ``.docs/``; the host project keeps
    ``docs/`` for its own documentation. Whether ``.docs/`` is tracked in git is
    resolved via ``track`` (CLI), a persisted ``.governancekit`` config, or an
    interactive prompt — see ``_resolve_track_kit_docs``.

    ``docs_only`` refreshes only kit-owned documentation (``_KIT_DOC_PATHS``) without
    touching ``AGENTS.md`` or the per-tool rule files — a narrower update than
    ``upgrade``.

    ``install_awt`` opts into automatically running the downloaded
    ``agent-worktree.sh install`` (which symlinks ``awt`` onto PATH). Off by
    default: it executes code from the downloaded kit, so it should be an
    explicit choice rather than an automatic side effect of installing docs.
    """
    root = root.resolve()

    result = InstallResult(target=root, upgraded=upgrade or docs_only)

    # Migrate a legacy layout (kit in docs/, project in docs/project/) BEFORE any
    # upgrade write, so kit content lands in .docs/ and project docs are preserved.
    if upgrade or docs_only:
        migrated, notes = _migrate_legacy_layout(root)
        result.migrated = migrated
        result.migration_notes = notes

    with tempfile.TemporaryDirectory() as tmp:
        src_root = _download(repo, ref, Path(tmp))

        if docs_only:
            result.paths_installed = _do_upgrade(src_root, root, paths=_KIT_DOC_PATHS)
        elif upgrade:
            result.paths_installed = _do_upgrade(src_root, root)
        else:
            result.paths_installed = _do_fresh(src_root, root, force=force)

        # Idempotent: seeds docs/ on fresh install and lets existing installs adopt
        # it on --upgrade / --docs-only without overwriting it.
        _ensure_project_docs(root)

        track_kit_docs = _resolve_track_kit_docs(root, track)
        result.track_kit_docs = track_kit_docs

        gitignore_path = root / ".gitignore"
        # The managed section always lists the secrets (.credentials, handoff.md)
        # and rule files so they stay untracked regardless of run mode. Whether
        # .docs/ is listed depends on the track-kit-docs choice. Always derive the
        # section from the full _FRESH_PATHS list (not the narrower upgrade scope) so
        # secrets are never dropped.
        _update_gitignore(gitignore_path, _FRESH_PATHS, track_kit_docs=track_kit_docs)
        result.gitignore_updated = True
        result.gitignore_path = gitignore_path

    _fill_placeholders(root, result.paths_installed)
    if install_awt and _dest_rel("scripts/agent-worktree.sh") in result.paths_installed:
        result.awt_installed, result.awt_message = _install_awt(root)
    elif _dest_rel("scripts/agent-worktree.sh") in result.paths_installed:
        result.awt_message = "skipped (pass --install-awt to symlink 'awt' onto PATH)"
    return result


def _install_awt(root: Path) -> tuple[bool, str | None]:
    """Symlink the worktree helper as ``awt`` on PATH (best-effort).

    The helper *is* ``scripts/agent-worktree.sh``; its own ``install`` subcommand
    creates the symlink (default ``~/.local/bin/awt``). Failure here never fails
    the kit install — we just report what happened so the user can finish by hand.
    """
    script = root / "scripts" / "agent-worktree.sh"
    if not script.is_file():
        return False, None
    try:
        proc = subprocess.run(
            ["bash", str(script), "install"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"could not run 'awt install': {exc}"
    msg = (proc.stdout + proc.stderr).strip() or None
    if proc.returncode != 0:
        return False, msg or f"'awt install' exited {proc.returncode}"
    return True, msg


# ── download ───────────────────────────────────────────────────────────────────

def _download(repo: str, ref: str, tmp: Path) -> Path:
    url = f"https://codeload.github.com/{repo}/tar.gz/{ref}"
    archive = tmp / "src.tar.gz"
    try:
        urllib.request.urlretrieve(url, archive)  # noqa: S310
    except Exception as exc:
        raise RuntimeError(f"Failed to download {url}: {exc}") from exc

    known_sha256 = KNOWN_TARBALL_SHA256.get((repo, ref))
    if known_sha256 is not None:
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        if actual != known_sha256:
            raise RuntimeError(
                f"Checksum mismatch for {url}: expected {known_sha256}, got {actual}. "
                "Refusing to install — the tarball may have been tampered with or "
                "the pinned checksum is stale."
            )
    else:
        print(
            f"Warning: no known checksum for {repo}@{ref} — installing unverified. "
            f"Use the default repo/ref for a checksum-verified install.",
            file=sys.stderr,
        )

    with tarfile.open(archive, "r:gz") as tf:
        _safe_extractall(tf, tmp)

    extracted = [p for p in tmp.iterdir() if p.is_dir() and p.name != archive.name]
    if not extracted:
        raise RuntimeError("Unexpected archive structure — no top-level directory found.")
    return extracted[0]


def _safe_extractall(tf: tarfile.TarFile, dest: Path) -> None:
    """Extract *tf* into *dest*, rejecting members that would escape it (tar-slip).

    Prefers the stdlib ``filter="data"`` (Python 3.10.12+/3.11.4+) which already
    rejects absolute paths, ``..`` traversal, and unsafe links. Falls back to
    manual member validation on older patch releases where the kwarg is absent.
    """
    try:
        tf.extractall(dest, filter="data")
        return
    except TypeError:
        pass

    dest_resolved = dest.resolve()
    safe_members = []
    for member in tf.getmembers():
        member_path = (dest / member.name).resolve()
        if member_path != dest_resolved and dest_resolved not in member_path.parents:
            raise RuntimeError(f"Refusing to extract unsafe tar member: {member.name!r}")
        if member.issym() or member.islnk():
            link_target = (member_path.parent / member.linkname).resolve()
            if link_target != dest_resolved and dest_resolved not in link_target.parents:
                raise RuntimeError(f"Refusing to extract unsafe tar link: {member.name!r}")
        safe_members.append(member)
    tf.extractall(dest, members=safe_members)


# ── fresh install ──────────────────────────────────────────────────────────────

_CONFLICT_FORCE_THRESHOLD = 0.10  # suggest --force when conflicts exceed this ratio


def _do_fresh(src: Path, dst: Path, *, force: bool) -> list[str]:
    available = [rel for rel in _FRESH_PATHS if _resolve_src(src, rel).exists()]
    # Conflicts are checked against the DESTINATION path (docs/ → .docs/).
    conflicts = [rel for rel in available if (dst / _dest_rel(rel)).exists()]

    skip: set[str] = set()

    if conflicts and not force:
        ratio = len(conflicts) / len(available) if available else 0
        if ratio > _CONFLICT_FORCE_THRESHOLD:
            print(
                f"Warning: {len(conflicts)} of {len(available)} paths already exist "
                f"({ratio:.0%}). Consider using --force to overwrite all at once."
            )

        interactive = sys.stdin.isatty()
        for rel in conflicts:
            dest_rel = _dest_rel(rel)
            if interactive:
                try:
                    answer = input(f"  '{dest_rel}' already exists — overwrite? [y/N] ").strip().lower()
                except EOFError:
                    answer = ""
                if answer != "y":
                    print(f"  skipped: {dest_rel}")
                    skip.add(rel)
            else:
                print(f"Warning: '{dest_rel}' already exists, skipping.")
                skip.add(rel)

    installed: list[str] = []
    for rel in available:
        if rel in skip:
            continue
        src_path = _resolve_src(src, rel)
        dst_path = dst / _dest_rel(rel)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if dst_path.exists():
            if dst_path.is_dir():
                shutil.rmtree(dst_path)
            else:
                dst_path.unlink()
        if src_path.is_dir():
            shutil.copytree(src_path, dst_path)
        else:
            shutil.copy2(src_path, dst_path)
        installed.append(_dest_rel(rel))

    _reset_readiness_flags(dst)
    return installed


def _reset_readiness_flags(root: Path) -> None:
    for rel, pattern, replacement in [
        (
            ".docs/software-overview.md",
            "- project_context_ready: yes",
            "- project_context_ready: no",
        ),
        (
            ".docs/limits.md",
            "- limits_ready: yes",
            "- limits_ready: no",
        ),
    ]:
        path = root / rel
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            path.write_text(text.replace(pattern, replacement), encoding="utf-8")


# ── upgrade ────────────────────────────────────────────────────────────────────

def _do_upgrade(src: Path, dst: Path, *, paths: list[str] | None = None) -> list[str]:
    installed: list[str] = []
    for rel in (paths if paths is not None else _UPGRADE_PATHS):
        src_path = _resolve_src(src, rel)
        dst_path = dst / _dest_rel(rel)
        if not src_path.exists():
            continue
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if src_path.is_dir():
            if dst_path.exists():
                shutil.rmtree(dst_path)
            shutil.copytree(src_path, dst_path)
        else:
            shutil.copy2(src_path, dst_path)
        installed.append(_dest_rel(rel))
    return installed


# ── legacy layout migration ──────────────────────────────────────────────────────

def _migrate_legacy_layout(root: Path) -> tuple[bool, list[str]]:
    """Migrate a legacy install (kit in ``docs/``, project in ``docs/project/``).

    Moves kit-owned docs from ``docs/`` to ``.docs/`` and promotes ``docs/project/*``
    up into ``docs/`` (the new project territory). Backs ``docs/`` up first. A no-op
    if ``.docs/`` already exists (already migrated) or no legacy markers are present.

    Returns ``(migrated, notes)`` where *notes* is a human-readable report.
    """
    docs = root / "docs"
    dotdocs = root / ".docs"
    # Legacy markers must be KIT-SPECIFIC. A generic name like docs/software-overview.md
    # is a common project filename; triggering on it would relocate a non-kit project's
    # whole docs/ (e.g. a GitHub Pages site) into the hidden .docs/. Require a marker a
    # random project is extremely unlikely to own: the kit's agents/ rule dir or its
    # workflows/session-close.md.
    markers = [docs / "agents", docs / "workflows" / "session-close.md"]
    if not docs.is_dir() or not any(m.exists() for m in markers):
        return False, []

    notes: list[str] = []
    # A pre-existing .docs/ usually means migration already completed → the marker
    # check above would have found nothing to do. Reaching here WITH .docs/ present
    # means a prior run was interrupted (or .docs/ is stray) while kit files are still
    # in docs/: complete the migration below, never overwriting what .docs/ already has,
    # instead of silently stranding the kit files in docs/ forever.
    if dotdocs.exists():
        notes.append(
            "note: .docs/ already existed — completing an interrupted migration "
            "without overwriting existing .docs/ entries"
        )

    # 1. Backup the whole docs/ tree before touching anything.
    backup = root / _MIGRATION_BACKUP_DIR
    if not backup.exists():
        shutil.copytree(docs, backup)
        notes.append(f"backup: docs/ → {_MIGRATION_BACKUP_DIR}/")

    # 2. Move kit-owned docs from docs/ to .docs/.
    dotdocs.mkdir(parents=True, exist_ok=True)
    for name in _LEGACY_KIT_DOC_NAMES:
        legacy = docs / name
        if not legacy.exists():
            continue
        if (dotdocs / name).exists():
            notes.append(
                f"skip: .docs/{name} already present — docs/{name} left in place "
                f"(also preserved in {_MIGRATION_BACKUP_DIR}/)"
            )
            continue
        shutil.move(str(legacy), str(dotdocs / name))
        notes.append(f"kit: docs/{name} → .docs/{name}")
    # issues/templates and issues/README.md are kit-owned; the rest of docs/issues/
    # (active issues) belongs to the project and stays.
    legacy_issues = docs / "issues"
    if legacy_issues.is_dir():
        (dotdocs / "issues").mkdir(exist_ok=True)
        for name in ("templates", "README.md"):
            legacy = legacy_issues / name
            if not legacy.exists():
                continue
            if (dotdocs / "issues" / name).exists():
                notes.append(f"skip: .docs/issues/{name} already present — left docs/issues/{name} in place")
                continue
            shutil.move(str(legacy), str(dotdocs / "issues" / name))
            notes.append(f"kit: docs/issues/{name} → .docs/issues/{name}")

    # 3. Promote docs/project/* into docs/ (project territory), reporting collisions.
    project = docs / "project"
    if project.is_dir():
        for child in sorted(project.iterdir()):
            target = docs / child.name
            if target.exists():
                notes.append(
                    f"SKIP (collision): docs/project/{child.name} kept in "
                    f"{_MIGRATION_BACKUP_DIR}/project/ — resolve manually"
                )
                continue
            shutil.move(str(child), str(target))
            notes.append(f"project: docs/project/{child.name} → docs/{child.name}")
        # Remove docs/project/ if now empty.
        remaining = list(project.iterdir())
        if not remaining:
            project.rmdir()
            notes.append("removed empty docs/project/")

    return True, notes


# ── project-owned docs ──────────────────────────────────────────────────────────

def _ensure_project_docs(root: Path) -> None:
    """Create the project-owned ``docs/`` folder once, never overwrite it."""
    project_dir = root / _PROJECT_DOCS_DIR
    readme = project_dir / "README.md"
    if readme.exists():
        return
    project_dir.mkdir(parents=True, exist_ok=True)
    readme.write_text(_PROJECT_DOCS_README, encoding="utf-8")


# ── track-kit-docs config ─────────────────────────────────────────────────────────

def _read_kit_config(root: Path) -> dict:
    path = root / _CONFIG_FILE
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_kit_config(root: Path, config: dict) -> None:
    path = root / _CONFIG_FILE
    path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve_track_kit_docs(root: Path, cli_value: bool | None) -> bool:
    """Decide whether kit docs (``.docs/``) are tracked in git.

    Priority: explicit CLI flag → persisted ``.governancekit`` config → interactive
    prompt (persisted) → default False (kit docs stay gitignored).
    """
    if cli_value is not None:
        _write_kit_config(root, {**_read_kit_config(root), "track_kit_docs": cli_value})
        return cli_value

    config = _read_kit_config(root)
    if "track_kit_docs" in config:
        return bool(config["track_kit_docs"])

    if sys.stdin.isatty():
        try:
            answer = input(
                "Track the kit documentation (.docs/) in git? [y/N] "
            ).strip().lower()
        except EOFError:
            answer = ""
        choice = answer == "y"
        _write_kit_config(root, {**config, "track_kit_docs": choice})
        return choice

    return False


# ── placeholder resolution ─────────────────────────────────────────────────────

_PLACEHOLDER_RE = re.compile(r"\[([A-Z][A-Z0-9_]+)\]")

_PLACEHOLDER_DESCRIPTIONS: dict[str, str] = {
    "OPERATOR_NAME": "operator / project owner name (used in agent greetings)",
    "GITHUB_OWNER": "GitHub username or organisation that owns the repo",
    "PROJECT_SLUG": "short identifier for this project (used in work_ids and logs, e.g. my-app)",
    "SMTP_ACCOUNT": "SMTP email account (e.g. you@yourdomain.com)",
    "SMTP_DOMAIN": "email domain (e.g. yourdomain.com)",
    "ORG_NAME": "organisation or company name",
    "PIX_KEY_UUID": "PIX random key UUID (Brazil payment system)",
    "PIX_HOLDER_NAME": "full name registered with the PIX key",
    "PIX_PAYLOAD": "full PIX copy-and-paste payload string",
    "PIX_QR_BASE64": "base64-encoded PNG of the PIX QR code",
    "PROJECT_ROOT": "absolute path to the project root on this machine",
    "KOFI_HANDLE": "Ko-fi username (e.g. yourhandle)",
    "ETH_WALLET_ADDRESS": "Ethereum wallet address for donations (0x...)",
}


def _fill_placeholders(root: Path, installed_paths: list[str]) -> None:
    """Scan installed files for known [PLACEHOLDER] tokens and prompt for values.

    Only tokens described in ``_PLACEHOLDER_DESCRIPTIONS`` are treated as fillable
    variables. Arbitrary ``[WORD]`` tokens that merely appear as documentation
    examples (e.g. the literal ``[PLACEHOLDER]`` / ``[TOKEN]`` used to *explain* the
    mechanism) are skipped instead of being prompted for. Mirrors ``configure.py``.
    """
    # Collect all unique placeholders across installed files
    placeholder_files: dict[str, list[Path]] = {}
    for rel in installed_paths:
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for token in _PLACEHOLDER_RE.findall(text):
            if token in _PLACEHOLDER_DESCRIPTIONS:
                placeholder_files.setdefault(token, []).append(path)

    if not placeholder_files:
        return

    if not sys.stdin.isatty():
        print(
            "\nWarning: the following placeholders were not filled "
            "(no interactive terminal):\n  "
            + ", ".join(f"[{p}]" for p in sorted(placeholder_files))
        )
        return

    print("\n── Configure installed kit ────────────────────────────────────────")
    print("The following values are required. Press Enter to skip any item.\n")

    values: dict[str, str] = {}
    for token in sorted(placeholder_files):
        desc = _PLACEHOLDER_DESCRIPTIONS.get(token, "")
        prompt = f"  [{token}]"
        if desc:
            prompt += f"  ({desc})"
        prompt += ": "
        try:
            answer = input(prompt).strip()
        except EOFError:
            answer = ""
        if answer:
            values[token] = answer

    if not values:
        print("\nNo values provided — placeholders left as-is.")
        return

    # Apply substitutions
    changed: list[str] = []
    seen_paths: set[Path] = set()
    for token, val in values.items():
        for path in placeholder_files.get(token, []):
            if path not in seen_paths:
                seen_paths.add(path)
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            new_text = text
            for t, v in values.items():
                new_text = new_text.replace(f"[{t}]", v)
            if new_text != text:
                path.write_text(new_text, encoding="utf-8")
                changed.append(str(path.relative_to(root)))

    if changed:
        print("\nPlaceholders filled in: " + ", ".join(sorted(set(changed))))

    # Warn about any that were skipped
    unfilled = [t for t in placeholder_files if t not in values]
    if unfilled:
        print(
            "Still unfilled (skipped): "
            + ", ".join(f"[{t}]" for t in sorted(unfilled))
        )


# ── .gitignore management ──────────────────────────────────────────────────────

def _gitignore_entries(paths: list[str], *, track_kit_docs: bool = False) -> list[str]:
    """Build .gitignore entries for the managed section.

    Kit docs live under ``.docs/`` — a single ``.docs/`` entry ignores them unless
    the user chose to track them (``track_kit_docs``). Project-owned files under
    ``docs/`` are never listed (they stay tracked). Secrets and rule files are always
    listed so they stay untracked regardless of the track-kit-docs choice.
    """
    entries: list[str] = []
    dotdocs_added = False
    for rel in paths:
        dest = _dest_rel(rel)
        if dest == ".docs" or dest.startswith(_DST_DOC_PREFIX):
            if track_kit_docs:
                continue
            if not dotdocs_added:
                entries.append(".docs/")
                dotdocs_added = True
        elif dest.startswith(_SRC_DOC_PREFIX):
            # Project-owned docs/ files: keep tracked.
            continue
        else:
            entries.append(dest)
    # The legacy-migration backup is a full copy of the pre-migration docs/ tree and
    # must never be committed. Always ignore it, independent of track-kit-docs.
    entries.append(f"{_MIGRATION_BACKUP_DIR}/")
    return entries


def _update_gitignore(gitignore: Path, paths: list[str], *, track_kit_docs: bool = False) -> None:
    existing = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    cleaned = _remove_section_text(existing)
    entries = "\n".join(_gitignore_entries(paths, track_kit_docs=track_kit_docs))
    section = f"\n{_GITIGNORE_BEGIN}\n{entries}\n{_GITIGNORE_END}\n"
    gitignore.write_text(cleaned.rstrip("\n") + section, encoding="utf-8")


def _remove_gitignore_section(gitignore: Path) -> bool:
    """Remove the kit section from .gitignore; returns True if a change was made."""
    text = gitignore.read_text(encoding="utf-8")
    cleaned = _remove_section_text(text)
    if cleaned == text:
        return False
    gitignore.write_text(cleaned, encoding="utf-8")
    return True


def _remove_section_text(text: str) -> str:
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.rstrip("\n")
        if stripped == _GITIGNORE_BEGIN:
            in_section = True
            continue
        if stripped == _GITIGNORE_END:
            in_section = False
            continue
        if not in_section:
            result.append(line)
    return "".join(result)
