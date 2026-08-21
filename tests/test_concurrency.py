from __future__ import annotations

import subprocess
from datetime import time
from pathlib import Path

from governancekit import concurrency as cc


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def _repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "development")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    (root / "f.txt").write_text("one\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


def _commit_on(root: Path, branch: str, text: str) -> None:
    _git(root, "checkout", "-q", "-b", branch)
    (root / f"{branch.replace('/', '-')}.txt").write_text(text, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", text)
    _git(root, "checkout", "-q", "development")


# ── the survey ────────────────────────────────────────────────────────────────

def test_a_single_checkout_is_one_front(tmp_path) -> None:
    root = _repo(tmp_path / "solo")

    survey = cc.survey_concurrency(root)

    assert survey.integration_branch == "development"
    assert survey.open_count == 1
    assert survey.beyond_current == 0
    assert survey.items[0].is_current


def test_a_branch_with_unmerged_work_is_a_front(tmp_path) -> None:
    root = _repo(tmp_path / "one")
    _commit_on(root, "feature/uc-001/x", "work")

    survey = cc.survey_concurrency(root)

    assert survey.beyond_current == 1
    branch = survey.unmerged_branches[0]
    assert branch.branch == "feature/uc-001/x"
    assert branch.unmerged == 1
    assert branch.path is None


def test_a_merged_branch_is_not_a_front(tmp_path) -> None:
    # A branch that exists but holds nothing is not work in progress.
    root = _repo(tmp_path / "merged")
    _commit_on(root, "feature/uc-002/y", "work")
    _git(root, "merge", "-q", "--no-ff", "-m", "merge", "feature/uc-002/y")

    survey = cc.survey_concurrency(root)

    assert survey.beyond_current == 0
    assert survey.unmerged_branches == ()


def test_a_worktree_counts_once_not_twice(tmp_path) -> None:
    # The branch has unmerged work AND a worktree. It is one front, not two.
    root = _repo(tmp_path / "wt")
    _commit_on(root, "feature/uc-003/z", "work")
    _git(root, "worktree", "add", "-q", str(tmp_path / "wt-z"), "feature/uc-003/z")

    survey = cc.survey_concurrency(root)

    assert survey.open_count == 2  # development + the worktree
    assert [item.branch for item in survey.worktrees] == ["development", "feature/uc-003/z"]
    assert survey.unmerged_branches == ()


def test_a_worktree_with_nothing_unmerged_is_reported_as_removable(tmp_path) -> None:
    # This is the fact that was missing when a history rewrite was priced for one
    # checkout and then met four.
    root = _repo(tmp_path / "rm")
    _commit_on(root, "feature/uc-004/done", "work")
    _git(root, "merge", "-q", "--no-ff", "-m", "merge", "feature/uc-004/done")
    _git(root, "worktree", "add", "-q", str(tmp_path / "rm-done"), "feature/uc-004/done")

    survey = cc.survey_concurrency(root)

    removable = survey.removable
    assert [item.branch for item in removable] == ["feature/uc-004/done"]
    assert "can be removed" in cc.format_survey(survey)


def test_a_failed_unmerged_read_is_never_reported_as_removable(monkeypatch, tmp_path) -> None:
    # `_unmerged_count` used to fold a failed `git rev-list` into 0, and 0 is exactly
    # `removable`'s trigger — a read failure read as "merged, safe to delete". This
    # pins the fix: failure must surface as unknown, never as a confident zero.
    root = _repo(tmp_path / "unknown")
    _commit_on(root, "feature/uc-006/w", "work")
    _git(root, "worktree", "add", "-q", str(tmp_path / "wt-w"), "feature/uc-006/w")

    real_git = cc._git

    def _flaky(path: Path, *args: str) -> str | None:
        if args[:2] == ("rev-list", "--count"):
            return None
        return real_git(path, *args)

    monkeypatch.setattr(cc, "_git", _flaky)

    survey = cc.survey_concurrency(root)

    target = next(item for item in survey.items if item.branch == "feature/uc-006/w")
    assert target.unmerged is None
    assert target.removable is False
    assert target not in survey.removable
    rendered = cc.format_survey(survey)
    assert "unmerged count unknown" in rendered
    assert "can be removed" not in rendered


def test_the_current_checkout_is_never_reported_as_removable(tmp_path) -> None:
    root = _repo(tmp_path / "self")

    survey = cc.survey_concurrency(root)

    assert survey.removable == ()


def test_a_directory_without_git_never_breaks_the_session(tmp_path) -> None:
    survey = cc.survey_concurrency(tmp_path / "plain")

    assert not survey.available
    assert survey.open_count == 0
    assert cc.format_survey(survey) == ""


def test_main_falls_back_when_there_is_no_development_branch(tmp_path) -> None:
    root = tmp_path / "onmain"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    (root / "f.txt").write_text("x\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")

    assert cc.survey_concurrency(root).integration_branch == "main"


# ── phrasing ──────────────────────────────────────────────────────────────────

def test_start_asks_for_authorization_and_close_asks_for_the_handoff(tmp_path) -> None:
    root = _repo(tmp_path / "phrase")
    _commit_on(root, "feature/uc-005/w", "work")
    survey = cc.survey_concurrency(root)

    assert "requires the operator's authorization" in cc.format_survey(survey, moment="start")
    assert "stay open for the next day" in cc.format_survey(survey, moment="close")


def test_nothing_else_open_says_so_plainly(tmp_path) -> None:
    survey = cc.survey_concurrency(_repo(tmp_path / "quiet"))

    assert "Nothing else is open." in cc.format_survey(survey)
    assert "Nothing stays open" in cc.format_survey(survey, moment="close")


# ── the wind-down clock (AGENTS.md §8c) ───────────────────────────────────────

def test_before_the_hour_is_normal() -> None:
    state = cc.winddown_state(time(14, 0))

    assert state.phase == "normal"
    assert state.runway_minutes == 240  # until 18:00


def test_after_the_hour_is_winddown_with_the_runway_left() -> None:
    state = cc.winddown_state(time(17, 10))

    assert state.phase == "winddown"
    assert state.runway_minutes == 50
    assert "50 min until the hard stop" in cc.format_winddown(state)


def test_past_the_budget_is_a_hard_stop() -> None:
    state = cc.winddown_state(time(18, 5))

    assert state.phase == "hard-stop"
    assert state.runway_minutes == 0
    assert "Start no new work" in cc.format_winddown(state)


def test_the_operator_can_move_the_hour_and_the_budget() -> None:
    state = cc.winddown_state(time(15, 10), hour=15, budget_minutes=30)

    assert state.phase == "winddown"
    assert state.runway_minutes == 20
    # The hard stop is inclusive: at winddown_hour + budget the runway is spent.
    assert cc.winddown_state(time(15, 30), hour=15, budget_minutes=30).phase == "hard-stop"
