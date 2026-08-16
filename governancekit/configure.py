from __future__ import annotations

import re
import sys
import socket
from dataclasses import dataclass, field
from pathlib import Path

from .identity import (
    ALL_FIELDS,
    REQUIRED_FIELDS,
    _FIELD_DESCRIPTIONS,
    Identity,
    identity_from_values,
    load_identity,
    read_existing_operator_name,
    save_identity,
)
from .install_agents import (
    _FRESH_PATHS,
    _PLACEHOLDER_DESCRIPTIONS,
    _RETIRED_PLACEHOLDERS,
    _PLACEHOLDER_RE,
    _PROJECT_SEED_PATHS,
    _dest_rel,
    _render_table,
    _render_file_text,
    _report_composing_tokens,
    _report_refused_values,
    persist_placeholder_values,
)
from .path_safety import UnsafePathError, safe_path, safe_regular_file

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

# Known kit placeholders. Only these are filled — arbitrary [WORD] tokens (e.g.
# the doctor's own `[FAIL]` / `[HINT]` output samples in README) are left alone.
#
# RETIRED tokens are included. They are no longer COLLECTED (nothing prompts for them),
# but a legacy file can still carry the slot, and `doctor`'s non-advisory
# `unfilled placeholders` check names THIS command as the remedy. Deriving the set from
# the descriptions alone made that remedy a no-op: the check failed forever and the
# command it named did nothing — a regression against the behaviour before the
# retirement, when `configure` could fill it. Council round 2 of GK#7.
_KNOWN_TOKENS: frozenset[str] = frozenset(_PLACEHOLDER_DESCRIPTIONS) | frozenset(
    _RETIRED_PLACEHOLDERS
)

# Credentials are local project state, not kit templates. They may intentionally
# contain symlinks to a private credential store and must never be read or changed
# by ``configure``.
_CONFIGURE_EXCLUDED_PATHS: frozenset[str] = frozenset({".credentials"})

# What a placeholder NAME looks like. Used to decide whether an unknown --set key
# is safe to echo back: a key with this shape is a mistyped token, a key without
# it is the operator's own text — a name, an e-mail, or a whole payload landed in
# the key half by an inverted pair.
_TOKEN_SHAPE = re.compile(r"[A-Z][A-Z0-9_]*")


@dataclass
class ConfigureResult:
    root: Path
    values: dict[str, str] = field(default_factory=dict)
    changed_files: list[str] = field(default_factory=list)
    unfilled: list[str] = field(default_factory=list)
    found_tokens: list[str] = field(default_factory=list)


def parse_set_pairs(pairs: list[str]) -> dict[str, str]:
    """Parse ``KEY=VALUE`` strings from ``--set`` into a mapping."""
    values: dict[str, str] = {}
    for raw in pairs:
        if "=" not in raw:
            raise ValueError(
                "invalid --set value: expected KEY=VALUE. The value is not shown "
                "here because it may be a secret."
            )
        key, val = raw.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(
                "invalid --set value: the key is empty. The value is not shown "
                "here because it may be a secret."
            )
        values[key] = val
    return values


@dataclass
class IdentityResult:
    root: Path
    saved: bool = False
    path: str = ""
    identity: Identity | None = None
    missing_required: list[str] = field(default_factory=list)
    gitignored: bool = False


def run_configure_identity(
    root: Path,
    *,
    preset: dict[str, str] | None = None,
    interactive: bool | None = None,
) -> IdentityResult:
    """Collect, validate and persist per-host identity fields.

    ``preset`` supplies non-interactive field values (from CLI flags). Any
    unfilled field is prompted for when a TTY is available, seeded from the
    existing identity file when present. Refuses to save while a REQUIRED field
    is missing, reporting the gap for a clear error.
    """
    root = root.resolve()
    preset = {k: v for k, v in (preset or {}).items() if v is not None and v != ""}

    if interactive is None:
        interactive = sys.stdin.isatty()

    existing = load_identity(root)
    inherited_operator = read_existing_operator_name(root) if existing is None else ""
    values: dict[str, str] = {}
    for f in ALL_FIELDS:
        if f in preset:
            values[f] = str(preset[f]).strip()
        elif existing is not None:
            cur = getattr(existing, f)
            values[f] = ",".join(cur) if isinstance(cur, list) else str(cur)
        elif f == "operator_name":
            values[f] = inherited_operator
        elif f == "instance_path":
            values[f] = str(root)
        elif f == "host_id" and interactive:
            values[f] = socket.gethostname()
        elif f == "branch_ownership" and interactive:
            values[f] = "all"
        else:
            values[f] = ""

    if interactive:
        print("\n── Configure host identity ──────────────────────────────────────")
        print("Press Enter to keep the current/blank value.\n")
        for f in ALL_FIELDS:
            if f in preset:
                continue
            desc = _FIELD_DESCRIPTIONS.get(f, "")
            required = " *required*" if f in REQUIRED_FIELDS else ""
            current = values.get(f, "")
            shown = f" [{current}]" if current else ""
            prompt = f"  {f}{required} ({desc}){shown}: "
            try:
                answer = input(prompt).strip()
            except EOFError:
                answer = ""
            if answer:
                values[f] = answer

    identity = identity_from_values(values)
    result = IdentityResult(root=root, identity=identity)
    result.missing_required = identity.missing_required()

    if result.missing_required:
        return result

    path = save_identity(root, identity)
    result.saved = True
    result.path = str(path.relative_to(root))
    result.gitignored = True
    return result


