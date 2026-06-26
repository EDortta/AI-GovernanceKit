from __future__ import annotations

import re
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REPO = "[GITHUB_OWNER]/AI-Agents"
DEFAULT_REF = "main"

# Paths copied in a fresh install (mirrors install-agents-kit.sh)
_FRESH_PATHS: list[str] = [
    "AGENTS.md",
    ".cursorrules",
    "CLAUDE.md",
    ".windsurfrules",
    "GEMINI.md",
    ".github/copilot-instructions.md",
    ".credentials",
    "docs",
    "handoff.md",
    "new-tag.sh",
    "scripts/install-agents-kit.sh",
]

# Paths replaced during --upgrade (dirs wholesale, files individually)
_UPGRADE_PATHS: list[str] = [
    "AGENTS.md",
    ".cursorrules",
    "CLAUDE.md",
    ".windsurfrules",
    "GEMINI.md",
    ".github/copilot-instructions.md",
    "new-tag.sh",
    "scripts/install-agents-kit.sh",
    "docs/agents",
    "docs/workflows",
    "docs/articles",
    "docs/icons",
    "docs/issues/templates",
    "docs/issues/README.md",
]

_GITIGNORE_BEGIN = "# AI-Agents kit — managed by governancekit install-agents"
_GITIGNORE_END = "# end AI-Agents kit"


@dataclass
class InstallResult:
    target: Path
    upgraded: bool
    paths_installed: list[str] = field(default_factory=list)
    gitignore_updated: bool = False
    gitignore_path: Path | None = None


def run_install_agents(
    root: Path,
    *,
    ref: str = DEFAULT_REF,
    repo: str = REPO,
    force: bool = False,
    upgrade: bool = False,
    track: bool = False,
) -> InstallResult:
    """Download and install AI-Agents kit into *root*.

    By default the installed paths are added to .gitignore so the kit files
    stay out of the host repository.  Pass ``track=True`` to keep them tracked.
    """
    root = root.resolve()

    with tempfile.TemporaryDirectory() as tmp:
        src_root = _download(repo, ref, Path(tmp))
        result = InstallResult(target=root, upgraded=upgrade)

        if upgrade:
            result.paths_installed = _do_upgrade(src_root, root)
        else:
            result.paths_installed = _do_fresh(src_root, root, force=force)

        if not track:
            gitignore_path = root / ".gitignore"
            _update_gitignore(gitignore_path, result.paths_installed)
            result.gitignore_updated = True
            result.gitignore_path = gitignore_path
        else:
            # Remove any existing kit section if the user wants to track files
            gitignore_path = root / ".gitignore"
            if gitignore_path.is_file():
                removed = _remove_gitignore_section(gitignore_path)
                if removed:
                    result.gitignore_updated = True
                    result.gitignore_path = gitignore_path

    _fill_placeholders(root, result.paths_installed)
    return result


# ── download ───────────────────────────────────────────────────────────────────

def _download(repo: str, ref: str, tmp: Path) -> Path:
    url = f"https://codeload.github.com/{repo}/tar.gz/{ref}"
    archive = tmp / "src.tar.gz"
    try:
        urllib.request.urlretrieve(url, archive)  # noqa: S310
    except Exception as exc:
        raise RuntimeError(f"Failed to download {url}: {exc}") from exc

    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(tmp)

    extracted = [p for p in tmp.iterdir() if p.is_dir() and p.name != archive.name]
    if not extracted:
        raise RuntimeError("Unexpected archive structure — no top-level directory found.")
    return extracted[0]


# ── fresh install ──────────────────────────────────────────────────────────────

_CONFLICT_FORCE_THRESHOLD = 0.10  # suggest --force when conflicts exceed this ratio


def _do_fresh(src: Path, dst: Path, *, force: bool) -> list[str]:
    available = [rel for rel in _FRESH_PATHS if (src / rel).exists()]
    conflicts = [rel for rel in available if (dst / rel).exists()]

    skip: set[str] = set()

    if conflicts and not force:
        ratio = len(conflicts) / len(available) if available else 0
        if ratio > _CONFLICT_FORCE_THRESHOLD:
            print(
                f"Warning: {len(conflicts)} of {len(available)} paths already exist "
                f"({ratio:.0%}). Consider using --force to overwrite all at once."
            )

        interactive = sys.stdin.isatty()
        for rel in conflicts:
            if interactive:
                try:
                    answer = input(f"  '{rel}' already exists — overwrite? [y/N] ").strip().lower()
                except EOFError:
                    answer = ""
                if answer != "y":
                    print(f"  skipped: {rel}")
                    skip.add(rel)
            else:
                print(f"Warning: '{rel}' already exists, skipping.")
                skip.add(rel)

    installed: list[str] = []
    for rel in available:
        if rel in skip:
            continue
        src_path = src / rel
        dst_path = dst / rel
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if dst_path.exists():
            if dst_path.is_dir():
                shutil.rmtree(dst_path)
            else:
                dst_path.unlink()
        if src_path.is_dir():
            shutil.copytree(src_path, dst_path)
        else:
            shutil.copy2(src_path, dst_path)
        installed.append(rel)

    _reset_readiness_flags(dst)
    return installed


