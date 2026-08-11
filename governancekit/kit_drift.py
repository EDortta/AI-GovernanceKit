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
            },
            indent=2,
        ) + "\n"


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
