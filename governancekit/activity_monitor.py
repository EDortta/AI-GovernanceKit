"""Migration support for the local agent activity monitor.

The former location, ``~/Sync/agent-status.json``, remains readable by existing
tools. GovernanceKit writes the canonical copy under the XDG state directory and
never removes or rewrites that legacy file during migration.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


LEGACY_SYNC_RELATIVE_PATH = Path("Sync") / "agent-status.json"
MONITOR_RELATIVE_PATH = Path("governancekit") / "agent-status.json"


class ActivityMonitorError(ValueError):
    """The activity-monitor document is missing, unsafe, or malformed."""


@dataclass(frozen=True)
class ActivityMonitorMigration:
    source: Path
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


def migrate_activity_monitor(
    *,
    source: Path | None = None,
    state_home: Path | None = None,
) -> ActivityMonitorMigration:
    """Copy/merge legacy sessions into XDG state without deleting the source.

    A session has no stable ID in the legacy schema, so exact JSON object equality
    is the deduplication key. Existing canonical sessions retain their order;
    previously unseen legacy sessions are appended.
    """
    source = (source or legacy_sync_monitor_path()).expanduser()
    destination = canonical_monitor_path(state_home=state_home).expanduser()
    source_data = _read_monitor(source, required=True)
    destination_data = _read_monitor(destination, required=False)

    merged = dict(destination_data)
    for key, value in source_data.items():
        merged.setdefault(key, value)

    existing_sessions = list(destination_data.get("sessions", []))
    seen = {_session_key(session) for session in existing_sessions}
    imported = 0
    duplicates = 0
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
    return ActivityMonitorMigration(source, destination, imported, duplicates, wrote)


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