def _reset_readiness_flags(root: Path) -> None:
    for rel, pattern, replacement in [
        (
            "docs/software-overview.md",
            "- project_context_ready: yes",
            "- project_context_ready: no",
        ),
        (
            "docs/limits.md",
            "- limits_ready: yes",
            "- limits_ready: no",
        ),
    ]:
        path = root / rel
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            path.write_text(text.replace(pattern, replacement), encoding="utf-8")


# ── upgrade ────────────────────────────────────────────────────────────────────

def _do_upgrade(src: Path, dst: Path) -> list[str]:
    installed: list[str] = []
    for rel in _UPGRADE_PATHS:
        src_path = src / rel
        dst_path = dst / rel
        if not src_path.exists():
            continue
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if src_path.is_dir():
            if dst_path.exists():
                shutil.rmtree(dst_path)
            shutil.copytree(src_path, dst_path)
        else:
            shutil.copy2(src_path, dst_path)
        installed.append(rel)
    return installed


# ── placeholder resolution ─────────────────────────────────────────────────────

_PLACEHOLDER_RE = re.compile(r"\[([A-Z][A-Z0-9_]+)\]")

_PLACEHOLDER_DESCRIPTIONS: dict[str, str] = {
    "OPERATOR_NAME": "operator / project owner name (used in agent greetings)",
    "GITHUB_OWNER": "GitHub username or organisation that owns the repo",
    "PROJECT_SLUG": "short identifier for this project (used in work_ids and logs, e.g. my-app)",
    "SMTP_ACCOUNT": "SMTP email account (e.g. you@yourdomain.com)",
    "SMTP_DOMAIN": "email domain (e.g. yourdomain.com)",
    "ORG_NAME": "organisation or company name",
    "PIX_KEY_UUID": "PIX random key UUID (Brazil payment system)",
    "PIX_HOLDER_NAME": "full name registered with the PIX key",
    "PIX_PAYLOAD": "full PIX copy-and-paste payload string",
    "PIX_QR_BASE64": "base64-encoded PNG of the PIX QR code",
    "PROJECT_ROOT": "absolute path to the project root on this machine",
    "KOFI_HANDLE": "Ko-fi username (e.g. yourhandle)",
    "ETH_WALLET_ADDRESS": "Ethereum wallet address for donations (0x...)",
}


def _fill_placeholders(root: Path, installed_paths: list[str]) -> None:
    """Scan installed files for [PLACEHOLDER] tokens and prompt the user for values."""
    # Collect all unique placeholders across installed files
    placeholder_files: dict[str, list[Path]] = {}
    for rel in installed_paths:
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for token in _PLACEHOLDER_RE.findall(text):
            placeholder_files.setdefault(token, []).append(path)

    if not placeholder_files:
        return

    if not sys.stdin.isatty():
        print(
            "\nWarning: the following placeholders were not filled "
            "(no interactive terminal):\n  "
            + ", ".join(f"[{p}]" for p in sorted(placeholder_files))
        )
        return

    print("\n── Configure installed kit ────────────────────────────────────────")
    print("The following values are required. Press Enter to skip any item.\n")

    values: dict[str, str] = {}
    for token in sorted(placeholder_files):
        desc = _PLACEHOLDER_DESCRIPTIONS.get(token, "")
        prompt = f"  [{token}]"
        if desc:
            prompt += f"  ({desc})"
        prompt += ": "
        try:
            answer = input(prompt).strip()
        except EOFError:
            answer = ""
        if answer:
            values[token] = answer

    if not values:
        print("\nNo values provided — placeholders left as-is.")
        return

    # Apply substitutions
    changed: list[str] = []
    seen_paths: set[Path] = set()
    for token, val in values.items():
        for path in placeholder_files.get(token, []):
            if path not in seen_paths:
                seen_paths.add(path)
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            new_text = text
            for t, v in values.items():
                new_text = new_text.replace(f"[{t}]", v)
            if new_text != text:
                path.write_text(new_text, encoding="utf-8")
                changed.append(str(path.relative_to(root)))

    if changed:
        print("\nPlaceholders filled in: " + ", ".join(sorted(set(changed))))

    # Warn about any that were skipped
    unfilled = [t for t in placeholder_files if t not in values]
    if unfilled:
        print(
            "Still unfilled (skipped): "
            + ", ".join(f"[{t}]" for t in sorted(unfilled))
        )


# ── .gitignore management ──────────────────────────────────────────────────────

def _update_gitignore(gitignore: Path, paths: list[str]) -> None:
    existing = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    cleaned = _remove_section_text(existing)
    entries = "\n".join(paths)
    section = f"\n{_GITIGNORE_BEGIN}\n{entries}\n{_GITIGNORE_END}\n"
    gitignore.write_text(cleaned.rstrip("\n") + section, encoding="utf-8")


def _remove_gitignore_section(gitignore: Path) -> bool:
    """Remove the kit section from .gitignore; returns True if a change was made."""
    text = gitignore.read_text(encoding="utf-8")
    cleaned = _remove_section_text(text)
    if cleaned == text:
        return False
    gitignore.write_text(cleaned, encoding="utf-8")
    return True


def _remove_section_text(text: str) -> str:
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.rstrip("\n")
        if stripped == _GITIGNORE_BEGIN:
            in_section = True
            continue
        if stripped == _GITIGNORE_END:
            in_section = False
            continue
        if not in_section:
            result.append(line)
    return "".join(result)
