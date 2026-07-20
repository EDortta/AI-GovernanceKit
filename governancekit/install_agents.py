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
# Kit-authored files here are replaced on upgrade; files the PROJECT added into these
# directories are preserved (see ``_sync_dir`` and the manifest below).
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

# Durable install state, in one hidden JSON. Two jobs:
#
# "files" — hash of each kit file AS IT ENDED UP ON DISK, recorded *after* placeholder
#   substitution. Hashing the pristine template instead would never match a file whose
#   [OPERATOR_NAME]/[SMTP_ACCOUNT] were filled in, so every configured file would look
#   locally edited and ownership would be undecidable exactly where the kit needs it.
#
# "metadata" — the operator's answers. Kept out of the files themselves so an upgrade,
#   which overwrites those files with fresh templates, can re-apply what it already
#   knows and only ask about variables it has never seen.
#
# Absent state (every install made before this existed) is deliberately read as
# "nothing is known to be kit-owned": the upgrade then refreshes what the new kit
# ships and deletes NOTHING. Safe by default — the cost is that a file genuinely
# retired upstream lingers until the first state-backed upgrade records it.
_STATE_DIR = ".gk"
# Split by who may read it, because the two halves have opposite requirements.
#
# manifest.json is COMMITTED: file hashes are not secret, and a team sharing a
# checkout must share them — that is what makes every programmer's upgrade decide
# ownership the same way. Non-sensitive answers (operator, org, repo owner) ride
# along so a teammate's first run is not re-interrogated.
#
# secrets.json is GITIGNORED: SMTP account, PIX keys, wallet address. Per-machine.
# If a team genuinely needs to share these, encrypt this file to the RECIPIENTS'
# public keys (sops/age) — never "encrypt with the origin machine's private key",
# which only signs and leaves the content readable to anyone holding the public key.
_STATE_FILE = f"{_STATE_DIR}/manifest.json"
_SECRETS_FILE = f"{_STATE_DIR}/secrets.json"
_STATE_VERSION = 1

# Answers that must never be committed. Everything else is shareable project context.
_SENSITIVE_PLACEHOLDERS: frozenset[str] = frozenset({
    "SMTP_ACCOUNT",
    "PIX_KEY_UUID",
    "PIX_HOLDER_NAME",
    "PIX_PAYLOAD",
    "PIX_QR_BASE64",
    "ETH_WALLET_ADDRESS",
    "KOFI_HANDLE",
    # Not a secret, but an absolute path on one machine — sharing it would point a
    # teammate's agents at a directory that does not exist for them.
    "PROJECT_ROOT",
})

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
    # Files inside kit-owned directories that the upgrade refused to delete because
    # they are project-authored, or kit files the project has since edited.
    preserved_paths: list[str] = field(default_factory=list)
    had_state: bool = False
    # Kit files the project had edited by hand; the new kit version replaced them and
    # a copy of the edit was stashed under .gk/overwritten/.
    overwritten_edits: list[str] = field(default_factory=list)
    metadata_known: list[str] = field(default_factory=list)


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
    # Read before any write: the upgrade needs the PREVIOUS hashes to judge ownership,
    # and the previous answers to avoid re-interrogating the operator.
    state = _read_state(root)

    # Migrate a legacy layout (kit in docs/, project in docs/project/) BEFORE any
    # upgrade write, so kit content lands in .docs/ and project docs are preserved.
    if upgrade or docs_only:
        migrated, notes = _migrate_legacy_layout(root)
        result.migrated = migrated
        result.migration_notes = notes

    with tempfile.TemporaryDirectory() as tmp:
        src_root = _download(repo, ref, Path(tmp))

        if docs_only or upgrade:
            result.had_state = bool(state)
            scope = _KIT_DOC_PATHS if docs_only else None
            result.paths_installed = _do_upgrade(
                src_root,
                root,
                paths=scope,
                manifest=_state_files(state),
                preserved=result.preserved_paths,
                overwritten=result.overwritten_edits,
            )
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

    metadata = _fill_placeholders(
        root, result.paths_installed, known=_state_metadata(state)
    )
    result.metadata_known = sorted(metadata)
    # Written last: hashes must describe the files as they stand AFTER substitution,
    # so a configured file still matches its own record on the next upgrade.
    _write_state(root, result.paths_installed, repo=repo, ref=ref, metadata=metadata)

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

