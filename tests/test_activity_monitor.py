from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from governancekit.activity_monitor import (
    ActivityMonitorError,
    canonical_log_path,
    canonical_monitor_path,
    default_state_home,
    migrate_activity_log,
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

    def test_canonical_namespace_is_the_contract_one_not_the_tool_one(self) -> None:
        # AGENTS.md §8a owns this path: the file is written by every governed agent
        # tool, so it must not live under the kit's own namespace.
        destination = canonical_monitor_path(state_home=Path("/var/state"))
        self.assertEqual(destination, Path("/var/state/ai-agents/agent-status.json"))

    def test_merges_both_legacy_locations_and_skips_the_missing_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            older = state / "governancekit" / "agent-status.json"
            older.parent.mkdir(parents=True)
            older.write_text(
                json.dumps({"sessions": [{"agent": "codex", "task": "frozen in july"}]}),
                encoding="utf-8",
            )

            # No ~/Sync copy in this fake home: the missing location is skipped, not
            # an error, because a machine may only ever have had one of the two.
            result = migrate_activity_monitor(state_home=state, home=root)

            destination = canonical_monitor_path(state_home=state)
            self.assertEqual(result.sources, (older,))
            self.assertTrue(older.is_file(), "legacy copies are never deleted")
            sessions = json.loads(destination.read_text(encoding="utf-8"))["sessions"]
            self.assertEqual(sessions, [{"agent": "codex", "task": "frozen in july"}])

    def test_log_moves_once_and_then_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            source = root / "Sync" / "agent-log.md"
            source.parent.mkdir()
            source.write_text("# Agent Work Log\n\nhistory\n", encoding="utf-8")

            moved = migrate_activity_log(source=source, state_home=state)

            destination = canonical_log_path(state_home=state)
            self.assertTrue(moved.moved)
            self.assertFalse(source.exists(), "a move, not a copy: no divergent second log")
            self.assertEqual(destination.read_text(encoding="utf-8"), "# Agent Work Log\n\nhistory\n")

            source.write_text("# Agent Work Log\n\nother history\n", encoding="utf-8")
            second = migrate_activity_log(source=source, state_home=state)

            self.assertFalse(second.moved)
            self.assertIn("by hand", second.reason)
            self.assertEqual(destination.read_text(encoding="utf-8"), "# Agent Work Log\n\nhistory\n")

    def test_log_migration_is_silent_when_there_is_nothing_to_move(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = migrate_activity_log(source=root / "absent.md", state_home=root / "state")
            self.assertFalse(result.moved)
            self.assertFalse(canonical_log_path(state_home=root / "state").exists())

    def test_rejects_malformed_monitor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "agent-status.json"
            source.write_text('{"sessions": "wrong"}', encoding="utf-8")

            with self.assertRaises(ActivityMonitorError):
                migrate_activity_monitor(source=source, state_home=Path(temporary) / "state")
