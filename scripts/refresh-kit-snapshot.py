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

from governancekit.install_agents import (
    DEFAULT_REF,
    KNOWN_TARBALL_SHA256,
    REPO,
    _TEMPLATE_SEEDS,
)
from governancekit.kit_drift import (
    SnapshotError,
    KitSnapshot,
    digest_shared_section,
    extract_protected_root_files,
)

# The canonical carrier of the shared section inside the AI-Agents release. The
# section lives here, not in that repo's AGENTS.md, which is why the gate cannot
# just diff two files with the same name.
_SHARED_SECTION_SOURCE = ".docs/workflows/sending-email.md"
_CONTRACT_SOURCE = ".docs/governancekit-integration.json"
# The other implementation of the same upgrade contract. It is the copy that gets
# deposited into every target, so what it protects is what a governed project is
# entitled to expect from an upgrade — whichever installer runs it.
_SHELL_INSTALLER_SOURCE = "scripts/install-agents-kit.sh"


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


def _credential_digests(tar: tarfile.TarFile) -> dict[str, str]:
    """sha256 of every regular file the release ships under `.credentials/`.

    Read off the verified tarball, never typed. The list it replaces was eight names
    written by hand in `remove_agents.py`, which had to agree with the release and was
    compared to it by nothing — and the digests it adds are the evidence the planner
    was already claiming to have.
    """
    prefix = ".credentials/"
    digests: dict[str, str] = {}
    for name in tar.getnames():
        rel = name.split("/", 1)[-1]
        if not rel.startswith(prefix) or rel.count("/") != 1:
            continue
        member = tar.getmember(name)
        if not member.isfile():
            continue
        handle = tar.extractfile(name)
        if handle is None:
            continue
        digests[rel[len(prefix):]] = hashlib.sha256(handle.read()).hexdigest()
    if not digests:
        raise SystemExit(f"ERROR: no .credentials/ files in the {DEFAULT_REF} tarball")
    return digests


def _credential_history() -> dict[str, tuple[str, ...]]:
    """Digests of `.credentials/` across EVERY release this kit has a checksum for.

    A target keeps the bytes it was seeded with for ever: the installer never replaces
    an existing file in that directory and the upgrade branch never seeds at all. So a
    project adopted two releases ago still holds those bytes, and a table built from
    only the pinned release told that population its own kit files were unknown — after
    which de-adoption left them on disk, which is the symptom the table exists to
    remove. A council measured it against `identity.json.example`, which changed on
    2026-08-10.

    Derived across the whole history rather than typed, and every ref is checksum-
    verified by `_download_verified` exactly as the pinned one is: `KNOWN_TARBALL_SHA256`
    is the list of releases this kit will install, so it is also the list of releases
    whose bytes a target can be carrying. Newest first.
    """
    refs = [ref for (repo, ref) in KNOWN_TARBALL_SHA256 if repo == REPO]
    refs.sort(key=lambda r: [int(p) for p in r.lstrip("v").split(".")], reverse=True)
    history: dict[str, list[str]] = {}
    for ref in refs:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                tarball = _download_verified(REPO, ref, Path(tmp))
            except SystemExit:
                raise
            except Exception as exc:  # a withdrawn tag is not a reason to fail
                print(f"  {ref}: skipped ({type(exc).__name__})")
                continue
            with tarfile.open(tarball, "r:gz") as tar:
                for name, digest in _credential_digests(tar).items():
                    seen = history.setdefault(name, [])
                    if digest not in seen:
                        seen.append(digest)
    if not history:
        raise SystemExit("ERROR: no .credentials/ digests could be derived")
    return {name: tuple(digests) for name, digests in history.items()}


def build_snapshot() -> KitSnapshot:
    with tempfile.TemporaryDirectory() as tmp:
        tarball = _download_verified(REPO, DEFAULT_REF, Path(tmp))
        with tarfile.open(tarball, "r:gz") as tar:
            contract = json.loads(_member(tar, _CONTRACT_SOURCE))
            section = _member(tar, _SHARED_SECTION_SOURCE)
            installer = _member(tar, _SHELL_INSTALLER_SOURCE)
            carried = {name.split("/", 1)[-1] for name in tar.getnames()}
    seeded = _credential_history()
    return KitSnapshot(
        agents_ref=contract["ai_agents"]["ref"],
        governancekit_version_range=contract["governancekit"]["version_range"],
        shared_section_sha256=digest_shared_section(section),
        template_seed_sources=tuple(
            sorted(src for src in set(_TEMPLATE_SEEDS.values()) if src in carried)
        ),
        protected_root_files=extract_protected_root_files(installer),
        seeded_credentials=seeded,
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
        # Compared as SETS per name, not as ordered tuples. `_credential_history`
        # skips a ref it cannot fetch, so a withdrawn tag or a network hiccup on an
        # OLD release would make `fresh` lose digests the stored table has — and the
        # gate would report drift, blaming the release for a problem in the wire.
        # Losing history is not drift: the stored table is the accumulated record.
        def _comparable(snapshot: KitSnapshot) -> tuple:
            return (
                snapshot.agents_ref,
                snapshot.governancekit_version_range,
                snapshot.shared_section_sha256,
                tuple(sorted(snapshot.template_seed_sources)),
                tuple(sorted(snapshot.protected_root_files)),
                tuple(sorted(
                    (name, frozenset(digests))
                    for name, digests in snapshot.seeded_credentials.items()
                )),
            )

        missing = {
            name: sorted(set(fresh.seeded_credentials.get(name, ())) - set(digests))
            for name, digests in stored.seeded_credentials.items()
        }
        if any(missing.values()):
            print(
                "ERROR: the release carries credential digests the stored snapshot "
                "does not — refresh it", file=sys.stderr,
            )
            return 1
        if _comparable(stored) != _comparable(fresh):
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
