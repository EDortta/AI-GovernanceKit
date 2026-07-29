"""Create local issue/epic scaffolding from installed templates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
import unicodedata

from .classification import load_change_classification
from .project_config import load_project_config

_EPIC_TEMPLATE = ".docs/issues/templates/epic.template.md"
_README_TEMPLATE = ".docs/issues/templates/README.template.md"
_TASK_TEMPLATE = ".docs/issues/templates/task.template.md"


@dataclass(frozen=True)
class IssueBootstrapResult:
    epic_dir: str
    files: list[str]


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "item"


def _read_template(root: Path, rel: str) -> str:
    path = root / rel
    if not path.is_file():
        raise RuntimeError(f"missing issue template: {rel}")
    return path.read_text(encoding="utf-8")


def _replace_common(
    text: str,
    *,
    title: str,
    work_id: str,
    owner: str,
    related_commit: str,
    epic_ref: str | None = None,
    project_context: str = "",
    classification_summary: str = "",
) -> str:
    today = date.today().isoformat()
    replacements = {
        "<EPIC_TITLE>": title,
        "<TASK_TITLE>": title,
        "WK-YYYYMMDD-<short-slug>": work_id,
        "YYYY-MM-DD": today,
        "<name>": owner,
        "<planned-or-hash>": related_commit,
        "<NNN-epic-slug>": epic_ref or "<NNN-epic-slug>",
        "<business and technical context>": project_context or "<business and technical context>",
        "<problem>": classification_summary or "<problem>",
        "<expected outcome>": classification_summary or "<expected outcome>",
        "<objective>": classification_summary or "<objective>",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def bootstrap_issue(
    root: Path,
    *,
    epic_number: str,
    epic_title: str,
    task_title: str,
    owner: str = "operator",
    related_commit: str = "planned",
) -> IssueBootstrapResult:
    root = root.resolve()
    epic_slug = _slugify(epic_title)
    task_slug = _slugify(task_title)
    today = date.today().strftime("%Y%m%d")
    work_id = f"WK-{today}-{epic_slug[:24]}"
    epic_dir_rel = f"docs/issues/{epic_number}-{epic_slug}-[draft]"
    epic_dir = root / epic_dir_rel
    task_rel = f"{epic_number}-{task_slug}-[draft].md"

    epic_dir.mkdir(parents=True, exist_ok=True)
    (epic_dir / "issues").mkdir(exist_ok=True)

    project_config = load_project_config(root)
    classification = load_change_classification(root)
    project_context = (
        f"domains: {', '.join(project_config.domains)}; "
        f"capabilities: {', '.join(project_config.capabilities)}"
        if project_config
        else "<business and technical context>"
    )
    classification_summary = (
        f"{classification.summary}. labels: {', '.join(classification.labels)}"
        if classification
        else "<problem>"
    )

    readme = _replace_common(
        _read_template(root, _README_TEMPLATE),
        title=epic_title,
        work_id=work_id,
        owner=owner,
        related_commit=related_commit,
        project_context=project_context,
        classification_summary=classification_summary,
    )
    epic = _replace_common(
        _read_template(root, _EPIC_TEMPLATE),
        title=epic_title,
        work_id=work_id,
        owner=owner,
        related_commit=related_commit,
        project_context=project_context,
        classification_summary=classification_summary,
    )
    task = _replace_common(
        _read_template(root, _TASK_TEMPLATE),
        title=task_title,
        work_id=work_id,
        owner=owner,
        related_commit=related_commit,
        epic_ref=f"{epic_number}-{epic_slug}",
        project_context=project_context,
        classification_summary=classification_summary,
    )

    files = [
        f"{epic_dir_rel}/README.md",
        f"{epic_dir_rel}/epic.md",
        f"{epic_dir_rel}/issues/{task_rel}",
    ]
    (root / files[0]).write_text(readme, encoding="utf-8")
    (root / files[1]).write_text(epic, encoding="utf-8")
    (root / files[2]).write_text(task, encoding="utf-8")
    return IssueBootstrapResult(epic_dir=epic_dir_rel, files=files)
