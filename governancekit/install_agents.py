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
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .path_safety import UnsafePathError, safe_path, safe_regular_file

REPO = "EDortta/AI-Agents"
# Pinned to a tagged release (not the mutable "main" branch) so installs are
# reproducible and can be checksum-verified. Bump alongside KNOWN_TARBALL_SHA256
# when a new AI-Agents release is adopted.
DEFAULT_REF = "v1.2.1"

# codeload.github.com tarball SHA-256 for (repo, ref) pairs we can vouch for.
# Only the upstream default repo/ref is pinned here; a custom --repo/--ref
# (e.g. a fork, or "main" for early access) is downloaded without verification,
# same as before this table existed.
KNOWN_TARBALL_SHA256: dict[tuple[str, str], str] = {
    (REPO, "v1.0.2"): "8746c817426deedef9384b8feeb6f4a3cae739f8599f9c71c0fec02722fea5ed",
    (REPO, "v1.1.1"): "7255592a071dfe331adba5d739ec5b4ee9e10c0f37471301870e826719f8da60",
    (REPO, "v1.1.2"): "ff163a7bf11b74fe9f9b30c4794ad081f9b6f678ea436f0980687fefda6033ed",
    (REPO, "v1.1.3"): "0bcdf6968e3018664f685abd5079c2cb99a8bb439ef0b5d97ba47e9218931ebd",
    (REPO, "v1.1.4"): "497670c3ce1bbdbd2d434f845438a32d6d3afa3337933b8567367127884e9403",
    (REPO, "v1.1.5"): "68881466d94fead63d8f55d2c48e3ab82d4b4099a3741c2064b08e44a726f2fd",
    (REPO, "v1.1.6"): "0cac041c9e5c7ce0cc28b032fbb6cc400509b9a23dc9f04c24e21b6d7daf6c21",
    (REPO, "v1.1.7"): "7bff38d6ff94576fee6329fd84074d14ad9af649e8d98ff4230516a4283db97a",
    (REPO, "v1.2.0"): "d7581907321c4cb89dba994165e797c25465d380e2e29e9dd6668f69aef08339",
    (REPO, "v1.2.1"): "ccf9ed693a8a69abcb2548b24cddbd920c2edc6b41bcbd99c6af0f879519ac61",
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
    "docs/governancekit-integration.json",
    "docs/context-manifest.yaml",
    "docs/context-optimization.md",
    "docs/schemas",
    "docs/issues/templates",
    "docs/issues/README.md",
]

# Kit-provided templates that the PROJECT fills in (readiness flags, overview text).
# Seeded on a fresh install (with flags reset) but NEVER overwritten on --upgrade,
# so the project's answers survive.
_KIT_SEED_PATHS: list[str] = []

# Project-owned starter files: seeded once into docs/ (the project's territory) and
# never overwritten. They stay in docs/, not .docs/.
#
# software-overview.md and limits.md belong here, not in _KIT_SEED_PATHS: the kit
# ships a template, but the project writes the content and owns the readiness flags,
# and the Start Gate reads exactly the file the project maintains. Keeping them under
# the kit's .docs/ (2026-07-01 to 2026-08-04) split the two apart.
_PROJECT_SEED_PATHS: list[str] = [
    "docs/software-overview.md",
    "docs/limits.md",
    "docs/required-reading.md",
    "docs/project-rules.md",
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
    ".amazonq/rules/ai-agents.md",
    ".credentials",
    *_KIT_DOC_PATHS,
    *_KIT_SEED_PATHS,
    *_PROJECT_SEED_PATHS,
    "handoff.md",
    "new-tag.sh",
    "scripts/agent-worktree.sh",
]
# `templates` is deliberately NOT installed, and the reason is worth keeping.
#
# It was added on 2026-08-10 so the shell installer shipped into the target could find
# templates/required-reading.template.md instead of bailing silently. The council of
# that delivery reproduced what it actually cost: `templates` is the commonest
# top-level directory name in web projects, every kit path here is unprefixed, and the
# consequences compound — `_update_gitignore` writes it as a BARE pattern, so git
# ignores `templates/` at ANY depth; `_do_fresh --force` rmtree's the project's own
# tree with no backup; and `_write_state` rglobs the destination into the TRACKED
# manifest, so the SECOND upgrade deletes the project's files as kit-owned leftovers —
# silently — and `remove-agents` then plans to delete them at confidence 1.0.
#
# The self-upgrade path it was meant to repair is degraded, not blocked, and the first
# cut of this comment overstated it. The shipped shell installer reads
# `.credentials/identity.json` while this installer writes identity to the local
# state half (`.gk/manifest.override.json` since AC-29; `.gk/operator.json` before
# it), so the two do not share the operator's answers: with stdin closed
# the shell run exits 8, but on a TTY — how an operator actually self-upgrades — it
# prompts and completes. So the entry did buy something; it just did not buy enough to
# be worth claiming the project's own directory. The silent bail is fixed where it belongs: the shell
# installer now names the index it failed to create instead of leaving on a bare
# `return 0` under a line that claimed the file had been preserved.
#
# Reinstating this needs a namespaced destination (`.docs/templates/`), not the root.

# Paths replaced during --upgrade (dirs wholesale, files individually). Excludes the
# seed paths so project-filled overview/limits/required-reading/napkin survive.
_UPGRADE_PATHS: list[str] = [
    "AGENTS.md",
    ".cursorrules",
    "CLAUDE.md",
    ".windsurfrules",
    "GEMINI.md",
    ".github/copilot-instructions.md",
    ".amazonq/rules/ai-agents.md",
    "new-tag.sh",
    "scripts/agent-worktree.sh",
    *_KIT_DOC_PATHS,
]

# Alias kept for --docs-only callers and tests.
_DOCS_PATHS = _KIT_DOC_PATHS

# A protected file is kit-owned for READING and project-owned for WRITING: once its
# content differs from what the kit installed, `--upgrade` stops claiming it. The new
# version lands beside it as `<file>.kit-new` and a human merges.
#
# `--upgrade`, and only `--upgrade`. `--force` is the fresh path and is documented as
# "overwrite existing kit files": it still removes and replaces this file with no
# stash, no backup and no report. The shell installer's `copy_path` does the same
# `rm -rf` under `--force`, so the two agree, and correcting one side alone would
# recreate exactly the divergence this pair of lists exists to prevent. Recorded as an
# accepted risk in the epic's RESUME rather than half-fixed here.
#
# This mirrors `PROTECTED_ROOT_FILES` in the shell installer, and the two lists must
# stay identical — `tests/test_kit_drift.py` asserts that against the pinned release
# rather than trusting this comment. The shell has had this since 2026-07-23, when a
# real target was found holding ~300 lines of project rules in AGENTS.md, including
# reviewer logins; this installer replaced the same file with a bare `shutil.copy2`
# for another twenty days. AGENTS.md is the first file every agent is told to read,
# so it is the first place anyone writes a project rule.
_PROTECTED_FILES: tuple[str, ...] = ("AGENTS.md",)

# The project's own directory, seeded but never claimed. It holds the programmer's
# identity file, their GitHub/Jira tokens and the LLM keys `scope_conversation` writes
# to `.credentials/llm/<provider>.key`. The kit adds what is missing and touches
# nothing else — the shell installer's `seed_dir_missing`, ported.
_CREDENTIALS_DIR = ".credentials"
_SEED_ONLY_PATHS: frozenset[str] = frozenset({_CREDENTIALS_DIR})

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

_PROJECT_REQUIRED_READING = """# Required Reading

List the project documents an agent must read before analysing or implementing an
issue. Keep this index honest: add the project contracts, runbooks, and domain
rules an agent must load before work.

- `docs/project-rules.md` — project-specific rules and operational contracts
"""

