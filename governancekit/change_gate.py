from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
import subprocess
from typing import Any

import yaml


class ChangeGateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChangeGateResult:
    contract: Path
    changed_files: tuple[str, ...]
    violations: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.violations

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "contract": str(self.contract),
            "changed_files": list(self.changed_files),
            "violations": list(self.violations),
            "warnings": list(self.warnings),
        }


def _git(root: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ChangeGateError(f"git command failed: {' '.join(args)}") from exc


def changed_files(root: Path, *, staged_only: bool = False) -> tuple[str, ...]:
    names: set[str] = set()

    def add(output: bytes) -> None:
        for raw in output.split(b"\0"):
            if raw:
                names.add(raw.decode("utf-8", errors="surrogateescape").replace("\\", "/"))

    if staged_only:
        add(_git(root, "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMRDT"))
    else:
        add(_git(root, "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMRDT"))
        add(_git(root, "diff", "--name-only", "-z", "--diff-filter=ACMRDT"))
        add(_git(root, "ls-files", "--others", "--exclude-standard", "-z"))

    return tuple(sorted(names))


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in patterns)


def _load_contract(root: Path, contract_path: Path) -> tuple[Path, dict[str, Any]]:
    absolute = contract_path if contract_path.is_absolute() else root / contract_path
    try:
        resolved = absolute.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ChangeGateError("contract must exist inside --root") from exc

    try:
        payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ChangeGateError(f"cannot read change contract: {resolved}") from exc
    if not isinstance(payload, dict):
        raise ChangeGateError("change contract must be a YAML mapping")
    return resolved, payload


def evaluate_change_gate(
    root: Path,
    contract_path: Path,
    *,
    staged_only: bool = False,
) -> ChangeGateResult:
    root = root.resolve()
    contract, payload = _load_contract(root, contract_path)
    relative_contract = contract.relative_to(root).as_posix()

    violations: list[str] = []
    warnings: list[str] = []

    if payload.get("version") != 2:
        violations.append("contract version must be 2")

    work_id = payload.get("work_id")
    if not isinstance(work_id, str) or not work_id.strip():
        violations.append("work_id is required")

    domains_write = payload.get("domains_write")
    if not isinstance(domains_write, list) or not all(isinstance(x, str) and x for x in domains_write):
        violations.append("domains_write must be a list of non-empty strings")
        domains_write = []

    write_scope = payload.get("write_scope")
    if not isinstance(write_scope, list) or not write_scope or not all(
        isinstance(x, str) and x for x in write_scope
    ):
        violations.append("write_scope must be a non-empty list of patterns")
        write_scope = []

    forbidden_scope = payload.get("forbidden_scope", [])
    if not isinstance(forbidden_scope, list) or not all(isinstance(x, str) and x for x in forbidden_scope):
        violations.append("forbidden_scope must be a list of patterns")
        forbidden_scope = []

    for field in ("must_preserve", "acceptance"):
        value = payload.get(field)
        if not isinstance(value, list) or not value:
            violations.append(f"{field} must be a non-empty list")

    baseline = payload.get("baseline")
    if not isinstance(baseline, dict):
        violations.append("baseline must be a mapping")

    if len(domains_write) > 1:
        cross = payload.get("cross_domain")
        if not isinstance(cross, dict) or cross.get("required") is not True:
            violations.append("cross_domain.required must be true when writing more than one domain")
        elif not cross.get("approved_by"):
            violations.append("cross_domain.approved_by is required for cross-domain writes")

    changed = changed_files(root, staged_only=staged_only)
    for path in changed:
        if path == relative_contract:
            continue
        if _matches(path, forbidden_scope):
            violations.append(f"forbidden write: {path}")
            continue
        if write_scope and not _matches(path, write_scope):
            violations.append(f"undeclared write: {path}")

    if not changed:
        warnings.append("no changed files detected")

    return ChangeGateResult(
        contract=Path(relative_contract),
        changed_files=changed,
        violations=tuple(violations),
        warnings=tuple(warnings),
    )
