"""Read-only project discovery for adoption/configuration flows."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .codemap import SKIP_DIRS

_LANGUAGE_SUFFIXES: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rb": "ruby",
    ".rs": "rust",
    ".java": "java",
    ".php": "php",
    ".sh": "shell",
}

_GOVERNANCE_PATHS: tuple[str, ...] = (
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".cursorrules",
    ".windsurfrules",
    ".docs/software-overview.md",
    ".docs/limits.md",
    ".docs/governancekit-integration.json",
    ".gk/manifest.json",
    ".governancekit-identity.json",
    "docs/required-reading.md",
    "docs/issues",
    "handoff.md",
)
_AGENT_FILES: tuple[tuple[str, str], ...] = (
    ("AGENTS.md", "openai-agents"),
    ("CLAUDE.md", "claude"),
    ("GEMINI.md", "gemini"),
    (".cursorrules", "cursor"),
    (".windsurfrules", "windsurf"),
    (".amazonq/rules/ai-agents.md", "amazonq"),
)


@dataclass(frozen=True)
class DiscoveryReport:
    root: Path
    project_state: str
    languages: dict[str, int]
    frameworks: list[str]
    package_managers: list[str]
    automation_commands: list[str]
    agents: list[str]
    governance_files: list[str]
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["root"] = str(self.root)
        return data


def _iter_project_files(root: Path):
    for path in root.rglob("*"):
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if ".git" in rel_parts:
            continue
        if path.is_file():
            yield path


def _detect_languages(root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in _iter_project_files(root):
        language = _LANGUAGE_SUFFIXES.get(path.suffix.lower())
        if language is None:
            continue
        counts[language] = counts.get(language, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _detect_frameworks(root: Path) -> list[str]:
    found: list[str] = []
    package_json = root / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        deps = {}
        for key in ("dependencies", "devDependencies"):
            block = data.get(key)
            if isinstance(block, dict):
                deps.update({str(name): str(version) for name, version in block.items()})
        if "next" in deps:
            found.append("nextjs")
        if "react" in deps:
            found.append("react")
        if "vue" in deps:
            found.append("vue")
        if "svelte" in deps:
            found.append("svelte")
        if "express" in deps:
            found.append("express")
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8", errors="replace")
        if "django" in text.lower():
            found.append("django")
        if "fastapi" in text.lower():
            found.append("fastapi")
        if "flask" in text.lower():
            found.append("flask")
        if "[tool.poetry]" in text:
            found.append("poetry")
    if (root / "go.mod").is_file():
        found.append("go-module")
    if (root / "Cargo.toml").is_file():
        found.append("cargo")
    return sorted(dict.fromkeys(found))


def _detect_package_managers(root: Path) -> list[str]:
    found: list[str] = []
    if (root / "package-lock.json").is_file():
        found.append("npm")
    if (root / "pnpm-lock.yaml").is_file():
        found.append("pnpm")
    if (root / "yarn.lock").is_file():
        found.append("yarn")
    if (root / "pyproject.toml").is_file():
        found.append("pip/pyproject")
    if (root / "requirements.txt").is_file():
        found.append("pip/requirements")
    if (root / "go.mod").is_file():
        found.append("go")
    if (root / "Cargo.toml").is_file():
        found.append("cargo")
    return found


def _detect_commands(root: Path) -> list[str]:
    commands: list[str] = []
    package_json = root / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        scripts = data.get("scripts")
        if isinstance(scripts, dict):
            for name in sorted(scripts):
                commands.append(f"npm run {name}")
    if (root / "Makefile").is_file():
        commands.append("make <target>")
    if (root / "pyproject.toml").is_file():
        commands.append("python3 -m pytest")
    if (root / "docker-compose.yml").is_file() or (root / "docker-compose.yaml").is_file():
        commands.append("docker compose up")
    return commands


def _governance_files(root: Path) -> list[str]:
    found: list[str] = []
    for rel in _GOVERNANCE_PATHS:
        path = root / rel
        if path.exists():
            found.append(rel)
    return found


def _detect_agents(root: Path) -> list[str]:
    found: list[str] = []
    for rel, label in _AGENT_FILES:
        if (root / rel).is_file():
            found.append(label)
    agent_docs = root / ".docs" / "agents"
    if agent_docs.is_dir():
        for path in sorted(agent_docs.glob("*.md")):
            stem = path.stem
            if stem.startswith("_") or stem == "README":
                continue
            found.append(f"policy:{stem}")
    return sorted(dict.fromkeys(found))


def _project_state(root: Path, governance_files: list[str]) -> tuple[str, list[str]]:
    notes: list[str] = []
    all_files = list(_iter_project_files(root))
    if not all_files:
        notes.append("directory is empty")
        return "new", notes
    governance_set = {root / rel for rel in governance_files}
    substantive_files = [
        path for path in all_files
        if path not in governance_set and ".docs" not in path.parts and "docs" not in path.parts
    ]
    if substantive_files:
        notes.append(
            f"detected {len(substantive_files)} non-governance file(s); adoption flow should inspect before writing"
        )
        return "existing", notes
    notes.append("only governance scaffolding detected")
    return "new", notes


def run_discover(root: Path) -> DiscoveryReport:
    root = root.resolve()
    languages = _detect_languages(root)
    governance_files = _governance_files(root)
    project_state, notes = _project_state(root, governance_files)
    return DiscoveryReport(
        root=root,
        project_state=project_state,
        languages=languages,
        frameworks=_detect_frameworks(root),
        package_managers=_detect_package_managers(root),
        automation_commands=_detect_commands(root),
        agents=_detect_agents(root),
        governance_files=governance_files,
        notes=notes,
    )


def format_discovery(report: DiscoveryReport) -> str:
    lines = ["AI GovernanceKit discover"]
    lines.append(f"root: {report.root}")
    lines.append(f"project state: {report.project_state}")
    lines.append(
        "languages: "
        + (", ".join(f"{name} ({count})" for name, count in report.languages.items()) or "(none)")
    )
    lines.append("frameworks: " + (", ".join(report.frameworks) or "(none)"))
    lines.append("package managers: " + (", ".join(report.package_managers) or "(none)"))
    lines.append("automation: " + (", ".join(report.automation_commands) or "(none)"))
    lines.append("agents: " + (", ".join(report.agents) or "(none)"))
    lines.append("governance files: " + (", ".join(report.governance_files) or "(none)"))
    if report.notes:
        lines.append("notes:")
        for note in report.notes:
            lines.append(f"  - {note}")
    return "\n".join(lines)