_PROJECT_RULES = """# Project Rules

Record the project-specific contracts, runbooks, and operational constraints that
do not belong in the reusable AI-Agents kit. Keep `docs/required-reading.md`
aligned with every document an agent must load before work.
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
    "governancekit-integration.json",
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
# Split by who may read it. Two halves, one rule (operator decision, 2026-08-13,
# PLANO-UNIFICADO of epic 014): the manifest says what the kit IS in this project;
# the override says what THIS MACHINE knows.
#
# manifest.json is COMMITTED: file hashes of impersonal kit files are not secret, and
# a team sharing a checkout must share them — that is what makes every programmer's
# upgrade decide ownership the same way. Only project-wide answers (org, repo owner)
# belong here. Nothing derived from personal data does — not the values, and not the
# hash of a file rendered with them (AC-22: the template is public and the candidate
# set is the team, so a hash of the rendered result is a confirmation oracle).
#
# manifest.override.json is GITIGNORED, per-machine, mode 0600: per-programmer
# identity answers (operator name, local absolute paths), anything sensitive, and the
# hashes of files whose rendered content carries such a value. It merges over the
# manifest on read and never reaches it on write. If a team genuinely needs to share
# these values, encrypt a copy to the RECIPIENTS' public keys (sops/age) — never
# "encrypt with the origin machine's private key", which only signs.
#
# operator.json and secrets.json are the LEGACY local halves (same gitignored rules).
# They are still read, and the next write migrates their content into the override
# and deletes them — reading them forever while writing elsewhere would leave two
# sources of truth, which is the defect class AC-30 just retired an installer over.
_STATE_FILE = f"{_STATE_DIR}/manifest.json"
_OVERRIDE_FILE = f"{_STATE_DIR}/manifest.override.json"
_OPERATOR_FILE = f"{_STATE_DIR}/operator.json"
_SECRETS_FILE = f"{_STATE_DIR}/secrets.json"
_STATE_VERSION = 1

# Answers that must never be committed because they are operator/machine-local.
_OPERATOR_PLACEHOLDERS: frozenset[str] = frozenset({
    "OPERATOR_NAME",
    # SMTP_ACCOUNT is no longer a fillable slot — it left _PLACEHOLDER_DESCRIPTIONS on
    # 2026-08-10 when the canonical contract stopped naming an email transport
    # (AI-Agents#5), so nothing collects it any more. It stays HERE on purpose: an
    # install made before that date has the operator's address in .gk/operator.json,
    # and this frozenset is what keeps a known key out of the COMMITTED manifest.
    # Dropping it would route a legacy value into a tracked file on the next upgrade.
    "SMTP_ACCOUNT",
    "SMTP_DOMAIN",
    "PROJECT_ROOT",
})

# Answers that must never be committed because they are sensitive. Everything else
# is shareable project context.
# Empty by decision, 2026-08-13: every name that lived here was a donation slot, and
# the operator's ruling was "não pode haver referência alguma". They were residue from
# `a228889` — the public release scrubbed the author's OWN donation page into tokens and
# the tokens became declared slots. Measured before removing: no shipped file carried
# any of them, and `.gk/secrets.json` existed in no governed project. Kept as an empty
# set rather than deleted so `_write_state`'s three-way split still reads as three ways.
_SENSITIVE_PLACEHOLDERS: frozenset[str] = frozenset()

# Withdrawn, and DISCARDED on sight — not merely unclassified.
#
# The first cut of the removal emptied `_SENSITIVE_PLACEHOLDERS` and stopped there. That
# did not delete anything: `shareable` is "everything not in the two sets", so the six
# names fell through to the SHARED half and `_write_state` wrote a stored PIX payload and
# a person's full name into `.gk/manifest.json` — the file `.gk/.gitignore` marks
# "intentionally NOT ignored — the team must share it" — while deleting the gitignored
# `secrets.json` in the same pass. The operator asked for "não pode haver referência
# alguma" and the implementation produced publication.
#
# Erasing a value's CLASSIFICATION does not erase the value; it decides where it goes.
# So the names stay, in the one list whose meaning is "drop this, wherever it came from",
# and the eliminação `AC-21` owes the operator happens here for these six by construction.
_DISCARDED_PLACEHOLDERS: frozenset[str] = frozenset({
    "PIX_KEY_UUID",
    "PIX_HOLDER_NAME",
    "PIX_PAYLOAD",
    "PIX_QR_BASE64",
    "KOFI_HANDLE",
    "ETH_WALLET_ADDRESS",
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
    # Protected files (see _PROTECTED_FILES) whose content no longer matches what the
    # kit installed. The project's version stayed; the kit's waits as <file>.kit-new
    # and is NOT recorded in the manifest until a human merges it.
    drifted_paths: list[str] = field(default_factory=list)
    # Files added into a directory the project owns (`.credentials/`), and the ones
    # already there that this run left alone. Reported: an operator who is told
    # "installed 26 paths" and nothing else cannot know their tokens survived.
    seeded_paths: list[str] = field(default_factory=list)
    # Files replaced this run whose previous content was copied to .gk/pre-upgrade/.
    # Reported: insurance nobody knows about is insurance nobody uses, and the
    # directory is cleared at the start of the next upgrade.
    backed_up: list[str] = field(default_factory=list)
    # Stored answers substituted into the download before anything was compared.
    substitutions_prerendered: int = 0
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


# Seeded from an EMPTY TEMPLATE, never from the kit's own copy. Copying the source
# tree's file hands every project this repository's content as if it were the project's
# own — the same mistake the kit already fixed for README.md.
#
# required-reading.md joined this list on 2026-08-10, and it is the sharpest case yet.
# `.docs/workflows/sending-email.md` requires each project to declare its own email
# transport and recipient list in that index, and the kit's own index declares the kit's
# — so seeding from it made every new project assert one operator's helper as its
# transport, in the exact table the contract tells the agent to trust. The rule that
# forbids carrying a transport across projects was being violated by the installer that
# ships the rule. Found by council round 1 of AI-Agents#5.
_TEMPLATE_SEEDS: dict[str, str] = {
    "handoff.md": "templates/handoff.template.md",
    "docs/napkin-lessons.md": "templates/napkin-lessons.template.md",
    "docs/required-reading.md": "templates/required-reading.template.md",
}


def _resolve_src(src_root: Path, rel: str) -> Path:
    """Resolve where a kit path actually lives in the downloaded source tree.

    Paths are canonical (``docs/…``). A restructured source repo stores kit-owned
    docs under ``.docs/…`` while project-owned seeds (``required-reading.md``,
    ``napkin-lessons.md``) stay in ``docs/…``. This prefers the ``.docs/`` location
    when present and falls back to ``docs/`` — so the installer reads correctly from
    both a restructured source and a legacy one.

    Template-seeded files (``_TEMPLATE_SEEDS``) resolve to their empty template instead
    of the source's own file, so a target is never seeded with the kit's history — nor,
    for the reading index, with the kit's own local sources and email transport.
    """
    template = _TEMPLATE_SEEDS.get(rel)
    if template is not None:
        candidate = src_root / template
        if candidate.is_file():
            return candidate
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
    migrate_content: bool = False,
    track: bool | None = None,
    install_awt: bool = False,
    allow_unverified: bool = False,
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

    if upgrade and _content_migration_required(root) and not migrate_content:
        raise RuntimeError(
            "Refusing upgrade: legacy agent contracts remain in .docs-migration-bak/. "
            "Run 'governancekit install-agents --upgrade --migrate-content' first."
        )

    # Migrate a legacy layout (kit in docs/, project in docs/project/) BEFORE any
    # upgrade write, so kit content lands in .docs/ and project docs are preserved.
    if upgrade or docs_only:
        migrated, notes = _migrate_legacy_layout(root)
        result.migrated = migrated
        result.migration_notes = notes
        readiness_moved, readiness_notes = _migrate_readiness_files_to_docs(root)
        result.migrated = result.migrated or readiness_moved
        result.migration_notes.extend(readiness_notes)
        if migrate_content:
            content_migrated, content_notes = _migrate_legacy_content(root)
            result.migrated = result.migrated or content_migrated
            result.migration_notes.extend(content_notes)

    with tempfile.TemporaryDirectory() as tmp:
        src_root = _download(repo, ref, Path(tmp), allow_unverified=allow_unverified)
        # Render the incoming source with what this project already answered, BEFORE
        # anything is compared or copied. Without this the comparison is rigged: the
        # target holds `Esteban` where the download still holds `{{OPERATOR_NAME}}`,
        # so a file the kit itself rendered can never read as identical to the kit.
        # One run, one warning per token: what the source pass says about a
        # composing slot must not be repeated verbatim by the target pass.
        composing_reported: set[tuple[str, str]] = set()
        result.substitutions_prerendered = _prerender_source(
            src_root, _state_metadata(state), reported=composing_reported
        )

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
                drifted=result.drifted_paths,
                backed_up=result.backed_up,
                clear_backups=not docs_only,
            )
        else:
            result.paths_installed = _do_fresh(
                src_root, root, force=force,
                seeded=result.seeded_paths, preserved=result.preserved_paths,
            )

        # Idempotent: seeds docs/ on fresh install and lets existing installs adopt
        # it on --upgrade / --docs-only without overwriting it.
        _ensure_project_docs(root)

        if docs_only:
            # This mode promises a documentation refresh. Do not prompt for tracking
            # or rewrite the project's root .gitignore as a side effect.
            result.track_kit_docs = bool(_read_kit_config(root).get("track_kit_docs", False))
        else:
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

    withdrawn = _remove_withdrawn(root)
    if withdrawn:
        print(
            "\nRemoved file(s) this kit no longer ships: " + ", ".join(withdrawn)
            + "\n  They were installed by an older kit and are not documentation this "
            "project needs."
        )
        result.migration_notes.extend(f"removed withdrawn {rel}" for rel in withdrawn)

    metadata = _fill_placeholders(
        root, result.paths_installed, known=_state_metadata(state),
        already_reported=composing_reported,
    )
    result.metadata_known = sorted(metadata)
    # Written last: hashes must describe the files as they stand AFTER substitution,
    # so a configured file still matches its own record on the next upgrade.
    _write_state(
        root,
        result.paths_installed,
        repo=repo,
        ref=ref,
        metadata=metadata,
        prune_missing=upgrade and not docs_only,
        preserved=result.preserved_paths,
        seeded=result.seeded_paths,
    )

    if install_awt and _dest_rel("scripts/agent-worktree.sh") in result.paths_installed:
        result.awt_installed, result.awt_message = _install_awt(root)
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

def _download(repo: str, ref: str, tmp: Path, *, allow_unverified: bool = False) -> Path:
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
    elif allow_unverified:
        print(
            f"Warning: no known checksum for {repo}@{ref} — installing unverified "
            "because --allow-unverified was given.",
            file=sys.stderr,
        )
    else:
        # A warning printed into a verbose install is not a decision anyone made. The
        # kit governs supply chains; it does not get to be looser than what it asks for.
        raise RuntimeError(
            f"No known checksum for {repo}@{ref}. Install from a pinned release, or "
            "pass --allow-unverified to accept an unverified tarball deliberately."
        )

    with tarfile.open(archive, "r:gz") as tf:
        _safe_extractall(tf, tmp)

    extracted = sorted(p for p in tmp.iterdir() if p.is_dir() and p.name != archive.name)
    if not extracted:
        raise RuntimeError("Unexpected archive structure — no top-level directory found.")
    if len(extracted) > 1:
        # iterdir() order is filesystem-dependent, so picking one would be an arbitrary
        # choice made silently about which tree gets installed.
        names = ", ".join(p.name for p in extracted)
        raise RuntimeError(f"Unexpected archive structure — several top-level directories: {names}")
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


def _seed_dir_missing(src_dir: Path, dst_dir: Path, root: Path) -> tuple[list[str], list[str]]:
    """Copy only what is absent, file by file. Never replaces, never deletes.

    Mirrors `seed_dir_missing` in the shell installer, whose comment is the whole
    specification: `.credentials/` holds the programmer's real tokens and their
    identity file, so the directory belongs to the project even though the kit seeds
    scaffolding into it.

    This runtime did the opposite until today: `.credentials` was an ordinary conflict,
    so answering `y` — or passing `--force`, which never asks — ran `shutil.rmtree` over
    the operator's tokens and LLM keys and copied the kit's scaffolding in their place.
    """
    if dst_dir.exists() and not dst_dir.is_dir():
        # The project has a FILE (or a broken link) where the kit ships a directory.
        # Nothing here may replace it — this whole function exists because that path
        # belongs to the project — and crashing the install over it helps nobody. The
        # old code reached `unlink()`; the seed-only branch jumps over that, so without
        # this the first `mkdir` raised FileExistsError and killed the run.
        return [], [dst_dir.relative_to(root).as_posix()]
    seeded: list[str] = []
    preserved: list[str] = []
    for src_file in sorted(p for p in src_dir.rglob("*") if p.is_file()):
        rel = src_file.relative_to(src_dir)
        target = safe_path(root, dst_dir / rel)
        if target.exists():
            preserved.append(target.relative_to(root).as_posix())
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, target)
        seeded.append(target.relative_to(root).as_posix())
    for existing in sorted(p for p in dst_dir.rglob("*") if p.is_file()):
        rel_to_root = existing.relative_to(root).as_posix()
        if rel_to_root not in seeded and rel_to_root not in preserved:
            preserved.append(rel_to_root)
    return seeded, sorted(preserved)


def _do_fresh(
    src: Path,
    dst: Path,
    *,
    force: bool,
    seeded: list[str] | None = None,
    preserved: list[str] | None = None,
) -> list[str]:
    available = [rel for rel in _FRESH_PATHS if _resolve_src(src, rel).exists()]
    # Conflicts are checked against the DESTINATION path (docs/ → .docs/).
    #
    # Two families are never conflicts, because they are never the kit's to replace:
    # `.credentials/` (tokens, identity, LLM keys) and the two readiness documents the
    # project writes. `--force` is documented as "overwrite existing KIT files"; these
    # are the project's. The shell installer has guarded both since it grew the
    # protection, and this is that convergence.
    protected = {rel for rel in available if rel in _SEED_ONLY_PATHS or rel in _PROJECT_SEED_PATHS}
    conflicts = [
        rel for rel in available
        if rel not in protected and (dst / _dest_rel(rel)).exists()
    ]

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
    # Readiness documents that were already on disk when this run started. The reset
    # below lowers only what this run seeded, and "already there" is the honest test —
    # deriving it from what the SOURCE ships would demote a confirmed document whenever
    # a release happened not to carry that file.
    kept_readiness = {
        _dest_rel(rel) for rel in _PROJECT_SEED_PATHS
        if (dst / _dest_rel(rel)).exists()
    }
    for rel in available:
        if rel in skip:
            continue
        src_path = _resolve_src(src, rel)
        dst_path = safe_path(dst, dst / _dest_rel(rel))
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if rel in _SEED_ONLY_PATHS and src_path.is_dir():
            was_seeded, was_kept = _seed_dir_missing(src_path, dst_path, dst)
            if seeded is not None:
                seeded.extend(was_seeded)
            if preserved is not None:
                preserved.extend(was_kept)
            # Deliberately NOT appended to `installed`: that list becomes the manifest,
            # and the manifest is tracked. See `_write_state`.
            continue
        if rel in _PROJECT_SEED_PATHS and dst_path.exists():
            if preserved is not None:
                preserved.append(_dest_rel(rel))
            continue
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

    # Only what this run just SEEDED. A readiness document the project already had was
    # preserved three lines above; lowering its flag would demote an answer the operator
    # gave — in the same run whose report says "kept" — and shut the Start Gate over
    # content nobody changed. Found by the council's migrator lens.
    _reset_readiness_flags(dst, skip=kept_readiness)
    return installed


def _reset_readiness_flags(root: Path, *, skip: set[str] | None = None) -> None:
    """Lower both readiness flags on a fresh install, as a metadata LINE.

    Anchored, like every other reader and writer of these flags. A plain `replace`
    matches mid-line, and the seeded documents explain the flag in a sentence — the
    same prose that made the adoption gate skip its write for eight days.
    """
    for rel, marker in (
        ("docs/software-overview.md", "project_context_ready"),
        ("docs/limits.md", "limits_ready"),
    ):
        if skip and rel in skip:
            continue
        path = safe_path(root, root / rel)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lowered = re.sub(
            rf"^(-?[ \t]*{re.escape(marker)}[ \t]*:[ \t]*)yes[ \t]*$",
            lambda m: f"{m.group(1)}no",
            text,
            flags=re.MULTILINE,
        )
        if lowered != text:
            path.write_text(lowered, encoding="utf-8")


# ── upgrade ────────────────────────────────────────────────────────────────────

def _do_upgrade(
    src: Path,
    dst: Path,
    *,
    paths: list[str] | None = None,
    manifest: dict[str, str] | None = None,
    preserved: list[str] | None = None,
    overwritten: list[str] | None = None,
    drifted: list[str] | None = None,
    backed_up: list[str] | None = None,
    clear_backups: bool = True,
) -> list[str]:
    installed: list[str] = []
    known = manifest if manifest is not None else {}
    # The backup holds the state before THIS upgrade. Accumulating runs would make the
    # name mean nothing in particular: after two upgrades `.gk/pre-upgrade/GEMINI.md`
    # would be the file as it stood before the FIRST one, and the operator restoring it
    # would silently roll back a version they never asked to lose. The shell clears it
    # per run for this reason; the port did not, and a council lens reproduced the
    # divergence — in a fleet where both installers run, the directory's meaning
    # depended on which one had run last.
    #
    # `--docs-only` passes False, and the second round is why: clearing there deleted
    # the backups a full upgrade had just made of the root contracts, which that mode
    # never touches. A narrower run must not destroy the wider run's insurance.
    if clear_backups:
        stale_backups = safe_path(dst, dst / _STATE_DIR / "pre-upgrade")
        if stale_backups.is_dir():
            shutil.rmtree(stale_backups)
    for rel in (paths if paths is not None else _UPGRADE_PATHS):
        src_path = _resolve_src(src, rel)
        dst_path = safe_path(dst, dst / _dest_rel(rel))
        if not src_path.exists():
            continue
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if src_path.is_dir():
            _sync_dir(src_path, dst_path, dst, known, preserved, overwritten)
        elif not _replace_kit_file(
            src_path, dst_path, dst, known,
            overwritten=overwritten, drifted=drifted, backed_up=backed_up,
        ):
            # The project's version stayed. Leaving the path out of `installed` keeps
            # it out of _write_state as well, so the manifest holds no hash for a file
            # the kit did not write — recording it would tell the NEXT upgrade
            # "untouched kit content, safe to replace", which is the loss this exists
            # to prevent.
            continue
        installed.append(_dest_rel(rel))
    return installed


def persist_placeholder_values(root: Path, values: dict[str, str]) -> None:
    """Record answers given outside an install, so the next upgrade still knows them.

    ``configure`` used to fill the files and remember nothing. Everything downstream
    reads the stored answers: ``_fill_placeholders`` re-applies them after a template
    is overwritten, and ``_prerender_source`` renders the incoming source with them
    before any comparison. Without the record, a target configured this way looked
    hand-edited on the next upgrade — the file differed from the kit by exactly the
    substitution the operator had just been told to perform — and, for the protected
    file, that verdict is permanent: it is kept, so it never converges back.

    The split between shared, operator-local and secret values is `_write_state`'s;
    this only routes the answers into it without touching any file hash.
    """
    if not values:
        return
    state = _read_state(root)
    _write_state(
        root,
        [],
        repo=str(state.get("repo") or REPO),
        ref=str(state.get("ref") or DEFAULT_REF),
        metadata=values,
    )


def _prerender_source(
    src_root: Path,
    known: dict[str, str],
    *,
    reported: set[tuple[str, str]] | None = None,
) -> int:
    """Substitute stored answers into the downloaded source; return substitutions made.

    This runs BEFORE the first comparison, and the ordering is the whole point. Every
    judgement downstream — the byte-identity short-circuit, the manifest hash, what
    lands in ``<file>.kit-new`` — compares a target the kit has already rendered
    against this source. Leave the source raw and a configured `AGENTS.md` differs
    from the kit by exactly the substitution the kit performed, which reads as
    operator intent. The consequences were reproduced by three separate council
    lenses: a target whose manifest entry was lost (a pre-`.gk` install, or a shell
    install where `write_manifest` bailed for want of `python3`) became permanently
    drifted and never received another `AGENTS.md`; `configure` — which rewrites the
    file and does not update the manifest — froze it the same way; and the `.kit-new`
    an operator was told to merge carried raw `{{OPERATOR_NAME}}`, so following the
    instruction turned `doctor` red.

    The shell installer has done this since it grew the protection, and says why in a
    comment (`apply_identity`): "A filled slot then reads as 'identical to the kit',
    not as drift." Porting its decision table without its ordering ported half a
    mechanism.

    Binary files (the shipped icons) and symlinks are never rewritten — an undecodable
    file is skipped, exactly as the shell's pass does.

    What may be substituted is decided by ``_render_table`` and applied by
    ``_render_text``, which every writer in the pipeline shares — see their docstrings
    for the four rules and for why the fourth one is the only one that closes the
    two-stage chain. This function used to carry its own copy of two of those rules,
    which is how the chain stayed open: each stage was correct alone.
    """
    tokens, refused = _render_table(known)
    if not tokens and not refused:
        return 0

    # One read of the tree. Each file decides for itself which of its own tokens
    # compose; nothing a defective file does reaches its neighbours.
    needed: set[str] = set()
    dropped: dict[str, set[str]] = {}
    substitutions = 0
    for path, text in _text_files(src_root):
        needed.update(_PLACEHOLDER_RE.findall(text))
        rendered, made, blocked = _render_file_text(text, tokens)
        if blocked:
            dropped[str(path.relative_to(src_root))] = blocked
        if rendered != text:
            path.write_text(rendered, encoding="utf-8")
        substitutions += made

    reported_here = _report_composing_tokens(dropped, prefix="the kit's own ")
    if reported is not None:
        reported.update(reported_here)
    # Reported after the sweep, so only the tokens some file actually carries are
    # named: a warning about a slot no shipped file uses is noise that costs the
    # reader's attention on the run where it is not noise.
    _report_refused_values(refused, needed=needed)
    return substitutions


def _replace_kit_file(
    src_file: Path,
    target: Path,
    root: Path,
    known: dict[str, str],
    *,
    overwritten: list[str] | None = None,
    drifted: list[str] | None = None,
    backed_up: list[str] | None = None,
) -> bool:
    """Replace a single kit-owned file, judging it against the manifest first.

    Returns whether the kit's version now stands at *target*.

    ==========================  ==========================================================
    manifest says               what happens
    ==========================  ==========================================================
    content already identical   nothing to preserve and nothing to report; a stale
                                ``.kit-new`` from an earlier run is cleared
    hash matches                untouched kit content; replaced silently
    hash differs, protected     kept; the new version lands as ``<file>.kit-new``
    hash differs, other         stashed under ``.gk/overwritten/``, then replaced
    no entry, protected         fail closed — kept, ``.kit-new`` written
    no entry, other             replaced (the behaviour that predates the manifest)
    ==========================  ==========================================================

    Failing closed on "no entry" is the case that matters: the installs most likely to
    hold hand-written rules are precisely the ones predating the manifest.

    Byte-identical content short-circuits everything *before* the manifest is
    consulted. That is not an optimisation — after a layout migration the file IS the
    rendered kit version while the manifest still holds the pre-migration hash, and
    judging by the manifest alone would demand a merge of a file against itself.
    """
    if target.is_file():
        rel_to_root = target.relative_to(root).as_posix()
        kit_new = safe_path(root, target.parent / (target.name + ".kit-new"))
        if _file_sha256(target) == _file_sha256(src_file):
            kit_new.unlink(missing_ok=True)
            return True

        recorded = known.get(rel_to_root)
        if recorded is None or recorded != _file_sha256(target):
            if rel_to_root in _PROTECTED_FILES:
                shutil.copy2(src_file, kit_new)
                if drifted is not None:
                    drifted.append(rel_to_root)
                return False
            if recorded is not None:
                stash = safe_path(root, root / _STATE_DIR / "overwritten" / rel_to_root)
                stash.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, stash)
                if overwritten is not None:
                    overwritten.append(rel_to_root)

        # Cheap insurance, independent of the judgement above: even a file the manifest
        # calls untouched keeps a copy, so a wrong call costs one `cp` to undo. Under
        # .gk/ rather than beside the file, so an upgrade does not litter the project
        # root with a dozen .bak files.
        backup = safe_path(root, root / _STATE_DIR / "pre-upgrade" / rel_to_root)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup)
        if backed_up is not None:
            backed_up.append(rel_to_root)
        kit_new.unlink(missing_ok=True)

    shutil.copy2(src_file, target)
    return True


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
    dst_dir = safe_path(root, dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    for existing in dst_dir.rglob("*"):
        if existing.is_symlink():
            raise UnsafePathError(f"refusing symlink in managed kit directory: {existing}")

    shipped: set[Path] = set()
    for src_file in sorted(p for p in src_dir.rglob("*") if p.is_file()):
        rel = src_file.relative_to(src_dir)
        target = safe_path(root, dst_dir / rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        # A kit file the project edited by hand is still kit-owned, so the new version
        # wins — but the edit is real intent and must not vanish silently. Stash it and
        # report it. Only detectable because the state records the hash as written.
        if target.is_file() and overwritten is not None:
            rel_to_root = target.relative_to(root).as_posix()
            recorded = known.get(rel_to_root)
            # Byte-identical to what is about to be written: nothing to preserve and
            # nothing to accuse anyone of, whatever the manifest remembers. The same
            # short-circuit `_replace_kit_file` has, missing here — so after
            # `configure` filled a slot inside a kit directory, the next upgrade told
            # the operator it had replaced a file "you had edited by hand" and stashed
            # a copy identical to the original, with a line about moving project rules
            # out of kit files. The edit was the kit's own.
            if recorded is not None and _file_sha256(target) == _file_sha256(src_file):
                recorded = None
            if recorded is not None and recorded != _file_sha256(target):
                backup = safe_path(root, root / _STATE_DIR / "overwritten" / rel_to_root)
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
    state = _read_json(safe_path(root, root / _STATE_FILE))
    operator = _read_json(safe_path(root, root / _OPERATOR_FILE))
    secrets = _read_json(safe_path(root, root / _SECRETS_FILE))
    override = _read_json(safe_path(root, root / _OVERRIDE_FILE))
    # Legacy manifests may still carry operator-local fields from before
    # operator.json existed. Ignore them here so a clone never inherits another
    # programmer's identity; the next write strips them from the manifest.
    manifest_meta = {
        k: v for k, v in _state_metadata(state).items() if k not in _OPERATOR_PLACEHOLDERS
    }
    if not operator and not secrets and not override:
        if manifest_meta != _state_metadata(state):
            merged = dict(state)
            merged["metadata"] = manifest_meta
            return merged
        return state
    # Present the split files to callers as one logical state; only _write_state
    # knows they are stored apart. The override wins: it is what this machine
    # answered, while the legacy pair and the manifest are what it inherited.
    merged = dict(state)
    merged["metadata"] = {
        **manifest_meta,
        **_state_metadata(operator),
        **_state_metadata(secrets),
        **_state_metadata(override),
    }
    override_files = _state_files(override)
    if override_files:
        # File hashes routed local by `_write_state` (a rendered file carrying a
        # local value). Merged here so ownership judgement on THIS machine still
        # sees them; a clone without the override simply preserves those files,
        # which is the safe direction an absent state already means.
        merged["files"] = {**_state_files(state), **override_files}
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
    prune_missing: bool = False,
    preserved: list[str] | None = None,
    seeded: list[str] | None = None,
) -> None:
    """Persist file hashes and operator answers.

    Call this AFTER placeholder substitution: the recorded hash must describe the file
    as it actually sits on disk, otherwise a configured file never matches its own
    record and looks hand-edited forever.

    Merges over the previous state rather than replacing it — ``--docs-only`` touches a
    narrow scope, and dropping what it did not touch would make the next full upgrade
    forget that e.g. ``AGENTS.md`` is kit-owned, or forget an answer already given.

    *preserved* names the files the upgrade refused to claim — project-authored files
    found inside kit-owned directories. They must not be recorded, and the reason is
    the second cycle, not this one. This function walks an installed DIRECTORY with
    ``rglob``, so a project's own file inside ``.docs/agents/`` was written into the
    manifest as kit-owned; on the NEXT upgrade ``_sync_dir`` read "the kit wrote this,
    the hash still matches, the kit no longer ships it" and deleted it — silently, with
    an empty preserved list — and in between ``remove-agents`` planned the same
    deletion at confidence 1.0 with ``requires_operator_review: false``. Upgrade one
    reports it kept the file; upgrade two destroys it. Reproduced by the council's
    sweep lens. The shell installer skips ``DRIFTED`` here and has the same hole for
    ``PRESERVED``.
    """
    previous = _read_state(root)
    files: dict[str, str] = dict(_state_files(previous))
    if prune_missing:
        # A full upgrade is authoritative for the kit layout. Retired files and
        # pre-.docs paths must not survive forever as fake managed files. Narrow
        # documentation refreshes deliberately do not prune outside their scope.
        files = {rel: digest for rel, digest in files.items() if (root / rel).is_file()}
    # `.gk/manifest.json` is TRACKED on purpose — a team must judge file ownership from
    # the same baseline. So nothing under `.credentials/` may appear in it: a SHA-256 of
    # a low-entropy token is a confirmation oracle, and the paths alone say which
    # providers a programmer holds keys for. Until today the directory was rmtree'd
    # before this ran, so only kit scaffolding was ever hashed; making the seeding
    # non-destructive would otherwise have started committing the real thing. The
    # filter runs over the MERGED dict, so a project that already carries those entries
    # loses them on its next run of any mode.
    files = {
        rel: digest for rel, digest in files.items()
        if not rel.startswith(f"{_CREDENTIALS_DIR}/") and rel != _CREDENTIALS_DIR
    }

    unclaimed = set(preserved or ())
    # The rels whose digest THIS run computed from the file on disk. The routing
    # below may only reclassify a previously-local entry on the strength of a
    # digest that provably describes content it just read — a merged entry from a
    # previous state describes bytes nobody looked at in this run.
    rehashed: set[str] = set()
    for rel in installed:
        target = safe_path(root, root / rel)
        if target.is_file():
            if rel not in unclaimed:
                files[rel] = _file_sha256(target)
                rehashed.add(rel)
        elif target.is_dir():
            for f in sorted(p for p in target.rglob("*") if p.is_file()):
                rel_to_root = f.relative_to(root).as_posix()
                if rel_to_root in unclaimed:
                    # Recording it would answer "who wrote this?" with the wrong name,
                    # and the only consumer of that answer deletes files.
                    files.pop(rel_to_root, None)
                    continue
                files[rel_to_root] = _file_sha256(f)
                rehashed.add(rel_to_root)

    merged_meta = {**_state_metadata(previous), **metadata}
    # Dropped BEFORE the split, so no branch below can receive them. Putting the filter
    # after the split is what published them: `shareable` is a negative set, so a name
    # removed from every positive list lands in the shared half by default.
    discarded = sorted(k for k in merged_meta if k in _DISCARDED_PLACEHOLDERS)
    if discarded:
        print(
            "\nWithdrawn value(s) dropped from this project's state, not carried "
            "forward: " + ", ".join(discarded)
        )
    merged_meta = {k: v for k, v in merged_meta.items() if k not in _DISCARDED_PLACEHOLDERS}
    shareable = {
        k: v for k, v in merged_meta.items()
        if k not in _OPERATOR_PLACEHOLDERS and k not in _SENSITIVE_PLACEHOLDERS
    }
    local_meta = {
        k: v for k, v in merged_meta.items()
        if k in _OPERATOR_PLACEHOLDERS or k in _SENSITIVE_PLACEHOLDERS
    }

    # AC-22, resolved by the manifest/override split rather than by a smarter hash:
    # a file whose RENDERED content carries a local value must not have its digest in
    # the committed half. The template is public and ships at the ref the manifest
    # itself records, so for such a file the digest's only unknown is the personal
    # value — hashing it publishes a confirmation oracle whose candidate set is the
    # team. Two rules, in order of authority:
    #
    # 1. **Provenance is sticky.** An entry already in the override describes content
    #    that carried a local value WHEN IT WAS HASHED. The first cut tested the file
    #    as it sits on disk today, and a council lens measured what that publishes:
    #    delete the file and the personalized digest fell through to the tracked
    #    manifest; rewrite it clean and the OLD digest — still derived from the
    #    personal value — fell through the same way. A previously-local entry may
    #    move to the shared half only on fresh evidence: this run re-hashed the file
    #    (`rehashed`), there are stored values to test against, and the content
    #    provably carries none of them. No evidence, no reclassification.
    # 2. **New placement is by content.** For everything else the digest just
    #    computed describes the bytes just read, so the scan decides. Over-routing
    #    is the safe direction — an entry missing from the shared half reads as
    #    "preserve, ask" — and unreadable is unknowable: never publish on a guess.
    #
    # `files` starts from the MERGED previous state, so entries a legacy tracked
    # manifest already carries migrate out of it on this write.
    local_values = [v for v in local_meta.values() if isinstance(v, str) and v]
    previously_local = set(
        _state_files(_read_json(safe_path(root, root / _OVERRIDE_FILE)))
    )

    def _content_carries_local_value(rel: str) -> bool | None:
        """True/False from the file's current bytes; None when there is no evidence
        (missing file, unreadable file, or no stored values to test against)."""
        if not local_values:
            return None
        target = safe_path(root, root / rel)
        if not target.is_file():
            return None
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        return any(value in text for value in local_values)

    def _routes_local(rel: str) -> bool:
        verdict = _content_carries_local_value(rel)
        if rel in previously_local:
            # Sticky: only a fresh hash of provably clean content may downgrade.
            return not (rel in rehashed and verdict is False)
        if verdict is None:
            # No evidence. A digest computed THIS run from a file the scan could
            # not read must not be published while stored values exist that it
            # may carry; a merged entry keeps the placement the team already had.
            return bool(local_values) and rel in rehashed
        return verdict

    local_files: dict[str, str] = {
        rel: digest for rel, digest in files.items() if _routes_local(rel)
    }
    files = {rel: digest for rel, digest in files.items() if rel not in local_files}

    state_dir = safe_path(root, root / _STATE_DIR)
    state_dir.mkdir(parents=True, exist_ok=True)
    # Self-contained ignore rules, matching the bash installer: manifest.json stays
    # tracked (the team shares it), the credential half and the stash never do. Kept
    # here so the guarantee holds even in a project whose root .gitignore we did not
    # write — the secrets file must never depend on that having gone well.
    safe_path(root, state_dir / ".gitignore").write_text(
        "# Managed by governancekit.\n"
        "# manifest.json is intentionally NOT ignored — the team must share it.\n"
        "# manifest.override.json is what THIS MACHINE knows: identity answers and\n"
        "# hashes derived from them. It must never be committed.\n"
        "manifest.override.json\n"
        # The legacy local pair stays listed: a mixed-version fleet still writes
        # them, and an un-migrated target must not have them one `git add -A`
        # from tracked just because a newer kit rewrote this file first.
        "operator.json\n"
        "secrets.json\n"
        "context-telemetry.jsonl\n"
        "overwritten/\n"
        "pre-upgrade/\n"
        # Written by the SHELL installer's content migration, never by this one — and
        # that is exactly why it belongs here. This file is rewritten wholesale on
        # every run, so anything the other implementation ignores and this one omits
        # gets silently un-ignored on the first Python upgrade of a shell-installed
        # target. What `.gk/pre-migrate/` holds is the project's root contracts as
        # they stood before migration: the hand-edited AGENTS.md this whole protection
        # exists for, one `git add -A` away from being committed.
        "pre-migrate/\n"
        # Written by `remove-agents apply`; ignored by neither writer before today.
        "remove-agents-backup/\n"
        # Council records key off a local staged diff, which means nothing to anyone
        # else once the commit lands. The durable record is the prose council.md §4
        # requires in docs/napkin-lessons.md and the active RESUME.md.
        "council/\n",
        encoding="utf-8",
    )

    # What the kit seeded into `.credentials/`, by NAME. Not under `files` and never
    # with a digest: the names are this kit's own scaffolding, identical in every
    # project, while a hash of anything in that directory is the thing that must not be
    # written. Without this record `remove-agents` had no evidence of kit authorship
    # there at all, and de-adoption left the kit's own README and examples behind.
    previous_seeded = previous.get("seeded_credentials")
    seeded_credentials = sorted({
        *(previous_seeded if isinstance(previous_seeded, list) else []),
        *(Path(rel).name for rel in (seeded or []) if rel.startswith(f"{_CREDENTIALS_DIR}/")),
    })

    # Written ONLY when there is something to record. Stamping `[]` looks harmless and
    # is not: `remove-agents` distinguishes an ABSENT key (no information, fall back to
    # byte-identity) from a present one (a list to narrow by). An empty list read as a
    # record says "the kit seeded nothing here", which is false for every legacy target
    # — and every legacy target got one on its next `configure`. A council measured the
    # repair surviving exactly until the next ordinary command, then failing for good.
    state_payload: dict[str, object] = {
        "state_version": _STATE_VERSION,
        "repo": repo,
        "ref": ref,
        "metadata": shareable,
        "files": files,
    }
    if seeded_credentials:
        state_payload["seeded_credentials"] = seeded_credentials

    safe_path(root, root / _STATE_FILE).write_text(
        json.dumps(
            state_payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    # One local file, not two. Written only when there is something local to record,
    # so a project with no local answers never grows a confusing empty file.
    override_path = safe_path(root, root / _OVERRIDE_FILE)
    if local_meta or local_files:
        override_payload: dict[str, object] = {"state_version": _STATE_VERSION}
        if local_meta:
            override_payload["metadata"] = local_meta
        if local_files:
            override_payload["files"] = local_files
        override_path.write_text(
            json.dumps(override_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        override_path.chmod(0o600)
    elif override_path.exists():
        override_path.unlink()

    # Migration of the legacy pair, and it happens HERE, after the override is on
    # disk. `previous` was read through `_read_state`, which merges both legacy
    # files, so everything they held is already inside `local_meta` — deleting them
    # loses nothing and leaves ONE local source of truth. Deleting before the
    # override write would have a crash window where the answers exist nowhere.
    for legacy_rel in (_OPERATOR_FILE, _SECRETS_FILE):
        legacy_path = safe_path(root, root / legacy_rel)
        if legacy_path.exists():
            legacy_path.unlink()


# ── legacy layout migration ──────────────────────────────────────────────────────

# Files an older kit installed into every target and that this kit withdraws. Removed
# on install and on upgrade, not merely stopped — the operator's ruling on the donation
# data was that "não pode haver referência alguma", and a file already sitting in three
# projects is a reference that stopping the copy does not undo.
#
# `.docs/index.html` is the kit's landing page. It was never documentation a governed
# project needs: it carries the author's own donation section with a real PIX key, a BR
# Code containing his civil name and city, an Ethereum address and a Ko-fi link, plus an
# outbound request to a QR service. The Python installer already refused to ship it; the
# shell installer copied it (`copy_file_replace ".docs/index.html"`), and the shell
# installer is being retired. Withdrawing it here reaches the targets that already have
# it, which stopping the copy cannot.
#
# `scripts/install-agents-kit.sh` (AC-30, folding AC-6 and AC-10): the operator decided
# the shell installer retires rather than gets reconciled with this one. Two installers
# writing the same manifest and the same managed `.gitignore` block, with no shared
# source of truth, produced two concrete defects (AC-6: the shell's `write_manifest`
# drops any key the Python side added that it does not itself know about; AC-10: the
# shell's `.gitignore` rewrite drops suffixes — `*.kit-new`, `*.pre-draft` — that guard
# the operator's own name and prose) and is a standing source of more of the same class.
# Removing it from `_FRESH_PATHS`/`_UPGRADE_PATHS` stops this kit from re-seeding it;
# withdrawing it here reaches every project that already has a copy, the same way
# `.docs/index.html` was reached. The source repository (AI-Agents) retiring its own
# copy of the script — and the docs that tell an operator to run it — is separate,
# tracked work: this kit's withdrawal does not wait on it, because a stale local copy
# left on disk after the source stops shipping it is exactly the kind of drift this
# mechanism exists to close.
_WITHDRAWN_PATHS: tuple[str, ...] = (
    ".docs/index.html",
    "scripts/install-agents-kit.sh",
)


def _remove_withdrawn(root: Path) -> list[str]:
    """Delete files this kit no longer ships, and say which. Never silently."""
    removed: list[str] = []
    for rel in _WITHDRAWN_PATHS:
        target = root / rel
        # A symlink here is the project's own decision about its own path; unlinking
        # the link would be removing something the kit did not put there.
        if target.is_symlink() or not target.is_file():
            continue
        try:
            target.unlink()
        except OSError:
            continue
        removed.append(rel)
    return removed


def _migrate_legacy_layout(root: Path) -> tuple[bool, list[str]]:
    """Migrate a legacy install (kit in ``docs/``, project in ``docs/project/``).

    Moves kit-owned docs from ``docs/`` to ``.docs/`` and promotes ``docs/project/*``
    up into ``docs/`` (the new project territory). Backs ``docs/`` up first. A no-op
    if ``.docs/`` already exists (already migrated) or no legacy markers are present.

    Returns ``(migrated, notes)`` where *notes* is a human-readable report.
    """
    docs = safe_path(root, root / "docs")
    dotdocs = safe_path(root, root / ".docs")
    # Legacy markers must be KIT-SPECIFIC. A generic name like docs/software-overview.md
    # is a common project filename; triggering on it would relocate a non-kit project's
    # whole docs/ (e.g. a GitHub Pages site) into the hidden .docs/. Require a marker a
    # random project is extremely unlikely to own: the kit's agents/ rule dir or its
    # workflows/session-close.md.
    markers = [docs / "agents", docs / "workflows" / "session-close.md"]
    if not docs.is_dir() or not any(m.exists() for m in markers):
        return False, []

    for path in docs.rglob("*"):
        if path.is_symlink():
            raise UnsafePathError(f"refusing symlink in legacy migration source: {path}")

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


def _content_migration_required(root: Path) -> bool:
    """Whether a layout backup still contains contracts outside the load path."""
    backup_agents = root / _MIGRATION_BACKUP_DIR / "agents"
    project_rules = root / "docs" / "project-rules.md"
    project_rules_dir = root / "docs" / "project-rules"
    return backup_agents.is_dir() and not project_rules.exists() and not project_rules_dir.is_dir()


_READINESS_ASIDE_DIR = ".gk/readiness-migration"


def _migrate_readiness_files_to_docs(root: Path) -> tuple[bool, list[str]]:
    """Bring ``software-overview.md`` and ``limits.md`` back from ``.docs/`` to ``docs/``.

    They were classified as kit-owned between 2026-07-01 and 2026-08-04 and installed
    under ``.docs/``. They are project-owned — the project writes them and owns their
    readiness flags — so the Start Gate must read them from ``docs/``, which the kit
    never overwrites.

    Idempotent, and it never destroys content: a symlink is the workaround projects
    used for this same misfiling, so dropping it completes the migration; a target
    holding both keeps the ``docs/`` copy and gets the ``.docs/`` one set aside.
    """
    notes: list[str] = []
    moved = False
    for name in ("software-overview.md", "limits.md"):
        src = root / ".docs" / name
        dst = root / "docs" / name
        if not src.exists() and not src.is_symlink():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)

        if src.is_symlink():
            src.unlink()
            notes.append(f"readiness: removed .docs/{name} symlink — docs/{name} is authoritative")
            moved = True
            continue

        if dst.exists():
            if src.read_bytes() == dst.read_bytes():
                src.unlink()
                notes.append(f"readiness: .docs/{name} was identical to docs/{name} — duplicate removed")
                moved = True
                continue
            aside = root / _READINESS_ASIDE_DIR
            aside.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(aside / name))
            notes.append(
                f"readiness: CONFLICT on {name} — docs/{name} kept as authoritative; "
                f"the .docs/ copy is at {_READINESS_ASIDE_DIR}/{name} for review"
            )
            moved = True
            continue

        shutil.move(str(src), str(dst))
        notes.append(f"readiness: .docs/{name} → docs/{name} (project-owned)")
        moved = True
    return moved, notes


def _migrate_legacy_content(root: Path) -> tuple[bool, list[str]]:
    """Preserve legacy agent contracts in project-owned reading paths.

    Layout migration protects the original tree in ``.docs-migration-bak``. This
    explicit second stage makes any agent role that is project-specific (or differs
    from the refreshed kit role) reachable through ``docs/project-rules`` and the
    required-reading index. It never deletes the backup or overwrites existing
    project rules.
    """
    backup_agents = safe_path(root, root / _MIGRATION_BACKUP_DIR / "agents")
    if not backup_agents.is_dir():
        return False, ["content migration: no legacy agent backup found"]

    selected: list[Path] = []
    kit_agents = root / ".docs" / "agents"
    for source in sorted(backup_agents.rglob("*.md")):
        relative = source.relative_to(backup_agents)
        current = kit_agents / relative
        if not current.is_file() or current.read_bytes() != source.read_bytes():
            selected.append(source)

    rules_dir = safe_path(root, root / "docs" / "project-rules")
    rules_dir.mkdir(parents=True, exist_ok=True)
    migrated = rules_dir / "legacy-agent-contracts.md"
    if migrated.exists():
        return False, ["content migration: docs/project-rules/legacy-agent-contracts.md already exists"]

    sections = [
        "# Migrated Legacy Agent Contracts",
        "",
        "Project-specific contracts preserved from the legacy AI-Agents layout. "
        "The original backup remains in `.docs-migration-bak/` for audit.",
    ]
    for source in selected:
        sections.extend([
            "",
            f"## {source.relative_to(backup_agents).as_posix()}",
            "",
            source.read_text(encoding="utf-8", errors="replace").rstrip(),
        ])
    if not selected:
        sections.extend(["", "No project-specific differences were detected."])
    migrated.write_text("\n".join(sections) + "\n", encoding="utf-8")

    project_rules = root / "docs" / "project-rules.md"
    if not project_rules.exists():
        project_rules.write_text(
            "# Project Rules\n\n"
            "Read `docs/project-rules/legacy-agent-contracts.md` before work that "
            "matches its operational domain.\n",
            encoding="utf-8",
        )
    _add_required_reading_entries(root, [
        "docs/project-rules.md",
        "docs/project-rules/legacy-agent-contracts.md",
    ])
    return True, [f"content: {len(selected)} legacy contract(s) extracted to docs/project-rules/"]


def _add_required_reading_entries(root: Path, paths: list[str]) -> None:
    index = safe_path(root, root / "docs" / "required-reading.md")
    existing = index.read_text(encoding="utf-8") if index.exists() else "# Required Reading\n"
    lines = [line for line in existing.splitlines() if line.strip().lower() not in {"- (none)", "* (none)"}]
    for path in paths:
        if path not in existing:
            lines.append(f"- `{path}` — migrated project-specific contract")
    index.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


# ── project-owned docs ──────────────────────────────────────────────────────────

def _ensure_project_docs(root: Path) -> None:
    """Seed missing project-owned docs without overwriting project content."""
    project_dir = safe_path(root, root / _PROJECT_DOCS_DIR)
    project_dir.mkdir(parents=True, exist_ok=True)

    readme = project_dir / "README.md"
    if not readme.exists():
        readme.write_text(_PROJECT_DOCS_README, encoding="utf-8")

    required_reading = project_dir / "required-reading.md"
    if not required_reading.exists():
        required_reading.write_text(_PROJECT_REQUIRED_READING, encoding="utf-8")

    project_rules = project_dir / "project-rules.md"
    if not project_rules.exists():
        project_rules.write_text(_PROJECT_RULES, encoding="utf-8")


# ── track-kit-docs config ─────────────────────────────────────────────────────────

def _read_kit_config(root: Path) -> dict:
    path = safe_path(root, root / _CONFIG_FILE)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_kit_config(root: Path, config: dict) -> None:
    path = safe_path(root, root / _CONFIG_FILE)
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

_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]+)\}\}")

# Text file extensions worth scanning for placeholders. Kept deliberately small —
# the kit's templates are Markdown / dotfiles / shell.
_TEXT_SUFFIXES: frozenset[str] = frozenset({
    ".md", ".txt", ".sh", ".bash", ".html", ".json", ".toml", ".cfg", ".ini",
    ".yml", ".yaml", ".py", ".rules",
})

# Dotfiles (no suffix) that the kit ships with placeholders.
_TEXT_NAMES: frozenset[str] = frozenset({
    ".cursorrules", ".windsurfrules",
})


def _is_text_file(path: Path) -> bool:
    return path.suffix in _TEXT_SUFFIXES or path.name in _TEXT_NAMES


def _iter_scan_targets(
    root: Path, rel_paths: Iterable[str], *, exclude: frozenset[str] = frozenset()
) -> Iterator[Path]:
    """Walk every text file under *rel_paths*, one scope for every placeholder reader.

    Shared by ``install-agents``, ``configure`` and ``doctor`` (AI-GovernanceKit#8):
    before this, each had its own list and its own walk, and only ``configure``'s
    actually descended into directories. ``_do_upgrade``/``_do_fresh`` return
    directory entries as single items (``['AGENTS.md', '.docs']``), and
    ``install-agents``/``doctor`` both stopped there without reading anything below
    — so a raw ``{{TOKEN}}`` under ``.docs/workflows/`` passed both the fill pass and
    the doctor check that was supposed to catch what the fill pass missed, while
    `configure`'s independent `rglob` scan (the only one of the three that walked)
    saw it correctly. A directory is walked with ``rglob``; a symlink anywhere in the
    tree is refused, matching the guard ``configure`` already applied on its own.
    """
    for rel in rel_paths:
        if rel in exclude:
            continue
        path = root / rel
        if path.is_dir():
            safe_path(root, path)
            candidates: Iterable[Path] = path.rglob("*")
        elif path.is_file():
            candidates = (path,)
        else:
            continue
        for candidate in candidates:
            if candidate.is_symlink():
                raise UnsafePathError(f"refusing symlink in managed kit path: {candidate}")
            if not safe_regular_file(root, candidate) or not _is_text_file(candidate):
                continue
            yield candidate

# A stored answer is text this process did not author: it comes from `.gk/manifest.json`,
# the half of the state a team shares and commits. The cap exists for ONE reason — to
# bound what a hostile or mistaken value can make a render pass allocate. It is not a
# validity rule, and treating it as one broke a working slot.
#
# It was 4096, justified in a comment by "the longest declared slot is an e-mail
# address". That was false when written: a declared slot then held a
# base64 PNG. Worse, 4096 lived only in `_prerender_source`, which renders the
# downloaded SOURCE; carrying it to the writers that render the TARGET turned a
# working answer into a refusal, and the council measured the consequence — an upgrade
# UN-RENDERED a file the previous release had rendered, `doctor` flipped to FAIL, and
# the verdict oscillated run by run against a host with an older wheel.
#
# 1 MiB is a DoS bound, not a guess about content: a base64 PNG of a bank-app QR
# screenshot measured 98,848 characters, so every plausible answer fits with an order
# of magnitude to spare, while a shared manifest still cannot make this pass allocate
# without limit. A value over it is refused BY NAME, with the remedy.
_MAX_PLACEHOLDER_VALUE = 1_048_576

# Tokens no longer COLLECTED (they are gone from _PLACEHOLDER_DESCRIPTIONS, so nothing
# prompts for them) but still SUBSTITUTED when a stored value exists. Without this a
# target installed before the retirement dead-ends: an upgrade at a ref whose files
# still carry `{{SMTP_ACCOUNT}}` leaves it raw, `doctor` fails non-advisory with "kit
# not configured", and `configure` cannot fix it because its known-token set is built
# from _PLACEHOLDER_DESCRIPTIONS too. Found by the council of AI-Agents#5 / GK#7.
_RETIRED_PLACEHOLDERS: dict[str, str] = {
    "SMTP_ACCOUNT": "retired 2026-08-10 (AI-Agents#5): the canonical contract names no "
                    "email transport, so nothing asks for this any more.",
    # Same field one over, and the council caught the asymmetry: it was left describable
    # while its sibling was retired, AND it was outside _OPERATOR_PLACEHOLDERS — so a
    # legacy stored answer would have been written into the COMMITTED manifest, the
    # exact hazard the SMTP_ACCOUNT comment says that set exists to prevent. No shipped
    # file has ever carried the token, so nothing collected it either.
    "SMTP_DOMAIN": "retired 2026-08-10 (AI-Agents#5): transport configuration, and no "
                   "kit file ever carried the slot.",
}

_PLACEHOLDER_DESCRIPTIONS: dict[str, str] = {
    "OPERATOR_NAME": "operator / project owner name (used in agent greetings)",
    "GITHUB_OWNER": "GitHub username or organisation that owns the repo",
    "PROJECT_SLUG": "short identifier for this project (used in work_ids and logs, e.g. my-app)",
    "ORG_NAME": "organisation or company name",
    "PROJECT_ROOT": "absolute path to the project root on this machine",
}


def _render_table(known: dict[str, str] | None) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Filter stored answers down to what may be substituted into kit text.

    Returns the usable table and the declared tokens that were REFUSED, with the
    reason for each, so the caller can say so. A refusal nobody reports is how a
    leak becomes a silence, and this delivery already shipped that mistake once:
    round 2 found a `try` that turned a traceback into a silently empty provider list.

    These rules bound the input. They do NOT close the injection chain on their own —
    `_render_text` does that, and its docstring says why the difference matters. The
    first cut of this gate claimed otherwise and was wrong in a way that is worth
    keeping in writing, because the claim was measurable and nobody measured it.

    1. **Declared tokens only.** A token the kit does not ship cannot be filled by a
       value the kit did not ask for. Unknown keys are dropped without a word — the
       state carries ordinary metadata too, and reporting it would bury the signal.
    2. **Text only.** JSON permits numbers, lists and objects; a hostile shared
       manifest used to abort an install with a raw `TypeError` from the regex.
    3. **Bounded length**, as a denial-of-service bound and nothing else. See
       `_MAX_PLACEHOLDER_VALUE`: reading it as a validity rule broke a working slot.
    4. **A value may not itself carry placeholder syntax.** Cheap, early, and it
       catches the obvious carrier — but only the obvious one. A value is not where
       the property lives.

    The refused value is left in the state and not deleted. It arrived from
    `.gk/manifest.json`, the half a team shares; dropping the victim's copy would not
    remove it from the source and would silently discard whatever else it holds.
    """
    table: dict[str, str] = {}
    refused: list[tuple[str, str]] = []
    for key, value in (known or {}).items():
        if key not in _PLACEHOLDER_DESCRIPTIONS and key not in _RETIRED_PLACEHOLDERS:
            continue
        if value is None:
            # Absence, not a hostile value: `null` is how a hand-edited manifest says
            # "not set", and it belongs in the same branch as "".
            continue
        if not isinstance(value, str):
            refused.append((key, f"stored value is {type(value).__name__}, not text"))
            continue
        if not value:
            continue
        if len(value) > _MAX_PLACEHOLDER_VALUE:
            refused.append(
                (key, f"stored value is longer than {_MAX_PLACEHOLDER_VALUE} characters")
            )
            continue
        if "{{" in value or "}}" in value:
            # Braces, not "a complete token". Refusing only a full `{{TOKEN}}` left the
            # pieces legal, and a council measured what pieces do: `{{SECRET_SLOT` in
            # one slot and `}}` in the adjacent one compose into a live token during a
            # single sweep. Every declared slot holds a name, handle, slug, path,
            # address or payload; none of them needs a brace, so the cheap rule is also
            # the complete one for values.
            refused.append(
                (key, "stored value contains {{ or }}, which no declared slot needs "
                      "and which composes into placeholder syntax during a render")
            )
            continue
        table[key] = value
    return table, refused


def _render_text(text: str, table: dict[str, str]) -> tuple[str, int, list[str]]:
    """Render *text*; return the result, the substitution count, and any COMPOSING tokens.

    The runtime backstop of a three-layer defence. The other two are cheaper and sit
    where the problem starts: `_render_table` refuses a value carrying a brace, and
    `tests/test_render_gate.py` refuses a SHIPPED FILE whose own text could compose.
    This layer answers the question neither can: did THIS render, on THIS text,
    manufacture placeholder syntax?

    Four designs were tried for that question, and the first three read plausibly:

    1. *one sweep* — cannot re-substitute its own output. True per stage, and the
       pipeline has three stages; what one writes, the next reads as ordinary text.
    2. *the value may not carry a complete token* — true about the value, and the
       braces can come from the template instead.
    3. *the output may not contain a token the input lacked* — compares SETS, so a
       render that MOVES a secret into a new position inside a file that already
       carried that token passes. Two councils measured it independently, one of them
       landing a stored secret in a document title.
    4. this one: **no placeholder match in the output may overlap text that came from
       a substituted value.**

    Only the fourth is about the mechanism that does the harm — a value contributing
    characters to a live token — instead of about a symptom of it. It needs the
    positions, which is why this builds the output by hand rather than calling `sub`.

    Callers reach this through `_render_file_text`, which owns the response to a
    composing token; its docstring carries the account of why the response is per
    file AND per token. This one describes only the detection, deliberately: two
    adjacent docstrings narrating the same mechanism differently is how the `{2,}`
    against `+` regex drift started in `doctor.py`.
    """
    parts: list[str] = []
    spans: list[tuple[int, int, str]] = []
    pos = out = substitutions = 0
    for match in _PLACEHOLDER_RE.finditer(text):
        replacement = table.get(match.group(1))
        if replacement is None:
            continue
        literal = text[pos:match.start()]
        parts.append(literal)
        out += len(literal)
        parts.append(replacement)
        spans.append((out, out + len(replacement), match.group(1)))
        out += len(replacement)
        pos = match.end()
        substitutions += 1
    parts.append(text[pos:])
    rendered = "".join(parts)
    if not substitutions:
        return text, 0, []
    # Every match, not the first: two composable shapes in one file are ordinary, and
    # returning early meant the second token was never detected — the caller dropped
    # the first, rendered again, hit the second, and silently left the whole file raw.
    composing: set[str] = set()
    for match in _PLACEHOLDER_RE.finditer(rendered):
        composing.update(
            t for start, end, t in spans if start < match.end() and match.start() < end
        )
    if composing:
        # Only the tokens whose inserted text actually overlaps a manufactured match.
        # An earlier cut blamed every token the file carried, which named innocent
        # slots — including personal-data ones — in a security message.
        return text, 0, sorted(composing)
    return rendered, substitutions, []


def _render_file_text(text: str, table: dict[str, str]) -> tuple[str, int, set[str]]:
    """Render *text*, dropping only the tokens that compose IN THIS TEXT.

    Two responses to a composable template were tried and both damaged the target:

    * **skip the file** — its innocent slots stayed raw while the same slots rendered
      in sibling files, so source and target disagreed and the next upgrade read the
      kit's own substitution as operator intent;
    * **drop the token for the whole run** — that removed the sibling asymmetry and
      replaced it with blast radius: one composable file anywhere in the downloaded
      tree un-rendered every file carrying that token, freezing `AGENTS.md` for any
      target without a manifest entry, permanently.

    The narrowest response is both: drop the composing token, in the file where it
    composes, and nowhere else. The kit's defective file keeps a raw slot; every other
    file, and every other slot in the defective file, renders exactly as before.

    Loops to a fixed point because dropping one token can reveal a second.
    """
    dropped: set[str] = set()
    while True:
        current = {k: v for k, v in table.items() if k not in dropped}
        if not current:
            return text, 0, dropped
        rendered, made, composing = _render_text(text, current)
        if not composing:
            return rendered, made, dropped
        dropped.update(composing)


def _report_refused_values(
    refused: list[tuple[str, str]], *, needed: set[str] | None = None
) -> None:
    """Name every refused value that this render actually needed, with the way out.

    *needed* is the set of tokens the text being rendered carries. Without it the
    installer warned about slots no shipped file uses, and warned twice per run (once
    for the source pass, once for the target pass) with identical wording — which
    trains the reader to skip exactly the block that matters.

    The remedy is named here rather than left to the operator to infer. The council
    measured what happens without it: `doctor` fails, tells them to run `configure`,
    `configure` refuses the same stored value again, and the natural way out is to
    paste the value into the kit file by hand — a git-tracked file, which is the one
    place the operator/secrets split exists to keep it out of.
    """
    if needed is not None:
        refused = [(t, r) for t, r in refused if t in needed]
    if not refused:
        return
    print("\nWarning: stored value(s) refused and NOT substituted:")
    for token, reason in sorted(refused):
        print(f"  {{{{{token}}}}} — {reason}")
    print(
        "  Stored answers live in .gk/manifest.json (shared) and "
        ".gk/manifest.override.json (local).\n"
        "  Replace one with: governancekit --root <project> configure "
        "--set <TOKEN>=<value>"
    )


def _report_composing_tokens(
    dropped: dict[str, set[str]],
    *,
    prefix: str = "",
    already: set[tuple[str, str]] | None = None,
) -> set[tuple[str, str]]:
    """Name each slot left raw AND the file that made it so; return what was reported.

    *dropped* maps a file label to the tokens dropped in it. Naming the file is the
    whole point: the message tells the operator to report a template defect, and the
    first cut did not say which file — the caller had the paths and did not pass them.

    *already* suppresses tokens a previous pass in the same run reported. Without it
    an upgrade printed this block twice, byte-identical, once from the source pass and
    once from the target pass — the repetition `_report_refused_values` says "trains
    the reader to skip exactly the block that matters".

    The remedy is deliberately NOT `configure --set`: the braces come from text the
    kit ships, so no answer the operator can type changes the outcome.
    """
    already = already or set()
    fresh = {
        rel: sorted(t for t in tokens if (rel, t) not in already)
        for rel, tokens in dropped.items()
        if any((rel, t) not in already for t in tokens)
    }
    if not fresh:
        return set()
    print(
        "\nWarning: slot(s) left raw — the kit's own text around them would have "
        "combined with the stored value into new placeholder syntax:"
    )
    for rel in sorted(fresh):
        for token in fresh[rel]:
            print(f"  {{{{{token}}}}} in {prefix}{rel}")
    print(
        "  The braces come from the file's own text, not from your answer, so "
        "`configure --set`\n  will not change this. If the file is the kit's, report "
        "it; if it is yours, edit it."
    )
    return {(rel, t) for rel, tokens in fresh.items() for t in tokens}


def _text_files(root: Path) -> Iterator[tuple[Path, str]]:
    """Every readable UTF-8 regular file under *root*. Symlinks and binaries skipped."""
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            yield path, path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue


def _fill_placeholders(
    root: Path,
    installed_paths: list[str],
    *,
    known: dict[str, str] | None = None,
    already_reported: set[tuple[str, str]] | None = None,
) -> dict[str, str]:
    """Scan installed files for known placeholder tokens and fill them in.

    Only tokens described in ``_PLACEHOLDER_DESCRIPTIONS`` are treated as fillable
    variables, and only in canonical ``{{TOKEN}}`` form. Bracketed markers such as
    ``[MANDATORY]`` are policy vocabulary, not personalization slots. Mirrors
    ``configure.py``.

    *known* carries answers from previous runs (``.gk/state.json``). They are offered
    as the default so the operator confirms with Enter instead of retyping, and they
    are applied without any prompt when there is no terminal — which is what gives an
    unattended ``--upgrade`` continuity across the template overwrite.

    Returns every value in force after this run, for the caller to persist.
    """
    # Collect all unique placeholders across installed files. `installed_paths` can
    # (and does) carry directory entries such as `.docs` — `_iter_scan_targets` walks
    # into them instead of skipping them; see its docstring for the bug this closes.
    placeholder_files: dict[str, list[Path]] = {}
    for path in _iter_scan_targets(root, installed_paths):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for token in _PLACEHOLDER_RE.findall(text):
            # Retired tokens are collected so a stored value can still be applied to a
            # legacy file that carries them; they are never asked about below.
            if token in _PLACEHOLDER_DESCRIPTIONS or token in _RETIRED_PLACEHOLDERS:
                placeholder_files.setdefault(token, []).append(path)

    known = known or {}

    if not placeholder_files:
        return dict(known)

    remembered = {t: known[t] for t in placeholder_files if known.get(t)}
    # A retired token with no stored value is not "unknown" — there is nobody left to
    # ask. Reporting it would send the operator to `configure`, which cannot fill it.
    unknown = [
        t for t in sorted(placeholder_files)
        if t not in remembered and t not in _RETIRED_PLACEHOLDERS
    ]

    if not sys.stdin.isatty():
        # Unattended: re-apply what we already know rather than leaving raw templates
        # behind, and report only what genuinely has no answer yet.
        values = dict(remembered)
        if unknown:
            print(
                "\nWarning: the following placeholders were not filled "
                "(no interactive terminal, no stored value):\n  "
                + ", ".join(f"{{{{{p}}}}}" for p in unknown)
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
            if token in _RETIRED_PLACEHOLDERS:
                # Apply what is stored, ask nothing: the slot no longer exists.
                if remembered.get(token):
                    values[token] = remembered[token]
                continue
            desc = _PLACEHOLDER_DESCRIPTIONS.get(token, "")
            current = remembered.get(token)
            # A stored value the gate would refuse is never offered as the default.
            # It used to be: the prompt read `{{ORG_NAME}} [{{OTHER_SLOT}}]: ` and
            # Enter re-submitted it, so the tool recommended the attacker's payload
            # and then refused what it had recommended.
            if current and not _render_table({token: current})[0]:
                current = None
            prompt = f"  {{{{{token}}}}}"
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

    # Apply substitutions through the same table and the same sweep the source pass
    # uses. They used to run different rules, and the gap between them was the leak:
    # this side had neither the one-pass sweep nor the length cap, and neither side
    # refused a value that carried placeholder syntax.
    table, refused = _render_table(values)
    _report_refused_values(refused, needed=set(placeholder_files))

    targets = sorted({p for token in table for p in placeholder_files.get(token, [])})

    changed: list[str] = []
    dropped: dict[str, set[str]] = {}
    for path in targets:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        new_text, _, blocked = _render_file_text(text, table)
        if blocked:
            dropped[str(path.relative_to(root))] = blocked
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed.append(str(path.relative_to(root)))
    # `already` suppresses what the source pass just said about the same tokens: the
    # block used to print twice per upgrade, byte-identical, once from each pass.
    _report_composing_tokens(dropped, already=already_reported)
    # Prune ONLY tokens that composed in EVERY file carrying them. Pruning the union
    # took the blast radius out of the rendering and left it in the accounting: a
    # token written successfully into one file vanished from the report and from the
    # state, so the kit rendered a target and recorded nothing about it. That is the
    # freeze `persist_placeholder_values` was written to prevent, arriving by the
    # bookkeeping instead of by the render.
    handled = {str(p.relative_to(root)) for p in targets}
    table = {
        k: v for k, v in table.items()
        if not (
            placeholder_files.get(k)
            and all(
                k in dropped.get(str(p.relative_to(root)), set())
                for p in placeholder_files[k]
                if str(p.relative_to(root)) in handled
            )
        )
    }

    if changed:
        print("\nPlaceholders filled in: " + ", ".join(sorted(set(changed))))

    # Warn about any that were skipped. Retired tokens are excluded for the same
    # reason they never reach `unknown`: naming them sends the operator to a slot that
    # no longer exists. The guard was added to `unknown` and to the prompt loop and
    # missed here, because the test's fixture held only the retired token and the
    # function returned before reaching this line. Council round 2 of GK#7.
    # `table`, not `values`: a token whose value was refused above is still unfilled,
    # and saying otherwise would report a substitution that did not happen.
    unfilled = [
        t for t in placeholder_files
        if t not in table and t not in _RETIRED_PLACEHOLDERS
    ]
    if unfilled:
        print(
            "Still unfilled (skipped): "
                + ", ".join(f"{{{{{t}}}}}" for t in sorted(unfilled))
        )

    # Only what passed the gate is carried forward. A refused value that came from the
    # state stays there untouched (it is still in `known`); a refused value TYPED this
    # run is not adopted. That falls out of the table without tracking where each value
    # came from, which would be a second code path to keep in step.
    return {**known, **table}


# ── .gitignore management ──────────────────────────────────────────────────────

# The secret paths the managed block ignores, and the single source of truth for
# `doctor._check_gitignore_secrets`, which probes the same list with `git check-ignore`.
#
# They were two lists, and they disagreed: the generator emitted eighteen entries and
# none of them covered `.env`, while the check failed the repository for exactly that.
# Every project the kit installed was born failing a mandatory gate on a file the kit
# itself wrote — observed on CodexBridge, where `.credentials/` was covered and `.env`
# was not. Two gates over one contract must read one list, or the newer one drifts and
# the tool ends up refusing what it produces. That is the same defect as the readiness
# flag on 2026-08-04, where a shell regex and a Python substring judged the same file
# differently.
#
# `.env` is deliberately a family: `.env.local`, `.env.production` and friends carry
# the same secrets. `.env.example` is re-included because it is documentation by
# convention and every project has one — a rule that ignores it teaches operators to
# fight the managed block, and `doctor`'s own tracked-secrets check already exempts it.
# Suffixes and names that mark a file as a template shipped on purpose, not a secret.
# `doctor._is_secret_template` imports these: the ignore block must re-include exactly
# what the tracked-secrets check forgives, or the two disagree again in the other
# direction — a file the checker calls safe that the block makes untrackable.
SECRET_TEMPLATE_SUFFIXES: tuple[str, ...] = (".example", ".sample", ".template", ".dist")
SECRET_TEMPLATE_NAMES: frozenset[str] = frozenset({".env.missing", ".env-example"})
# Scaffolding the kit itself seeds into `.credentials/`. `.credentials/` as a bare
# directory pattern would make all of them permanently untrackable: git does not
# descend into an excluded directory, so a nested `!README.md` never fires. The
# pattern has to exclude the *contents* and re-include the docs.
CREDENTIALS_DOC_NAMES: tuple[str, ...] = (".gitignore", ".keep", "README*")


def _secret_ignore_patterns() -> tuple[str, ...]:
    patterns: list[str] = [
        ".env",
        ".env.*",
        ".envrc",
        # Package-manager and network credential files. Bare names, so no glob can
        # reach past them — the low-risk half of what the security lens found missing.
        ".npmrc",
        ".pypirc",
        ".netrc",
        # A private key in a repository is a mistake often enough that the default is
        # to ignore it. A project that genuinely tracks a key fixture uses `git add -f`
        # once; the reverse mistake is unrecoverable. Risk accepted in the round record.
        "*.pem",
        "*.key",
        ".credentials/*",
    ]
    patterns += [f"!.env{suffix}" for suffix in SECRET_TEMPLATE_SUFFIXES]
    patterns += [f"!{name}" for name in sorted(SECRET_TEMPLATE_NAMES)]
    patterns += [f"!.credentials/{name}" for name in CREDENTIALS_DOC_NAMES]
    patterns += [f"!.credentials/*{suffix}" for suffix in SECRET_TEMPLATE_SUFFIXES]
    return tuple(patterns)


SECRET_IGNORE_PATTERNS: tuple[str, ...] = _secret_ignore_patterns()


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
        elif dest == _CREDENTIALS_DIR:
            # The secret patterns below already cover this directory, as `.credentials/*`
            # plus re-includes for the scaffolding. Emitting the bare directory name here
            # too silently wins over them: git does not descend into an excluded
            # directory, so `!.credentials/README*` never fires and every file the kit
            # seeds there is permanently untrackable. The comment above
            # CREDENTIALS_DOC_NAMES has said so since the patterns were written; this
            # branch was quietly contradicting it, and the gitignore test never ran the
            # real path list.
            continue
        else:
            entries.append(dest)
    # The legacy-migration backup is a full copy of the pre-migration docs/ tree and
    # must never be committed. Always ignore it, independent of track-kit-docs.
    entries.append(f"{_MIGRATION_BACKUP_DIR}/")
    # .gk/manifest.json is deliberately NOT ignored: a team sharing a checkout must
    # share the file hashes, or each programmer's upgrade would judge ownership from a
    # different baseline. Only the local operator/secrets halves and the stash are
    # ignored, unconditionally — unlike .docs/, this is not subject to the
    # track-kit-docs choice.
    entries.append(_OVERRIDE_FILE)
    # The legacy pair stays listed for the un-migrated and mixed-version fleet.
    entries.append(_OPERATOR_FILE)
    entries.append(_SECRETS_FILE)
    entries.append(f"{_STATE_DIR}/context-telemetry.jsonl")
    entries.append(f"{_STATE_DIR}/overwritten/")
    entries.append(f"{_STATE_DIR}/pre-upgrade/")
    entries.append(f"{_STATE_DIR}/pre-migrate/")
    entries.append(f"{_STATE_DIR}/remove-agents-backup/")
    # The removal PLAN, not just its backups. It records a verdict per path — including
    # `remove` at confidence 1.0 with review dispensed — and `apply` acts on the file,
    # not on a fresh analysis. Committed, it travels to every clone and can be applied
    # by a teammate whose target does not match the one it was built against; kept
    # across an upgrade, it applies decisions the new code has since corrected. It sat
    # outside the managed block while every sibling artefact of `.gk/` was inside it.
    entries.append(f"{_STATE_DIR}/remove-agents-plan.json")
    # The refused context draft: the kit wrote it, but it is a proposal about the
    # project's own documents and has no business in the history of a clone.
    entries.append(f"{_STATE_DIR}/context-proposal/")
    # The parked copy of a protected file. It is rendered with the operator's stored
    # answers — that is what makes it mergeable — which means it carries the very
    # value `_OPERATOR_PLACEHOLDERS` keeps out of the tracked state. `AGENTS.md`
    # itself is ignored by the block above; its `.kit-new` sibling was not, so it sat
    # in `git status` as untracked and one `git add -A` from committing the operator's
    # name. Introduced by rendering the source, caught by the council's second round.
    entries.append("*.kit-new")
    # Same reason, other artifact: `<file>.pre-draft` is the copy taken when an accepted
    # draft replaces text the project wrote. It holds the operator's own prose, and it
    # was the one stash of this kit that git could see.
    entries.append("*.pre-draft")
    entries.extend(SECRET_IGNORE_PATTERNS)
    return entries


def _update_gitignore(gitignore: Path, paths: list[str], *, track_kit_docs: bool = False) -> None:
    gitignore = safe_path(gitignore.parent, gitignore)
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
