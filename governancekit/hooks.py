"""Local hook installation for governed repositories."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class HookInstallResult:
    hook_type: str
    path: str
    replaced: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


_PRE_COMMIT_SCRIPT = """#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"

# `doctor` exits non-zero when a mandatory check fails, and this script is what
# decides what that means — so capture rather than let `set -e` abort here.
REPORT="$(python3 -m governancekit.cli --root "$ROOT" doctor --json || true)"

# The verdict is read by a program whose source arrives via -c, never via stdin:
# a heredoc on the reader replaces the pipe it was supposed to read, which is how
# this check silently passed everything it was meant to stop.
VERDICT=$(cat <<'PY'
import json, sys
try:
    payload = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    # An unreadable report is a broken toolchain, not a broken commit.
    sys.exit(0)
mandatory_failures = [
    check for check in payload.get("checks", [])
    if (not check.get("passed")) and (not check.get("advisory"))
]
if mandatory_failures:
    print("governancekit pre-commit blocked: mandatory doctor check failed", file=sys.stderr)
    for check in mandatory_failures:
        print(f" - {check['name']}: {check['message']}", file=sys.stderr)
    sys.exit(1)
PY
)

if [ -n "$REPORT" ]; then
  printf '%s' "$REPORT" | python3 -c "$VERDICT"
else
  echo "governancekit pre-commit: doctor produced no report; not blocking" >&2
fi

STAGED="$(git diff --cached --name-only)"
if printf '%s\n' "$STAGED" | grep -Eq '(^|/)(\\.env|\\.env\\.|\\.credentials($|/)|id_rsa|id_ed25519)'; then
  echo "governancekit pre-commit blocked: staged secret-like path detected" >&2
  exit 1
fi
"""


def install_hook(root: Path, *, hook_type: str = "pre-commit", force: bool = False) -> HookInstallResult:
    root = root.resolve()
    if hook_type != "pre-commit":
        raise RuntimeError(f"unsupported hook type: {hook_type}")
    hook_path = root / ".git" / "hooks" / hook_type
    if not hook_path.parent.is_dir():
        raise RuntimeError("target is not a git repository")
    replaced = hook_path.exists()
    if replaced and not force:
        raise RuntimeError(f"{hook_type} already exists; pass --force to replace it")
    hook_path.write_text(_PRE_COMMIT_SCRIPT, encoding="utf-8")
    hook_path.chmod(0o755)
    return HookInstallResult(hook_type=hook_type, path=str(hook_path), replaced=replaced)