def _do_upgrade(
    src: Path,
    dst: Path,
    *,
    paths: list[str] | None = None,
    manifest: dict[str, str] | None = None,
    preserved: list[str] | None = None,
    overwritten: list[str] | None = None,
) -> list[str]:
    installed: list[str] = []
    known = manifest if manifest is not None else {}
    for rel in (paths if paths is not None else _UPGRADE_PATHS):
        src_path = _resolve_src(src, rel)
        dst_path = dst / _dest_rel(rel)
        if not src_path.exists():
            continue
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if src_path.is_dir():
            _sync_dir(src_path, dst_path, dst, known, preserved, overwritten)
        else:
            shutil.copy2(src_path, dst_path)
        installed.append(_dest_rel(rel))
    return installed


def _sync_dir(
    src_dir: Path,
    dst_dir: Path,
    root: Path,
    known: dict[str, str],
    preserved: list[str] | None,
    overwritten: list[str] | None = None,
) -> None:
    """Refresh a kit-owned directory without discarding project-authored files.

    Replaces every file the new kit ships. A destination file the kit does NOT ship
    is removed only when the manifest proves the kit itself wrote it AND its content
    is still byte-identical to what was written — i.e. it was retired upstream and
    the project never touched it. Anything else (project-authored, or kit-authored
    but locally edited) is kept and reported through *preserved*.

    This replaces an earlier ``rmtree`` + ``copytree``, which deleted project rules
    that lived inside kit directories.
    """
    dst_dir.mkdir(parents=True, exist_ok=True)

    shipped: set[Path] = set()
    for src_file in sorted(p for p in src_dir.rglob("*") if p.is_file()):
        rel = src_file.relative_to(src_dir)
        target = dst_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        # A kit file the project edited by hand is still kit-owned, so the new version
        # wins — but the edit is real intent and must not vanish silently. Stash it and
        # report it. Only detectable because the state records the hash as written.
        if target.is_file() and overwritten is not None:
            rel_to_root = target.relative_to(root).as_posix()
            recorded = known.get(rel_to_root)
            if recorded is not None and recorded != _file_sha256(target):
                backup = root / _STATE_DIR / "overwritten" / rel_to_root
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                overwritten.append(rel_to_root)
        shutil.copy2(src_file, target)
        shipped.add(target)

    for existing in sorted(p for p in dst_dir.rglob("*") if p.is_file()):
        if existing in shipped:
            continue
        rel_to_root = existing.relative_to(root).as_posix()
        recorded = known.get(rel_to_root)
        if recorded is not None and recorded == _file_sha256(existing):
            existing.unlink()
            continue
        if preserved is not None:
            preserved.append(rel_to_root)

    # Directories emptied by the retirement pass above carry no information; leave
    # any directory that still holds preserved files untouched.
    for d in sorted((p for p in dst_dir.rglob("*") if p.is_dir()), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()


# ── install state (.gk/state.json) ─────────────────────────────────────────────

def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_state(root: Path) -> dict:
    """Load ``.gk/state.json``; an absent or corrupt file yields an empty state.

    Empty means "nothing is provably kit-owned and nothing is known about the
    operator" — which makes the upgrade preserve files and ask questions, never
    delete or assume.
    """
    state = _read_json(root / _STATE_FILE)
    secrets = _read_json(root / _SECRETS_FILE)
    if not secrets:
        return state
    # Present the two files to callers as one logical state; only _write_state knows
    # they are stored apart.
    merged = dict(state)
    merged["metadata"] = {
        **_state_metadata(state),
        **_state_metadata(secrets),
    }
    return merged


def _state_files(state: dict) -> dict[str, str]:
    files = state.get("files")
    return files if isinstance(files, dict) else {}


def _state_metadata(state: dict) -> dict[str, str]:
    meta = state.get("metadata")
    return {k: v for k, v in meta.items() if isinstance(v, str)} if isinstance(meta, dict) else {}


def _write_state(
    root: Path,
    installed: list[str],
    *,
    repo: str,
    ref: str,
    metadata: dict[str, str],
) -> None:
    """Persist file hashes and operator answers.

    Call this AFTER placeholder substitution: the recorded hash must describe the file
    as it actually sits on disk, otherwise a configured file never matches its own
    record and looks hand-edited forever.

    Merges over the previous state rather than replacing it — ``--docs-only`` touches a
    narrow scope, and dropping what it did not touch would make the next full upgrade
    forget that e.g. ``AGENTS.md`` is kit-owned, or forget an answer already given.
    """
    previous = _read_state(root)
    files: dict[str, str] = dict(_state_files(previous))
    for rel in installed:
        target = root / rel
        if target.is_file():
            files[rel] = _file_sha256(target)
        elif target.is_dir():
            for f in sorted(p for p in target.rglob("*") if p.is_file()):
                files[f.relative_to(root).as_posix()] = _file_sha256(f)

    merged_meta = {**_state_metadata(previous), **metadata}
    shareable = {k: v for k, v in merged_meta.items() if k not in _SENSITIVE_PLACEHOLDERS}
    sensitive = {k: v for k, v in merged_meta.items() if k in _SENSITIVE_PLACEHOLDERS}

    state_dir = root / _STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    # Self-contained ignore rules, matching the bash installer: manifest.json stays
    # tracked (the team shares it), the credential half and the stash never do. Kept
    # here so the guarantee holds even in a project whose root .gitignore we did not
    # write — the secrets file must never depend on that having gone well.
    (state_dir / ".gitignore").write_text(
        "# Managed by governancekit.\n"
        "# manifest.json is intentionally NOT ignored — the team must share it.\n"
        "secrets.json\n"
        "overwritten/\n",
        encoding="utf-8",
    )

    (root / _STATE_FILE).write_text(
        json.dumps(
            {
                "state_version": _STATE_VERSION,
                "repo": repo,
                "ref": ref,
                "metadata": shareable,
                "files": files,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    # Written only when there is something to write, so a project with no secrets
    # never grows a confusing empty file.
    if sensitive:
        secrets_path = root / _SECRETS_FILE
        secrets_path.write_text(
            json.dumps(
                {"state_version": _STATE_VERSION, "metadata": sensitive},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        secrets_path.chmod(0o600)


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


def _fill_placeholders(
    root: Path,
    installed_paths: list[str],
    *,
    known: dict[str, str] | None = None,
) -> dict[str, str]:
    """Scan installed files for known [PLACEHOLDER] tokens and fill them in.

    Only tokens described in ``_PLACEHOLDER_DESCRIPTIONS`` are treated as fillable
    variables. Arbitrary ``[WORD]`` tokens that merely appear as documentation
    examples (e.g. the literal ``[PLACEHOLDER]`` / ``[TOKEN]`` used to *explain* the
    mechanism) are skipped instead of being prompted for. Mirrors ``configure.py``.

    *known* carries answers from previous runs (``.gk/state.json``). They are offered
    as the default so the operator confirms with Enter instead of retyping, and they
    are applied without any prompt when there is no terminal — which is what gives an
    unattended ``--upgrade`` continuity across the template overwrite.

    Returns every value in force after this run, for the caller to persist.
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

    known = known or {}

    if not placeholder_files:
        return dict(known)

    remembered = {t: known[t] for t in placeholder_files if known.get(t)}
    unknown = [t for t in sorted(placeholder_files) if t not in remembered]

    if not sys.stdin.isatty():
        # Unattended: re-apply what we already know rather than leaving raw templates
        # behind, and report only what genuinely has no answer yet.
        values = dict(remembered)
        if unknown:
            print(
                "\nWarning: the following placeholders were not filled "
                "(no interactive terminal, no stored value):\n  "
                + ", ".join(f"[{p}]" for p in unknown)
            )
        if not values:
            return dict(known)
    else:
        print("\n── Configure installed kit ────────────────────────────────────────")
        if remembered:
            print(
                f"{len(remembered)} value(s) recalled from a previous install — "
                "press Enter to keep them."
            )
        print("Press Enter to skip an item with no stored value.\n")

        values = {}
        for token in sorted(placeholder_files):
            desc = _PLACEHOLDER_DESCRIPTIONS.get(token, "")
            current = remembered.get(token)
            prompt = f"  [{token}]"
            if desc:
                prompt += f"  ({desc})"
            prompt += f" [{current}]: " if current else ": "
            try:
                answer = input(prompt).strip()
            except EOFError:
                answer = ""
            if answer:
                values[token] = answer
            elif current:
                values[token] = current

        if not values:
            print("\nNo values provided — placeholders left as-is.")
            return dict(known)

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

    return {**known, **values}


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
    # .gk/manifest.json is deliberately NOT ignored: a team sharing a checkout must
    # share the file hashes, or each programmer's upgrade would judge ownership from a
    # different baseline. Only the credential half and the stash are ignored, and
    # unconditionally — unlike .docs/, this is not subject to the track-kit-docs choice.
    entries.append(_SECRETS_FILE)
    entries.append(f"{_STATE_DIR}/overwritten/")
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
