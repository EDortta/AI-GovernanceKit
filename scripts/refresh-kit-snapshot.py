#!/usr/bin/env python3
"""Re-derive `governancekit/_kit_snapshot.json` from the pinned AI-Agents release.

Run this when `DEFAULT_REF` moves. It downloads the pinned tarball, verifies it
against `KNOWN_TARBALL_SHA256` before reading a byte of its content, and records
what that release says about GovernanceKit.

The download is the point. A snapshot typed by hand is a second place to be
wrong; a snapshot read off a checksum-verified release is a fact. The offline
tests then compare this repository against the snapshot, so the gate itself
never needs the network.

    python3 scripts/refresh-kit-snapshot.py            # refresh from DEFAULT_REF
    python3 scripts/refresh-kit-snapshot.py --check    # verify, write nothing

`--check` exits non-zero when the stored snapshot disagrees with the release, so
a release runner can prove the snapshot is current without trusting that whoever
bumped the pin remembered to refresh it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from governancekit.install_agents import DEFAULT_REF, KNOWN_TARBALL_SHA256, REPO
from governancekit.kit_drift import KitSnapshot, digest_shared_section

# The canonical carrier of the shared section inside the AI-Agents release. The
# section lives here, not in that repo's AGENTS.md, which is why the gate cannot
# just diff two files with the same name.
_SHARED_SECTION_SOURCE = ".docs/workflows/sending-email.md"
_CONTRACT_SOURCE = ".docs/governancekit-integration.json"


def _download_verified(repo: str, ref: str, dest: Path) -> Path:
    expected = KNOWN_TARBALL_SHA256.get((repo, ref))
    if expected is None:
        raise SystemExit(
            f"ERROR: no pinned checksum for ({repo}, {ref}). Add it to "
            "KNOWN_TARBALL_SHA256 before refreshing the snapshot — refreshing from "
            "an unverified download would launder an unknown tarball into a gate."
        )
    url = f"https://codeload.github.com/{repo}/tar.gz/{ref}"
    tarball = dest / "agents.tar.gz"
    with urllib.request.urlopen(url) as response:  # noqa: S310 - fixed codeload host
        tarball.write_bytes(response.read())
    actual = hashlib.sha256(tarball.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(
            f"ERROR: checksum mismatch for {repo}@{ref}\n  expected {expected}\n  got      {actual}"
        )
    return tarball


def _member(tar: tarfile.TarFile, suffix: str) -> str:
    """Read one path from the archive, ignoring its top-level directory name."""
    for name in tar.getnames():
        if name.split("/", 1)[-1] == suffix:
            handle = tar.extractfile(name)
            if handle is None:
                break
            return handle.read().decode("utf-8")
    raise SystemExit(f"ERROR: {suffix} not found in the {DEFAULT_REF} tarball")


def build_snapshot() -> KitSnapshot:
    with tempfile.TemporaryDirectory() as tmp:
        tarball = _download_verified(REPO, DEFAULT_REF, Path(tmp))
        with tarfile.open(tarball, "r:gz") as tar:
            contract = json.loads(_member(tar, _CONTRACT_SOURCE))
            section = _member(tar, _SHARED_SECTION_SOURCE)
    return KitSnapshot(
        agents_ref=contract["ai_agents"]["ref"],
        governancekit_version_range=contract["governancekit"]["version_range"],
        shared_section_sha256=digest_shared_section(section),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the stored snapshot against the release; write nothing",
    )
    args = parser.parse_args()

    fresh = build_snapshot()
    target = Path(__file__).resolve().parent.parent / "governancekit" / "_kit_snapshot.json"

    if fresh.agents_ref != DEFAULT_REF:
        print(
            f"ERROR: {DEFAULT_REF} ships a contract that calls itself "
            f"{fresh.agents_ref!r} — the release disagrees with its own tag.",
            file=sys.stderr,
        )
        return 2

    if args.check:
        try:
            stored = KitSnapshot.load(target)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if stored != fresh:
            print("ERROR: stored snapshot disagrees with the pinned release", file=sys.stderr)
            print(f"  stored: {stored}", file=sys.stderr)
            print(f"  release: {fresh}", file=sys.stderr)
            return 1
        print(f"snapshot is current for {DEFAULT_REF}")
        return 0

    target.write_text(fresh.to_json(), encoding="utf-8")
    print(f"snapshot refreshed from {REPO}@{DEFAULT_REF}")
    print(f"  range:  {fresh.governancekit_version_range}")
    print(f"  digest: {fresh.shared_section_sha256[:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
