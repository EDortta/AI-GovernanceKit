"""How much is open at once in this repository, and how much runway is left today.

Two facts an operator should never have to discover mid-operation:

*How many working fronts exist.* A checkout that looks single can be one of several
worktrees over the same ``.git``, each on its own branch. An operation priced for one
repository — a history rewrite, a branch cleanup — is priced wrong the moment there
are four. The survey below answers that before the work starts, not during it.

*How much of the day is left.* ``AGENTS.md`` §8c defines a wind-down hour and a
closing budget precisely because closing several parallel sessions takes about an
hour, and reaching end-of-day without warning leaves them dirty. Agents have no
continuous clock, so the contract asks them to read the time per response; this
module turns that reading into a phase and a runway.

Nothing here ever fails a session: a directory that is not a git repository, or a git
that cannot be run at all, yields an empty survey the caller can silently skip.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import time as _time
from pathlib import Path

# The branch work is expected to land on. First one that exists wins.
_INTEGRATION_CANDIDATES = ("development", "main", "master")

# AGENTS.md §8c defaults.
DEFAULT_WINDDOWN_HOUR = 17
DEFAULT_CLOSE_BUDGET_MINUTES = 60


def _git(root: Path, *args: str) -> str | None:
    """Run a read-only git command, or return None when git cannot answer."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout


@dataclass(frozen=True)
class OpenItem:
    """One working front: a live worktree, or a branch holding unmerged work."""

    kind: str  # "worktree" | "branch"
    branch: str
    path: str | None
    unmerged: int
    is_current: bool = False
    prunable: bool = False

    @property
    def removable(self) -> bool:
        """A worktree whose branch holds nothing the integration branch lacks.

        The single most actionable line in the report: it can be removed today
        without losing a commit.
        """
        return self.kind == "worktree" and self.unmerged == 0 and not self.is_current

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "branch": self.branch,
            "path": self.path,
            "unmerged": self.unmerged,
            "is_current": self.is_current,
            "prunable": self.prunable,
            "removable": self.removable,
        }


@dataclass(frozen=True)
class ConcurrencySurvey:
    root: Path
    integration_branch: str
    items: tuple[OpenItem, ...]
    available: bool = True

    @property
    def open_count(self) -> int:
        return len(self.items)

    @property
    def beyond_current(self) -> int:
        """How many fronts exist besides the one this session is sitting on."""
        return max(0, self.open_count - sum(1 for item in self.items if item.is_current))

    @property
    def worktrees(self) -> tuple[OpenItem, ...]:
        return tuple(item for item in self.items if item.kind == "worktree")

    @property
    def unmerged_branches(self) -> tuple[OpenItem, ...]:
        return tuple(item for item in self.items if item.kind == "branch")

    @property
    def removable(self) -> tuple[OpenItem, ...]:
        return tuple(item for item in self.items if item.removable)

    def as_dict(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "available": self.available,
            "integration_branch": self.integration_branch,
            "open_count": self.open_count,
            "beyond_current": self.beyond_current,
            "items": [item.as_dict() for item in self.items],
        }


def _integration_branch(root: Path) -> str:
    for candidate in _INTEGRATION_CANDIDATES:
        if _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{candidate}") is not None:
            return candidate
    return ""


def _unmerged_count(root: Path, branch: str, integration: str) -> int:
    if not integration or branch == integration:
        return 0
    out = _git(root, "rev-list", "--count", f"{integration}..{branch}")
    if out is None:
        return 0
    try:
        return int(out.strip())
    except ValueError:
        return 0


def _parse_worktrees(porcelain: str) -> list[dict[str, str | bool]]:
    """Parse ``git worktree list --porcelain`` into one record per worktree."""
    records: list[dict[str, str | bool]] = []
    current: dict[str, str | bool] = {}
    for line in porcelain.splitlines():
        if not line.strip():
            if current:
                records.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            if current:
                records.append(current)
            current = {"path": value, "branch": "", "detached": False, "prunable": False}
        elif key == "branch":
            current["branch"] = value.removeprefix("refs/heads/")
        elif key in {"detached", "prunable", "locked"}:
            current[key if key != "locked" else "prunable"] = True
    if current:
        records.append(current)
    return records


def survey_concurrency(root: Path) -> ConcurrencySurvey:
    """Enumerate the working fronts open in *root*'s repository.

    A front is a live worktree, or a local branch carrying commits the integration
    branch does not have. A branch that has a worktree is reported once, as the
    worktree: it is one front, not two.
    """
    root = root.resolve()
    porcelain = _git(root, "worktree", "list", "--porcelain")
    if porcelain is None:
        return ConcurrencySurvey(root, "", (), available=False)

    integration = _integration_branch(root)
    records = _parse_worktrees(porcelain)
    # git lists the main worktree first; showing every path relative to its parent is
    # how the operator sees them side by side in the filesystem.
    base = Path(str(records[0]["path"])).parent if records else root

    items: list[OpenItem] = []
    seen_branches: set[str] = set()
    for record in records:
        path = str(record.get("path") or "")
        branch = str(record.get("branch") or "")
        if branch:
            seen_branches.add(branch)
        items.append(
            OpenItem(
                kind="worktree",
                branch=branch or "(detached)",
                path=_relative(path, base),
                unmerged=_unmerged_count(root, branch, integration) if branch else 0,
                is_current=Path(path).resolve() == root,
                prunable=bool(record.get("prunable")),
            )
        )

    refs = _git(root, "for-each-ref", "--format=%(refname:short)", "refs/heads") or ""
    for branch in (line.strip() for line in refs.splitlines()):
        if not branch or branch in seen_branches or branch == integration:
            continue
        unmerged = _unmerged_count(root, branch, integration)
        if unmerged:
            items.append(
                OpenItem(kind="branch", branch=branch, path=None, unmerged=unmerged)
            )

    items.sort(key=lambda item: (item.kind != "worktree", not item.is_current, item.branch))
    return ConcurrencySurvey(root, integration, tuple(items))