def _is_text_file(path: Path) -> bool:
    return path.suffix in _TEXT_SUFFIXES or path.name in _TEXT_NAMES


def _scan(root: Path) -> dict[str, list[Path]]:
    """Map each known placeholder token in active kit-owned files.

    Project-owned documents and migration recovery material are deliberately not
    scanned or changed by ``configure``.
    """
    found: dict[str, list[Path]] = {}
    for rel in _FRESH_PATHS:
        if rel in _PROJECT_SEED_PATHS or rel in _CONFIGURE_EXCLUDED_PATHS:
            continue
        path = root / _dest_rel(rel)
        if path.is_dir():
            safe_path(root, path)
            candidates = path.rglob("*")
        else:
            candidates = (path,)
        for candidate in candidates:
            if candidate.is_symlink():
                raise UnsafePathError(f"refusing symlink in managed kit path: {candidate}")
            if not safe_regular_file(root, candidate) or not _is_text_file(candidate):
                continue
            path = candidate
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for token in _PLACEHOLDER_RE.findall(text):
                if token in _KNOWN_TOKENS:
                    found.setdefault(token, []).append(path)
    return found


def run_configure(
    root: Path,
    *,
    preset: dict[str, str] | None = None,
    interactive: bool | None = None,
) -> ConfigureResult:
    """Fill kit placeholder variables only in managed kit files under *root*.

    ``preset`` supplies non-interactive ``KEY=VALUE`` answers. Remaining tokens are
    prompted for when a TTY is available (override with ``interactive``). Only
    canonical ``{{TOKEN}}`` placeholders are filled.
    """
    root = root.resolve()
    preset = dict(preset or {})
    found = _scan(root)
    result = ConfigureResult(root=root, found_tokens=sorted(found))

    # The preset is gated ONCE, here, for every path below. Three council lenses found
    # the same hole independently: the early-return branch persisted `preset` raw, so
    # the identical command wrote a poisoned value straight into the SHARED manifest
    # when the target happened to have no raw token left, and refused it loudly when it
    # did. A gate whose effect depends on where the target happens to be is not a gate.
    preset_table, preset_refused = _render_table(preset)
    _report_refused_values(preset_refused)

    # An undeclared key in `--set` is a typo, and it used to vanish: `_render_table`
    # drops unknown keys without a word — correct for the state, which carries ordinary
    # metadata, and wrong for an explicit instruction from the operator. The command
    # reported success while discarding what it was told to record.
    unknown = sorted(k for k in preset if k not in _KNOWN_TOKENS)
    if unknown:
        # Named, and the run continues. Dropping it in silence discarded an explicit
        # instruction; raising aborted the whole command, so a legacy script with one
        # stale key configured NOTHING where it used to configure everything else.
        # Both are the same trade — silence against noise — made in opposite
        # directions, and neither is what the operator needs.
        # Only keys SHAPED like a token are echoed. Both halves of `KEY=VALUE` are
        # free text from the operator, and the first cut of this warning protected the
        # value — saying so in as many words — while printing the key verbatim two
        # hundred lines below. An inverted pair puts a name, an e-mail or a whole
        # payload in the key, and `split("=", 1)` keeps a payload intact because it
        # carries no `=`. A key that has no token shape is not a mistyped token; it is
        # the operator's data, and naming it is the same leak wearing the other half.
        shaped = [k for k in unknown if _TOKEN_SHAPE.fullmatch(k)]
        unshaped = len(unknown) - len(shaped)
        parts = []
        if shaped:
            parts.append(", ".join(shaped))
        if unshaped:
            parts.append(
                f"{unshaped} more whose name is not token-shaped (not shown: a key "
                "that is not a token may be a value typed into the wrong half)"
            )
        print(
            "\nWarning: ignoring --set key(s) this kit does not declare: "
            + "; ".join(parts)
            # Retired tokens are deliberately absent: nothing collects them, so
            # offering one invites the operator to store an answer no slot consumes.
            + "\n  Known tokens: "
            + ", ".join(sorted(_PLACEHOLDER_DESCRIPTIONS))
        )

    if not found:
        # Nothing left to fill, but an explicit `--set` is still an answer worth
        # recording — and this is the ONLY path back for every target configured
        # before answers were persisted: its files are already rendered, so the scan
        # finds nothing, and without this the state stays empty, the source is never
        # pre-rendered, and the protected file reads as drifted forever. The fix would
        # otherwise have been forward-only, which round 2 measured.
        persist_placeholder_values(root, {t: v for t, v in preset_table.items() if v})
        return result

    if interactive is None:
        interactive = sys.stdin.isatty()

    # Deliberately NOT filtered by `found`. It was, and that is how a refused value
    # became permanent: once its slot had been rendered away, `--set` silently dropped
    # the new answer and there was no command left that could replace the poisoned one.
    # A refusal that cannot be undone is a mailbox that never empties.
    values: dict[str, str] = dict(preset_table)

    to_prompt = [t for t in sorted(found) if t not in values]
    if to_prompt and interactive:
        print("\n── Configure kit variables ────────────────────────────────────────")
        print("Press Enter to leave a value unchanged.\n")
        for token in to_prompt:
            desc = _PLACEHOLDER_DESCRIPTIONS.get(token, "")
            prompt = f"  {{{{{token}}}}}" + (f"  ({desc})" if desc else "") + ": "
            try:
                answer = input(prompt).strip()
            except EOFError:
                answer = ""
            if answer:
                values[token] = answer

    # Everything below reports and acts on `table`, never on `values`: a refused value
    # was not substituted, so calling it filled would be a claim the disk contradicts.
    # Same table and sweep the installer uses — this was the third writer with its own
    # sequential `str.replace`, and a policy with three implementations is a policy
    # that will drift again.
    table, refused = _render_table(values)
    _report_refused_values(refused)

    if not table:
        result.unfilled = sorted(found)
        return result

    # Apply every substitution to every file that holds at least one filled token.
    target_paths: set[Path] = set()
    for token in table:
        target_paths.update(found.get(token, []))

    dropped: dict[str, set[str]] = {}
    for path in sorted(target_paths):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        new_text, _, blocked = _render_file_text(text, table)
        if blocked:
            dropped[str(path.relative_to(root))] = blocked
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            result.changed_files.append(str(path.relative_to(root)))

    _report_composing_tokens(dropped)
    # Prune ONLY tokens that composed in EVERY file carrying them. Filtering by the
    # union took the blast radius out of the render and left it in the accounting: an
    # answer written into two files was recorded nowhere, `.gk/` was never created,
    # and the CLI printed `Filled 0 variable(s) in 2 file(s)` over the two files it
    # had just filled. The comment below says what that costs, and it was already
    # written when this filter reintroduced the cost by another door.
    handled = {str(p.relative_to(root)) for p in target_paths}
    table = {
        k: v for k, v in table.items()
        if not (
            found.get(k)
            and all(
                k in dropped.get(str(p.relative_to(root)), set())
                for p in found[k]
                if str(p.relative_to(root)) in handled
            )
        )
    }

    result.changed_files.sort()
    # `values` is what the operator ANSWERED; this is what reached a file. Three
    # lenses caught the difference independently once the `found` filter was dropped:
    # the CLI counts this field, so recording an answer for a slot the target does not
    # carry made it print `Filled 3 variable(s) in 1 file(s)` — a claim the disk
    # contradicts, which is the exact defect shape this whole epic is auditing.
    result.values = {t: v for t, v in table.items() if found.get(t)}
    result.unfilled = sorted(t for t in found if t not in table)
    # Remember what was answered. Filling the files and recording nothing is what made
    # `configure` freeze a protected file: the next upgrade compared a rendered target
    # against a raw source, called the kit's own substitution operator intent, and kept
    # the file for good. Verified against a real target, not only in unit tests.
    persist_placeholder_values(root, table)
    return result
