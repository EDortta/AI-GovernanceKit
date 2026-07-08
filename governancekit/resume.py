from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# ── data model ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class HandoffEntry:
    """Parsed snapshot from the most recent handoff.md entry."""

    work_id: str
    date: str
    status: str
    branch: str
    summary: str
    next_steps: str
    blockers: str


@dataclass(frozen=True)
class ResumeResult:
    """Context assembled for the start of a new session."""

    root: Path
    work_id: str
    branch: str
    status: str
    next_step: str
    handoff: HandoffEntry | None
    warning: str  # non-fatal issue (e.g. handoff.md missing); empty if none
    operator_name: str = ''
    host_id: str = ''
    active_branch: str = ''       # git branch of this checkout
    identity_warning: str = ''    # same-branch / sibling collision warning


# ── public API ─────────────────────────────────────────────────────────────────

def _load_identity_context(root: Path) -> tuple[str, str, str, str]:
    """Return (operator_name, host_id, active_branch, identity_warning)."""
    from .identity import current_branch, load_identity, sibling_branch_conflict

    identity = load_identity(root)
    active_branch = current_branch(root)
    if identity is None:
        return '', '', active_branch, (
            'No host identity found — run governancekit configure to declare '
            'operator_name/host_id/instance_path.'
        )
    warning = sibling_branch_conflict(identity, active_branch)
    return identity.operator_name, identity.host_id, active_branch, warning


def run_resume(root: Path) -> ResumeResult:
    """Assemble session-start context from RESUME.md and handoff.md."""
    root = root.resolve()

    operator_name, host_id, active_branch, identity_warning = _load_identity_context(root)

    resume_path = _find_resume(root)
    if resume_path is None:
        return ResumeResult(
            root=root,
            work_id='', branch='', status='',
            next_step='',
            handoff=None,
            warning='No RESUME.md found under docs/issues/ — run governancekit doctor for details.',
            operator_name=operator_name,
            host_id=host_id,
            active_branch=active_branch,
            identity_warning=identity_warning,
        )

    meta, next_step = _parse_resume_md(resume_path)

    handoff_path = root / 'handoff.md'
    handoff: HandoffEntry | None = None
    warning = ''
    if handoff_path.is_file():
        handoff = _parse_handoff_md(handoff_path)
        if handoff is None:
            warning = 'handoff.md found but could not be parsed (unexpected format).'
    else:
        warning = 'handoff.md not found — no recent context available.'

    return ResumeResult(
        root=root,
        work_id=meta.get('work_id', ''),
        branch=meta.get('branch', ''),
        status=meta.get('status', ''),
        next_step=next_step,
        handoff=handoff,
        warning=warning,
        operator_name=operator_name,
        host_id=host_id,
        active_branch=active_branch,
        identity_warning=identity_warning,
    )


# ── RESUME.md parsing ──────────────────────────────────────────────────────────

def _find_resume(root: Path) -> Path | None:
    """Return the active RESUME.md, preferring [started] epics."""
    issues_root = root / 'docs' / 'issues'
    if not issues_root.is_dir():
        return None
    resume_files = sorted(
        p for p in issues_root.glob('*/RESUME.md')
        if p.is_file() and p.parent.name != 'templates'
    )
    if not resume_files:
        return None
    for rf in resume_files:
        if '[started]' in rf.parent.name:
            return rf
    return resume_files[0]


def _parse_resume_md(path: Path) -> tuple[dict[str, str], str]:
    """Return (metadata dict, next_step text) from a RESUME.md file."""
    try:
        content = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return {}, ''

    meta: dict[str, str] = {}
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith('## '):
            break
        if stripped.startswith('- ') and ':' in stripped:
            key, _, val = stripped[2:].partition(':')
            meta[key.strip().lower().replace(' ', '_')] = val.strip()

    next_step = ''
    marker = '## Next Step (DO THIS FIRST)'
    if marker in content:
        after = content.split(marker, 1)[1].strip()
        step_lines: list[str] = []
        for line in after.splitlines():
            if line.startswith('## '):
                break
            step_lines.append(line)
        next_step = '\n'.join(step_lines).strip()

    return meta, next_step


# ── handoff.md parsing ─────────────────────────────────────────────────────────

_MULTI_ENTRY_RE = re.compile(
    r'^## \[(\d{4}-\d{2}-\d{2})\] (WK-[^\s]+) - (.+)$',
    re.MULTILINE,
)


def _parse_handoff_md(path: Path) -> HandoffEntry | None:
    """Return the most recent entry from handoff.md, or None if unparseable."""
    try:
        content = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None

    # ── multi-entry format: ## [YYYY-MM-DD] WK-xxx - status ──────────────────
    matches = list(_MULTI_ENTRY_RE.finditer(content))
    if matches:
        m = matches[0]
        date, work_id, status = m.group(1), m.group(2), m.group(3).strip()
        end = matches[1].start() if len(matches) > 1 else len(content)
        section = content[m.end():end]

        return HandoffEntry(
            work_id=work_id,
            date=date,
            status=status,
            branch=_bullet_value(section, 'branch'),
            summary=_bullet_value(section, 'summary'),
            next_steps=_section_text(section, 'next steps'),
            blockers=_section_text(section, 'blockers'),
        )

    # ── single-entry format: ## Current Status + - key: value ─────────────────
    if '## Current Status' in content:
        status_block = content.split('## Current Status', 1)[1]
        meta: dict[str, str] = {}
        for line in status_block.splitlines():
            stripped = line.strip()
            if stripped.startswith('## '):
                break
            if stripped.startswith('- ') and ':' in stripped:
                key, _, val = stripped[2:].partition(':')
                meta[key.strip().lower().replace(' ', '_')] = val.strip()

        return HandoffEntry(
            work_id=meta.get('work_id', ''),
            date=meta.get('date', ''),
            status=meta.get('status', ''),
            branch=meta.get('branch', ''),
            summary='',
            next_steps=_section_text(content, 'next steps'),
            blockers=_section_text(content, 'blockers'),
        )

    return None


def _bullet_value(text: str, key: str) -> str:
    """Extract `- Key: value` from a block of text (case-insensitive key)."""
    key_lower = key.lower()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('- ') and ':' in stripped:
            k, _, v = stripped[2:].partition(':')
            if k.strip().lower() == key_lower:
                return v.strip()
    return ''


def _section_text(text: str, heading_fragment: str) -> str:
    """Extract content under the first heading matching heading_fragment (case-insensitive)."""
    fragment = heading_fragment.lower()
    lines = text.splitlines()
    in_section = False
    collected: list[str] = []
    for line in lines:
        if line.startswith('## ') or line.startswith('# '):
            if line.lstrip('#').strip().lower().startswith(fragment):
                in_section = True
                continue
            elif in_section:
                break
        elif in_section:
            collected.append(line)
    return '\n'.join(collected).strip()
