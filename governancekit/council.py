"""The commit-time gate for ``.docs/agents/council.md``.

That contract describes an adversarial review of already-approved work, lists five
mandatory triggers in its §4, and then says of itself:

    a council that nothing convenes is decoration. Nothing in this file convenes it.

Five weeks and zero rounds later, it was right. This module is what convenes it.

The gate sits at the **delivery commit** — the commit that closes the work and
precedes handing back to the operator. Not at push: push may never happen, may
happen weeks later, and ``hooks.py`` has no pre-push to hang anything on. The
delivery commit always happens and is the agent's own act, one moment after
``reviewer.md`` returned non-BLOCKER, which is the ordering §4 requires.

Nothing here decides anything about the code. It answers one question — *did a
council run against **this** diff?* — and lets the existing ``doctor`` →
``pre-commit`` path act on the answer.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

# council.md §4: two rounds, then the operator. Mirrors governance-precedence.md,
# which escalates to a human on round 2 rather than orbiting a finding forever.
MAX_ROUNDS = 2

# council.md §3, the three default lenses. Each one is a regression this ecosystem
# actually had; see that file's Provenance.
DEFAULT_LENSES: tuple[str, ...] = (
    "sweep skeptic",
    "claim auditor",
    "second caller",
)

_RECORD_DIR = Path(".gk") / "council"

# A staged path under any of these changes a contract other repositories inherit —
# council.md §4's "blast radius greater than one repo". The most reliable of the
# five triggers to detect, and the one with the most to lose.
_SHARED_CONTRACT_PREFIXES: tuple[str, ...] = (".docs/", "templates/")
_SHARED_CONTRACT_FILES: frozenset[str] = frozenset({"AGENTS.md"})

# Where a delivery states what it did and did not validate.
_DELIVERY_DOCS: tuple[str, ...] = ("handoff.md", "docs/napkin-lessons.md")

# Anchored to the start of a line — after list markers and quoting, but not after
# arbitrary prose. A plain substring matched the sentence that *explains* the
# marker ("caso contrário escrever `not validated: <o quê>`"), so every delivery
# whose notes discussed the convention convened a council. Same failure the
# readiness flag had, where the template's own prose satisfied the check it
# described; both are documentation about a pattern being read as the pattern.
_NOT_VALIDATED_RE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+|>[ \t]*)*[`\"']?not validated:",
    re.IGNORECASE | re.MULTILINE,
)

# council.md §4's "mechanical sweep" is a shape, not a path, so it can only ever be
# guessed at. This threshold is the guess; the report always says so.
_SWEEP_FILE_THRESHOLD = 12


class CouncilError(RuntimeError):
    """The council record is missing, unreadable, or malformed."""


@dataclass(frozen=True)
class Trigger:
    name: str
    reason: str
    # True when the detection is a heuristic rather than a fact about the diff.
    # Printed as such: a guess presented as a certainty is the claim auditor's lens
    # turned on this module.
    heuristic: bool = False


@dataclass(frozen=True)
class Finding:
    """One surviving finding, in the four parts council.md §2 requires."""

    lens: str
    trigger: str          # the input, state or sequence
    wrong_outcome: str    # what the operator or next reader would actually see
    location: str         # file:line, or the rule it violates
    evidence: str         # failing test, reproduction, or "not reproduced: ..."
    closure: str = ""     # test that fails without the fix, or written risk acceptance

    @property
    def closed(self) -> bool:
        return bool(self.closure.strip())

    def as_dict(self) -> dict[str, str]:
        return {
            "lens": self.lens,
            "trigger": self.trigger,
            "wrong_outcome": self.wrong_outcome,
            "location": self.location,
            "evidence": self.evidence,
            "closure": self.closure,
        }


@dataclass(frozen=True)
class Waiver:
    reason: str
    recorded_at: str

    def as_dict(self) -> dict[str, str]:
        return {"reason": self.reason, "recorded_at": self.recorded_at}


@dataclass(frozen=True)
class CouncilRecord:
    fingerprint: str
    round: int
    triggers: tuple[str, ...] = ()
    lenses: tuple[str, ...] = ()
    findings: tuple[Finding, ...] = ()
    # council.md §2: a finding without evidence is not a finding, it is a question.
    # Questions do not block, but they are written down — a question that keeps
    # coming back across rounds is how the next council gets its lens.
    questions: tuple[str, ...] = ()
    waiver: Waiver | None = None
    recorded_at: str = ""

    @property
    def open_findings(self) -> tuple[Finding, ...]:
        return tuple(finding for finding in self.findings if not finding.closed)

    def as_dict(self) -> dict[str, object]:
        return {
            "fingerprint": self.fingerprint,
            "round": self.round,
            "triggers": list(self.triggers),
            "lenses": list(self.lenses),
            "findings": [finding.as_dict() for finding in self.findings],
            "questions": list(self.questions),
            "waiver": self.waiver.as_dict() if self.waiver else None,
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True)
class GateResult:
    """What the gate concluded, in a shape both ``doctor`` and the CLI can print."""

    state: str          # see the constants below
    message: str
    triggers: tuple[Trigger, ...] = ()
    record: CouncilRecord | None = None
    fingerprint: str | None = None

    @property
    def blocks(self) -> bool:
        return self.state in {NO_RECORD, STALE_RECORD, OPEN_FINDINGS, ROUNDS_EXHAUSTED}


NOT_A_REPO = "not-a-repo"
NOTHING_STAGED = "nothing-staged"
NO_TRIGGER = "no-trigger"
NOT_SELECTABLE = "not-selectable"
SATISFIED = "satisfied"
WAIVED = "waived"
NO_RECORD = "no-record"
STALE_RECORD = "stale-record"
OPEN_FINDINGS = "open-findings"
ROUNDS_EXHAUSTED = "rounds-exhausted"


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


def staged_fingerprint(root: Path) -> str | None:
    """A stable digest of what is staged right now, or None when nothing is.

    The record is bound to this value, so a council from yesterday cannot clear
    today's commit, and amending a single file invalidates the round that approved
    the previous content. That binding is the whole point: an unbound record would
    make the gate a one-time formality.
    """
    diff = _git(root, "diff", "--cached")
    if diff is None or not diff.strip():
        return None
    return hashlib.sha256(diff.encode("utf-8", errors="replace")).hexdigest()


def staged_paths(root: Path) -> tuple[str, ...]:
    listing = _git(root, "diff", "--cached", "--name-only")
    if listing is None:
        return ()
    return tuple(line.strip() for line in listing.splitlines() if line.strip())


def _staged_content(root: Path, relative_path: str) -> str:
    blob = _git(root, "show", f":{relative_path}")
    return blob or ""


def detect_triggers(root: Path, *, operator_requested: bool = False) -> tuple[Trigger, ...]:
    """Which of council.md §4's triggers this staged diff hits.

    Only what a staged diff can actually answer. §4's "release/tag that changes a
    gate" is a tag operation and never reaches a pre-commit hook; it is named in
    the CLI output as out of reach rather than silently dropped, because a gate
    that hides its own blind spot is worse than one that has none.
    """
    triggers: list[Trigger] = []
    paths = staged_paths(root)

    shared = [
        path for path in paths
        if path in _SHARED_CONTRACT_FILES
        or any(path.startswith(prefix) for prefix in _SHARED_CONTRACT_PREFIXES)
    ]
    if shared:
        shown = ", ".join(sorted(shared)[:3])
        more = f" (+{len(shared) - 3} more)" if len(shared) > 3 else ""
        triggers.append(Trigger(
            "shared-contract",
            f"changes a contract other repositories inherit: {shown}{more}",
        ))

    for doc in _DELIVERY_DOCS:
        if doc in paths and _NOT_VALIDATED_RE.search(_staged_content(root, doc)):
            triggers.append(Trigger(
                "not-validated",
                f"the delivery in {doc} still carries a `not validated:` claim",
            ))
            break

    if len(paths) >= _SWEEP_FILE_THRESHOLD:
        triggers.append(Trigger(
            "mechanical-sweep",
            f"{len(paths)} files staged at once, the shape of a sweep",
            heuristic=True,
        ))

    if operator_requested:
        triggers.append(Trigger("operator", "the operator asked for a council"))

    return tuple(triggers)


def record_path(root: Path, fingerprint: str) -> Path:
    return root / _RECORD_DIR / f"{fingerprint}.json"


def read_record(root: Path, fingerprint: str) -> CouncilRecord | None:
    path = record_path(root, fingerprint)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CouncilError(f"unreadable council record {path}: {error}") from error
    if not isinstance(data, dict):
        raise CouncilError(f"council record {path} must be an object")
    try:
        findings = tuple(
            Finding(
                lens=str(item.get("lens", "")),
                trigger=str(item.get("trigger", "")),
                wrong_outcome=str(item.get("wrong_outcome", "")),
                location=str(item.get("location", "")),
                evidence=str(item.get("evidence", "")),
                closure=str(item.get("closure", "")),
            )
            for item in data.get("findings", [])
        )
    except AttributeError as error:
        raise CouncilError(f"council record {path} has malformed findings") from error
    waiver_data = data.get("waiver")
    waiver = None
    if isinstance(waiver_data, dict) and str(waiver_data.get("reason", "")).strip():
        waiver = Waiver(
            reason=str(waiver_data["reason"]),
            recorded_at=str(waiver_data.get("recorded_at", "")),
        )
    return CouncilRecord(
        fingerprint=str(data.get("fingerprint", fingerprint)),
        round=int(data.get("round", 1) or 1),
        triggers=tuple(str(item) for item in data.get("triggers", [])),
        lenses=tuple(str(item) for item in data.get("lenses", [])),
        findings=findings,
        questions=tuple(str(item) for item in data.get("questions", [])),
        waiver=waiver,
        recorded_at=str(data.get("recorded_at", "")),
    )


def write_record(root: Path, record: CouncilRecord) -> Path:
    path = record_path(root, record.fingerprint)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record.as_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def record_from_payload(
    payload: object,
    *,
    fingerprint: str,
    triggers: tuple[str, ...],
    recorded_at: str,
) -> CouncilRecord:
    """Build a record from what a council round reported.

    The fingerprint and the trigger list are supplied by the tool, never taken from
    the payload: a round that could name its own diff could name yesterday's.
    """
    if not isinstance(payload, dict):
        raise CouncilError("a council round must be a JSON object")
    round_number = payload.get("round", 1)
    try:
        round_number = int(round_number)
    except (TypeError, ValueError) as error:
        raise CouncilError("round must be a number") from error
    if not 1 <= round_number <= MAX_ROUNDS:
        raise CouncilError(
            f"round must be between 1 and {MAX_ROUNDS}; §4 escalates to the operator after that"
        )

    raw_lenses = payload.get("lenses", [])
    if not isinstance(raw_lenses, list) or not raw_lenses:
        raise CouncilError("a council round must name its lenses (§3: one per member)")
    lenses = tuple(str(item).strip() for item in raw_lenses)
    if any(not lens for lens in lenses):
        raise CouncilError("a lens cannot be blank")

    raw_findings = payload.get("findings", [])
    if not isinstance(raw_findings, list):
        raise CouncilError("findings must be a list")
    findings: list[Finding] = []
    for index, item in enumerate(raw_findings, start=1):
        if not isinstance(item, dict):
            raise CouncilError(f"finding {index} must be an object")
        missing = [
            key for key in ("lens", "trigger", "wrong_outcome", "location", "evidence")
            if not str(item.get(key, "")).strip()
        ]
        if missing:
            # council.md §2: without all four parts it is not a finding, it is a
            # question — and questions belong in `questions`, where they are kept
            # rather than dropped.
            raise CouncilError(
                f"finding {index} is missing {', '.join(missing)}; §2 requires all four parts, "
                "and something without evidence belongs in `questions`"
            )
        findings.append(Finding(
            lens=str(item["lens"]).strip(),
            trigger=str(item["trigger"]).strip(),
            wrong_outcome=str(item["wrong_outcome"]).strip(),
            location=str(item["location"]).strip(),
            evidence=str(item["evidence"]).strip(),
            closure=str(item.get("closure", "")).strip(),
        ))

    raw_questions = payload.get("questions", [])
    if not isinstance(raw_questions, list):
        raise CouncilError("questions must be a list")

    return CouncilRecord(
        fingerprint=fingerprint,
        round=round_number,
        triggers=triggers,
        lenses=lenses,
        findings=tuple(findings),
        questions=tuple(str(item).strip() for item in raw_questions if str(item).strip()),
        recorded_at=recorded_at,
    )


def _distinct_lens_problem(record: CouncilRecord) -> str | None:
    """council.md §3: three members with one lens is one member with extra cost."""
    if not record.lenses:
        return "the record names no lenses; §3 requires one per member"
    if len(set(record.lenses)) != len(record.lenses):
        return f"lenses repeat ({', '.join(record.lenses)}); §3 requires them to differ"
    return None


def evaluate(
    root: Path,
    *,
    operator_requested: bool = False,
    context_ready: bool = True,
) -> GateResult:
    """Decide whether this staged diff may be committed.

    ``context_ready`` is council.md §5: without ``project_context_ready: yes`` the
    council cannot be selected at all, because every question that shapes it reads
    from ``docs/software-overview.md``. The gate says so and steps aside — the
    readiness check that already exists owns that failure, and blocking twice for
    one cause only teaches people to ignore both messages.
    """
    fingerprint = staged_fingerprint(root)
    if fingerprint is None:
        if _git(root, "rev-parse", "--git-dir") is None:
            return GateResult(NOT_A_REPO, "not a git repository")
        return GateResult(NOTHING_STAGED, "nothing staged; the gate applies at commit time")

    triggers = detect_triggers(root, operator_requested=operator_requested)
    if not triggers:
        return GateResult(
            NO_TRIGGER,
            "no council trigger in this diff",
            fingerprint=fingerprint,
        )

    named = ", ".join(trigger.name for trigger in triggers)
    if not context_ready:
        return GateResult(
            NOT_SELECTABLE,
            f"triggers present ({named}) but docs/software-overview.md is not ready, "
            "so §5 forbids selecting a council; fix readiness first",
            triggers=triggers,
            fingerprint=fingerprint,
        )

    record = read_record(root, fingerprint)
    if record is None:
        return GateResult(
            NO_RECORD,
            f"{named}: this delivery needs a council round "
            "(.docs/agents/council.md) and none is recorded for the staged diff",
            triggers=triggers,
            fingerprint=fingerprint,
        )

    if record.fingerprint != fingerprint:
        return GateResult(
            STALE_RECORD,
            "the council record does not match the staged diff; run another round",
            triggers=triggers,
            record=record,
            fingerprint=fingerprint,
        )

    if record.waiver is not None:
        return GateResult(
            WAIVED,
            f"council waived: {record.waiver.reason}",
            triggers=triggers,
            record=record,
            fingerprint=fingerprint,
        )

    lens_problem = _distinct_lens_problem(record)
    if lens_problem:
        return GateResult(
            OPEN_FINDINGS,
            f"council record rejected: {lens_problem}",
            triggers=triggers,
            record=record,
            fingerprint=fingerprint,
        )

    open_findings = record.open_findings
    if open_findings and record.round >= MAX_ROUNDS:
        listed = "; ".join(f"{f.lens}: {f.location}" for f in open_findings)
        return GateResult(
            ROUNDS_EXHAUSTED,
            f"round {record.round} still has {len(open_findings)} open finding(s) "
            f"({listed}). §2 is exhausted — stop and take them to the operator; "
            "do not run another round",
            triggers=triggers,
            record=record,
            fingerprint=fingerprint,
        )
    if open_findings:
        listed = "; ".join(f"{f.lens}: {f.location}" for f in open_findings)
        return GateResult(
            OPEN_FINDINGS,
            f"{len(open_findings)} finding(s) still open after round {record.round} "
            f"({listed}); §2 requires a failing test or a written risk acceptance",
            triggers=triggers,
            record=record,
            fingerprint=fingerprint,
        )

    closed = len(record.findings)
    tail = f", {len(record.questions)} question(s) left open" if record.questions else ""
    return GateResult(
        SATISFIED,
        f"council round {record.round} recorded: {closed} finding(s) closed{tail}",
        triggers=triggers,
        record=record,
        fingerprint=fingerprint,
    )
