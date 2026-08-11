"""Migration support for the local agent activity monitor.

The registry is machine-local by nature: it says which agents are alive *here*,
and a copy replicated to another machine is worse than no copy — it reports
sessions that were never running on the reader's box. That is why it belongs in
``XDG_STATE_HOME`` (state that survives a restart, is not portable, and is not
grave to lose) and not in a synchronised directory.

The canonical path is ``$XDG_STATE_HOME/ai-agents/agent-status.json``, declared by
``AGENTS.md`` §8a. The namespace is ``ai-agents`` and not ``governancekit`` on
purpose: the file is written by every agent tool the contract governs, and
GovernanceKit is one writer among them, not the owner.

Two earlier locations are read as legacy sources and never deleted or rewritten:
``~/Sync/agent-status.json`` (what agents actually wrote) and
``$XDG_STATE_HOME/governancekit/agent-status.json`` (a first migration that used
the tool's own namespace).
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


LEGACY_SYNC_RELATIVE_PATH = Path("Sync") / "agent-status.json"
LEGACY_STATE_RELATIVE_PATH = Path("governancekit") / "agent-status.json"
MONITOR_RELATIVE_PATH = Path("ai-agents") / "agent-status.json"
MONITOR_LOG_RELATIVE_PATH = Path("ai-agents") / "agent-log.md"
LEGACY_SYNC_LOG_RELATIVE_PATH = Path("Sync") / "agent-log.md"


class ActivityMonitorError(ValueError):
    """The activity-monitor document is missing, unsafe, or malformed."""


@dataclass(frozen=True)
class ActivityMonitorMigration:
    sources: tuple[Path, ...]
    destination: Path
    imported_sessions: int
    duplicate_sessions: int
    wrote_destination: bool


def default_state_home(*, environ: dict[str, str] | None = None, home: Path | None = None) -> Path:
    """Resolve the XDG state directory without creating it."""
    environment = os.environ if environ is None else environ
    if environment.get("XDG_STATE_HOME"):
        return Path(environment["XDG_STATE_HOME"]).expanduser()
    return (home or Path.home()) / ".local" / "state"


def canonical_monitor_path(*, state_home: Path | None = None) -> Path:
    return (state_home or default_state_home()) / MONITOR_RELATIVE_PATH


def legacy_sync_monitor_path(*, home: Path | None = None) -> Path:
    return (home or Path.home()) / LEGACY_SYNC_RELATIVE_PATH


def legacy_monitor_paths(
    *, home: Path | None = None, state_home: Path | None = None
) -> tuple[Path, ...]:
    """Every location a session entry may still be sitting in, oldest first."""
    return (
        legacy_sync_monitor_path(home=home),
        (state_home or default_state_home()) / LEGACY_STATE_RELATIVE_PATH,
    )


def canonical_log_path(*, state_home: Path | None = None) -> Path:
    return (state_home or default_state_home()) / MONITOR_LOG_RELATIVE_PATH


def legacy_sync_log_path(*, home: Path | None = None) -> Path:
    return (home or Path.home()) / LEGACY_SYNC_LOG_RELATIVE_PATH


def migrate_activity_monitor(
    *,
    source: Path | None = None,
    state_home: Path | None = None,
    home: Path | None = None,
) -> ActivityMonitorMigration:
    """Copy/merge legacy sessions into XDG state without deleting any source.

    A session has no stable ID in the legacy schema, so exact JSON object equality
    is the deduplication key. Existing canonical sessions retain their order;
    previously unseen legacy sessions are appended.

    With no explicit ``source``, every known legacy location is merged in turn and
    a missing one is simply skipped — the machine may only ever have had one. An
    explicit ``source`` is required to exist, so a typo fails loudly.
    """
    destination = canonical_monitor_path(state_home=state_home).expanduser()
    if source is None:
        candidates = tuple(
            path.expanduser()
            for path in legacy_monitor_paths(home=home, state_home=state_home)
        )
        required = False
    else:
        candidates = (source.expanduser(),)
        required = True

    destination_data = _read_monitor(destination, required=False)
    merged = dict(destination_data)
    existing_sessions = list(destination_data.get("sessions", []))
    seen = {_session_key(session) for session in existing_sessions}
    imported = 0
    duplicates = 0
    used: list[Path] = []

    for candidate in candidates:
        if candidate == destination:
            continue
        source_data = _read_monitor(candidate, required=required)
        if not source_data:
            continue
        used.append(candidate)
        for key, value in source_data.items():
            merged.setdefault(key, value)
        for session in source_data["sessions"]:
            key = _session_key(session)
            if key in seen:
                duplicates += 1
                continue
            existing_sessions.append(session)
            seen.add(key)
            imported += 1

    merged["sessions"] = existing_sessions

    wrote = not destination.exists() or merged != destination_data
    if wrote:
        _write_monitor(destination, merged)
    return ActivityMonitorMigration(tuple(used), destination, imported, duplicates, wrote)


@dataclass(frozen=True)
class ActivityLogMigration:
    source: Path
    destination: Path
    moved: bool
    reason: str


def migrate_activity_log(
    *,
    source: Path | None = None,
    state_home: Path | None = None,
) -> ActivityLogMigration:
    """Move the append-only work log to XDG state.

    A move, not a merge: the log is append-only prose with no record boundary a
    machine can trust, so two divergent copies cannot be reconciled safely. If a
    canonical log already exists the move is refused and both are left in place
    for a human to reconcile.
    """
    source = (source or legacy_sync_log_path()).expanduser()
    destination = canonical_log_path(state_home=state_home).expanduser()
    if source.is_symlink() or destination.is_symlink():
        raise ActivityMonitorError(f"refusing symlinked activity log: {source} -> {destination}")
    if not source.is_file():
        return ActivityLogMigration(source, destination, False, "no legacy log to move")
    if destination.is_file():
        return ActivityLogMigration(
            source, destination, False,
            "canonical log already exists; reconcile the two by hand",
        )
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        source.replace(destination)
    except OSError:
        # Different filesystems: ~/Sync and ~/.local need not share a mount.
        shutil.move(str(source), str(destination))
    return ActivityLogMigration(source, destination, True, "moved")


def _read_monitor(path: Path, *, required: bool) -> dict[str, object]:
    if path.is_symlink():
        raise ActivityMonitorError(f"refusing symlinked activity monitor: {path}")
    if not path.is_file():
        if required:
            raise ActivityMonitorError(f"activity monitor not found: {path}")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ActivityMonitorError(f"invalid activity monitor {path}: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("sessions"), list):
        raise ActivityMonitorError(f"activity monitor {path} must be an object with a sessions list")
    if not all(isinstance(session, dict) for session in data["sessions"]):
        raise ActivityMonitorError(f"activity monitor {path} sessions must be objects")
    return data


def _session_key(session: object) -> str:
    return json.dumps(session, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_monitor(path: Path, data: dict[str, object]) -> None:
    if path.is_symlink():
        raise ActivityMonitorError(f"refusing symlinked activity monitor destination: {path}")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=".agent-status-", dir=path.parent, text=True)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
        temporary_path.chmod(0o600)
        temporary_path.replace(path)
    except OSError:
        temporary_path.unlink(missing_ok=True)
        raise
