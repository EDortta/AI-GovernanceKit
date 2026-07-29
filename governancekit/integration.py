"""AI-Agents <-> GovernanceKit integration contract inspection."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .install_agents import REPO

_CONTRACT_REL = ".docs/governancekit-integration.json"
_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_RANGE_RE = re.compile(r"^(>=|<=|>|<|==)\s*(v?\d+\.\d+\.\d+)$")


def _parse_version(raw: str) -> tuple[int, int, int] | None:
    match = _SEMVER_RE.fullmatch(raw.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def _matches_range(version: str, spec: str) -> bool:
    parsed = _parse_version(version)
    if parsed is None:
        return False
    for chunk in (part.strip() for part in spec.split(",")):
        if not chunk:
            continue
        match = _RANGE_RE.fullmatch(chunk)
        if not match:
            return False
        op, raw_expected = match.groups()
        expected = _parse_version(raw_expected)
        if expected is None:
            return False
        if op == ">=" and not (parsed >= expected):
            return False
        if op == "<=" and not (parsed <= expected):
            return False
        if op == ">" and not (parsed > expected):
            return False
        if op == "<" and not (parsed < expected):
            return False
        if op == "==" and not (parsed == expected):
            return False
    return True


@dataclass(frozen=True)
class IntegrationContract:
    path: Path
    schema_version: int
    agents_repo: str
    agents_ref: str
    governancekit_version_range: str
    required_features: tuple[str, ...]


@dataclass(frozen=True)
class IntegrationStatus:
    status: str
    message: str
    contract: IntegrationContract | None = None


def find_integration_contract(start: Path) -> tuple[Path, Path] | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        contract = candidate / _CONTRACT_REL
        if contract.is_file():
            return candidate, contract
    return None


def load_integration_contract(path: Path) -> IntegrationContract:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("contract root must be a JSON object")
    schema_version = data.get("schema_version")
    agents = data.get("ai_agents")
    governancekit = data.get("governancekit")
    if not isinstance(schema_version, int):
        raise ValueError("schema_version must be an integer")
    if not isinstance(agents, dict):
        raise ValueError("ai_agents block missing")
    if not isinstance(governancekit, dict):
        raise ValueError("governancekit block missing")
    repo = agents.get("repo")
    ref = agents.get("ref")
    version_range = governancekit.get("version_range")
    required_features = governancekit.get("required_features", [])
    if not isinstance(repo, str) or not repo:
        raise ValueError("ai_agents.repo must be a non-empty string")
    if not isinstance(ref, str) or not ref:
        raise ValueError("ai_agents.ref must be a non-empty string")
    if not isinstance(version_range, str) or not version_range:
        raise ValueError("governancekit.version_range must be a non-empty string")
    if not isinstance(required_features, list) or any(
        not isinstance(feature, str) or not feature for feature in required_features
    ):
        raise ValueError("governancekit.required_features must be a list of strings")
    return IntegrationContract(
        path=path,
        schema_version=schema_version,
        agents_repo=repo,
        agents_ref=ref,
        governancekit_version_range=version_range,
        required_features=tuple(required_features),
    )


def inspect_integration_contract(root: Path) -> IntegrationStatus:
    found = find_integration_contract(root)
    if found is None:
        return IntegrationStatus(
            status="missing",
            message="AI-Agents integration contract not found under .docs/",
        )
    _, contract_path = found
    try:
        contract = load_integration_contract(contract_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return IntegrationStatus(
            status="unreadable",
            message=f"AI-Agents integration contract unreadable: {exc}",
        )

    if contract.agents_repo != REPO:
        return IntegrationStatus(
            status="custom-repo",
            message=f"AI-Agents integration contract targets a custom repo ({contract.agents_repo})",
            contract=contract,
        )

    if not _matches_range(__version__, contract.governancekit_version_range):
        return IntegrationStatus(
            status="incompatible",
            message=(
                "AI-Agents integration contract requires GovernanceKit "
                f"{contract.governancekit_version_range}, current version is {__version__}"
            ),
            contract=contract,
        )

    return IntegrationStatus(
        status="ok",
        message=(
            f"AI-Agents contract {contract.agents_ref} is compatible with "
            f"GovernanceKit {__version__}"
        ),
        contract=contract,
    )
