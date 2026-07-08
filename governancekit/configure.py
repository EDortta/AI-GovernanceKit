from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from .codemap import SKIP_DIRS
from .identity import (
    ALL_FIELDS,
    REQUIRED_FIELDS,
    _FIELD_DESCRIPTIONS,
    Identity,
    identity_from_values,
    load_identity,
    save_identity,
)
from .install_agents import _PLACEHOLDER_DESCRIPTIONS, _PLACEHOLDER_RE

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
_KNOWN_TOKENS: frozenset[str] = frozenset(_PLACEHOLDER_DESCRIPTIONS)


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
            raise ValueError(f"invalid --set value (expected KEY=VALUE): {raw!r}")
        key, val = raw.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid --set value (empty key): {raw!r}")
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
    values: dict[str, str] = {}
    for f in ALL_FIELDS:
        if f in preset:
            values[f] = str(preset[f]).strip()
        elif existing is not None:
            cur = getattr(existing, f)
            values[f] = ",".join(cur) if isinstance(cur, list) else str(cur)
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
    """Map each known placeholder token to the files that still contain it."""
    found: dict[str, list[Path]] = {}
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if not path.is_file() or not _is_text_file(path):
            continue
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
    """Fill kit placeholder variables across all text files under *root*.

    ``preset`` supplies non-interactive ``KEY=VALUE`` answers. Remaining tokens are
    prompted for when a TTY is available (override with ``interactive``).
    """
    root = root.resolve()
    preset = dict(preset or {})
    found = _scan(root)
    result = ConfigureResult(root=root, found_tokens=sorted(found))

    if not found:
        return result

    if interactive is None:
        interactive = sys.stdin.isatty()

    values: dict[str, str] = {t: v for t, v in preset.items() if t in found}

    to_prompt = [t for t in sorted(found) if t not in values]
    if to_prompt and interactive:
        print("\n── Configure kit variables ────────────────────────────────────────")
        print("Press Enter to leave a value unchanged.\n")
        for token in to_prompt:
            desc = _PLACEHOLDER_DESCRIPTIONS.get(token, "")
            prompt = f"  [{token}]" + (f"  ({desc})" if desc else "") + ": "
            try:
                answer = input(prompt).strip()
            except EOFError:
                answer = ""
            if answer:
                values[token] = answer

    result.values = values
    result.unfilled = sorted(t for t in found if t not in values)

    if not values:
        return result

    # Apply every substitution to every file that holds at least one filled token.
    target_paths: set[Path] = set()
    for token in values:
        target_paths.update(found.get(token, []))

    for path in sorted(target_paths):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        new_text = text
        for token, val in values.items():
            new_text = new_text.replace(f"[{token}]", val)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            result.changed_files.append(str(path.relative_to(root)))

    result.changed_files.sort()
    return result