def _relative(path: str, base: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(base.resolve()))
    except ValueError:
        return path


# ── wind-down clock (AGENTS.md §8c) ────────────────────────────────────────────

@dataclass(frozen=True)
class WinddownState:
    phase: str  # "normal" | "winddown" | "hard-stop"
    winddown_hour: int
    budget_minutes: int
    runway_minutes: int  # minutes until the hard stop; 0 once past it

    def as_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "winddown_hour": self.winddown_hour,
            "budget_minutes": self.budget_minutes,
            "runway_minutes": self.runway_minutes,
        }


def winddown_state(
    now: _time,
    *,
    hour: int = DEFAULT_WINDDOWN_HOUR,
    budget_minutes: int = DEFAULT_CLOSE_BUDGET_MINUTES,
) -> WinddownState:
    """Classify the moment against the wind-down hour and the closing budget.

    ``now`` is a parameter so the phase is a pure function of the clock the caller
    read — the contract already asks the agent to read the wall clock per response,
    and a hidden ``datetime.now()`` would make this untestable.
    """
    minutes_now = now.hour * 60 + now.minute
    winddown_at = hour * 60
    hard_stop_at = winddown_at + budget_minutes
    if minutes_now >= hard_stop_at:
        return WinddownState("hard-stop", hour, budget_minutes, 0)
    if minutes_now >= winddown_at:
        return WinddownState("winddown", hour, budget_minutes, hard_stop_at - minutes_now)
    return WinddownState("normal", hour, budget_minutes, hard_stop_at - minutes_now)


def load_winddown_config(root: Path) -> tuple[int, int]:
    """Read the operator's wind-down settings, falling back to the §8c defaults."""
    from .identity import load_identity

    identity = load_identity(root)
    raw = getattr(identity, "extra", None) or {}
    hour = _as_hour(raw.get("session_winddown_hour"), DEFAULT_WINDDOWN_HOUR)
    budget = _as_minutes(raw.get("session_close_budget"), DEFAULT_CLOSE_BUDGET_MINUTES)
    return hour, budget


def _as_hour(value: object, default: int) -> int:
    text = str(value or "").strip()
    if not text:
        return default
    head = text.split(":", 1)[0]
    return int(head) if head.isdigit() and 0 <= int(head) <= 23 else default


def _as_minutes(value: object, default: int) -> int:
    text = str(value or "").strip().lower().removesuffix("min").strip()
    return int(text) if text.isdigit() and int(text) > 0 else default


# ── rendering ─────────────────────────────────────────────────────────────────

def format_survey(survey: ConcurrencySurvey, *, moment: str = "start") -> str:
    """Render the survey. The table is the same; the closing sentence is not."""
    if not survey.available:
        return ""
    integration = survey.integration_branch or "(none)"
    lines = [
        f"Open in this repository (integration branch: {integration})",
        f"  worktrees: {len(survey.worktrees)}"
        f"    branches carrying unmerged work: {len(survey.unmerged_branches)}",
        "",
    ]
    where_width = max((len(item.path or "(no worktree)") for item in survey.items), default=0)
    branch_width = max((len(item.branch) for item in survey.items), default=0)
    for item in survey.items:
        marker = "*" if item.is_current else " "
        where = item.path or "(no worktree)"
        note = ""
        if item.is_current:
            note = "this session"
        elif item.removable:
            note = "merged — this worktree can be removed"
        elif item.unmerged:
            note = f"+{item.unmerged} commit{'s' if item.unmerged > 1 else ''}"
        lines.append(f"  {marker} {where:<{where_width}}  {item.branch:<{branch_width}}  {note}".rstrip())

    lines.append("")
    if moment == "close":
        if survey.beyond_current:
            lines.append(
                f"  {survey.beyond_current} of these stay open for the next day. "
                "Say what each one holds in the handoff."
            )
        else:
            lines.append("  Nothing stays open beyond this session.")
    elif survey.beyond_current:
        lines.append(
            f"  {survey.beyond_current} open beyond this session. Working on another one "
            "requires the operator's authorization."
        )
    else:
        lines.append("  Nothing else is open.")

    if survey.removable:
        names = ", ".join(item.path or item.branch for item in survey.removable)
        lines.append(f"  Removable now (nothing unmerged): {names}")
    return "\n".join(lines)


def format_winddown(state: WinddownState) -> str:
    if state.phase == "normal":
        return (
            f"Wind-down at {state.winddown_hour:02d}:00 "
            f"({state.runway_minutes} min of runway left today)."
        )
    if state.phase == "winddown":
        return (
            f"WIND-DOWN: past {state.winddown_hour:02d}:00 — {state.runway_minutes} min "
            "until the hard stop. Prioritize session-close over new work."
        )
    return (
        "HARD STOP: the closing budget is spent. Start no new work — drive "
        "handoff / RESUME / napkin to completion."
    )
