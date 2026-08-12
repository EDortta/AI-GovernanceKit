"""Drift gate between the two kits.

The two components ship separately and each states things about the other. The
contract in AI-Agents declares which GovernanceKit versions it accepts; this
runtime pins which AI-Agents release it installs; and `AGENTS.md` here carries a
copy of a section whose origin is AI-Agents. Until now the only thing holding
those in agreement was prose asking the next person to change both sides.

Prose does not go red. On 2026-08-11 a version bump here was one step away from
publishing a runtime that every governed project's contract would have rejected,
and the copied section had already drifted once before by translation.

The gate works off a **snapshot**: `_kit_snapshot.json` records what the pinned
AI-Agents release says, and the tests compare this repository against it without
a network. `scripts/refresh-kit-snapshot.py` re-derives the snapshot from the
pinned tarball, so the snapshot cannot quietly disagree with the release it
claims to describe — refreshing it is part of bumping `DEFAULT_REF`.

Every drift direction seen in practice turns a test red:

* pin bumped without refreshing the snapshot  -> ref mismatch
* runtime version leaves the declared range   -> range mismatch
* either copy of the shared section edited    -> digest mismatch
* a seed template missing from the release    -> seed mismatch
* either installer changes which files it protects -> protected-set mismatch
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

_SNAPSHOT_FILE = "_kit_snapshot.json"

# The heading the shared section carries in both kits. In AI-Agents it is a
# section of `.docs/workflows/sending-email.md`; here it is a section of
# `AGENTS.md`. Matching on the heading rather than on a file path is what lets
# one gate compare two different carriers.
_SECTION_HEADING = "Sending Email"

# Everything from this marker on is GovernanceKit's own note about where the
# section came from. It is deliberately *not* part of the canonical body: the
# origin note only makes sense in the copy, and demanding it upstream would be
# the mirror of the defect this gate exists to catch.
_ORIGIN_MARKER = "One origin:"


class SnapshotError(RuntimeError):
    """The snapshot is missing, unreadable, or does not describe what it claims."""


@dataclass(frozen=True)
class KitSnapshot:
    """What the pinned AI-Agents release says, recorded at pin time."""

    agents_ref: str
    governancekit_version_range: str
    shared_section_sha256: str
    # Seed sources `_TEMPLATE_SEEDS` points at, as the release actually carries them.
    # A seed that resolves to nothing is not an error anywhere — `_resolve_src` simply
    # falls back to the source's own file, so the target silently receives the KIT's
    # handoff and reading index instead of an empty template. That is R2-15, and it
    # shipped for three releases because nothing compared the two lists.
    template_seed_sources: tuple[str, ...]
    # Root files the SHELL installer refuses to overwrite once they differ from what
    # it installed. Both kits replace the same files in the same targets, so a file
    # protected by one and replaced by the other is a data-loss path that reads as
    # closed. That was R2-16': the shell has fought for AGENTS.md since 2026-07-23
    # while this runtime kept replacing it with a bare copy.
    protected_root_files: tuple[str, ...]

    @classmethod
    def load(cls, path: Path | None = None) -> "KitSnapshot":
        path = path or Path(__file__).with_name(_SNAPSHOT_FILE)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SnapshotError(
                f"kit snapshot missing at {path} — run scripts/refresh-kit-snapshot.py"
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise SnapshotError(f"kit snapshot unreadable at {path}: {exc}") from exc
        try:
            return cls(
                agents_ref=raw["agents_ref"],
                governancekit_version_range=raw["governancekit_version_range"],
                shared_section_sha256=raw["shared_section_sha256"],
                template_seed_sources=tuple(raw["template_seed_sources"]),
                protected_root_files=tuple(raw["protected_root_files"]),
            )
        except (KeyError, TypeError) as exc:
            raise SnapshotError(f"kit snapshot at {path} is missing {exc}") from exc

    def to_json(self) -> str:
        return json.dumps(
            {
                "_comment": (
                    "Derived from the pinned AI-Agents release by "
                    "scripts/refresh-kit-snapshot.py. Do not hand-edit: the point of "
                    "this file is that it was read off the release, not typed."
                ),
                "agents_ref": self.agents_ref,
                "governancekit_version_range": self.governancekit_version_range,
                "shared_section_sha256": self.shared_section_sha256,
                "template_seed_sources": list(self.template_seed_sources),
                "protected_root_files": list(self.protected_root_files),
            },
            indent=2,
        ) + "\n"


def extract_protected_root_files(text: str) -> tuple[str, ...]:
    """Read ``PROTECTED_ROOT_FILES`` out of the shell installer's source.

    Returns an empty tuple when the assignment is absent, so a release that drops
    the protection fails the comparison instead of erroring out — same reasoning as
    :func:`digest_shared_section` over a deleted section.
    """
    match = re.search(r"^PROTECTED_ROOT_FILES=\((.*?)\)", text, re.MULTILINE | re.DOTALL)
    if not match:
        return ()
    return tuple(re.findall(r'"([^"]+)"', match.group(1)))


def extract_shared_section(text: str) -> str:
    """Return the canonical body of the shared section, or "" when absent.

    The body ends at the first of: a horizontal rule, the next heading, the
    origin note, or end of text. Both carriers are matched by the same rule so
    that "identical" means the same thing on both sides.
    """
    match = re.search(
        rf"^##\s+{re.escape(_SECTION_HEADING)}\s*$(.*?)(?=^---\s*$|^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return ""
    body = re.split(rf"^{re.escape(_ORIGIN_MARKER)}", match.group(1), flags=re.MULTILINE)[0]
    return body.strip()


def digest_shared_section(text: str) -> str:
    """SHA-256 of the canonical body, over an empty string when the section is absent.

    An absent section hashes to the digest of "" rather than raising, so a
    section that gets *deleted* fails the comparison like any other drift
    instead of erroring out in a way a caller might catch and skip.
    """
    return hashlib.sha256(extract_shared_section(text).encode("utf-8")).hexdigest()
