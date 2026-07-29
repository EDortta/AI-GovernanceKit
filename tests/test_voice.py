from __future__ import annotations

from pathlib import Path

from governancekit.voice import detect_voice_integration


def test_voice_detection_reports_absent_by_default(tmp_path: Path) -> None:
    status = detect_voice_integration(tmp_path)
    assert status.status == "absent"
    assert status.command is None


def test_voice_detection_uses_env_override(tmp_path: Path, monkeypatch) -> None:
    fake_bin = tmp_path / "ai-listentomeoncli"
    fake_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_bin.chmod(0o755)
    monkeypatch.setenv("AI_LISTENTOMEONCLI_BIN", str(fake_bin))

    status = detect_voice_integration(tmp_path)

    assert status.status == "available"
    assert status.command == str(fake_bin)
