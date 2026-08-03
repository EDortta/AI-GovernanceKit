from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from governancekit.activity_monitor import (
    ActivityMonitorError,
    canonical_monitor_path,
    default_state_home,
    migrate_activity_monitor,
)


class ActivityMonitorMigrationTests(unittest.TestCase):
    def test_uses_xdg_state_home_when_present(self) -> None:
        self.assertEqual(
            default_state_home(environ={"XDG_STATE_HOME": "/var/state"}),
            Path("/var/state"),
        )

    def test_migrates_without_removing_legacy_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "Sync" / "agent-status.json"
            source.parent.mkdir()
            source.write_text(json.dumps({"sessions": [{"agent": "cursor", "task": "review"}]}), encoding="utf-8")

            result = migrate_activity_monitor(source=source, state_home=root / "state")

            destination = canonical_monitor_path(state_home=root / "state")
            self.assertTrue(source.is_file())
            self.assertTrue(destination.is_file())
            self.assertEqual(result.imported_sessions, 1)
            self.assertEqual(json.loads(destination.read_text(encoding="utf-8"))["sessions"], [{"agent": "cursor", "task": "review"}])

    def test_merges_new_sessions_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "Sync" / "agent-status.json"
            source.parent.mkdir()
            source.write_text(json.dumps({"sessions": [{"agent": "cursor", "task": "review"}, {"agent": "codex", "task": "ship"}]}), encoding="utf-8")
            destination = canonical_monitor_path(state_home=root / "state")
            destination.parent.mkdir(parents=True)
            destination.write_text(json.dumps({"sessions": [{"agent": "cursor", "task": "review"}]}), encoding="utf-8")

            first = migrate_activity_monitor(source=source, state_home=root / "state")
            second = migrate_activity_monitor(source=source, state_home=root / "state")

            self.assertEqual(first.imported_sessions, 1)
            self.assertEqual(first.duplicate_sessions, 1)
            self.assertTrue(first.wrote_destination)
            self.assertEqual(second.imported_sessions, 0)
            self.assertFalse(second.wrote_destination)
            self.assertEqual(len(json.loads(destination.read_text(encoding="utf-8"))["sessions"]), 2)

    def test_rejects_malformed_monitor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "agent-status.json"
            source.write_text('{"sessions": "wrong"}', encoding="utf-8")

            with self.assertRaises(ActivityMonitorError):
                migrate_activity_monitor(source=source, state_home=Path(temporary) / "state")
