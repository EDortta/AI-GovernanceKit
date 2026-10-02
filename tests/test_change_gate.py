from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from governancekit.change_gate import evaluate_change_gate


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def make_repo(tmp_path: Path) -> Path:
    root = tmp_path
    git(root, "init", "-q")
    git(root, "config", "user.email", "change-gate@test")
    git(root, "config", "user.name", "change-gate")
    (root / "src/a").mkdir(parents=True)
    (root / "src/b").mkdir(parents=True)
    (root / "src/a/file.py").write_text("before\n", encoding="utf-8")
    (root / "src/b/file.py").write_text("before\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "seed")
    return root


def write_contract(root: Path, **overrides) -> Path:
    payload = {
        "version": 2,
        "work_id": "WK-20261001-test",
        "domains_read": ["a"],
        "domains_write": ["a"],
        "write_scope": ["src/a/**"],
        "forbidden_scope": ["src/b/**"],
        "must_preserve": ["existing behavior"],
        "acceptance": ["new behavior works"],
        "baseline": {"commands": ["pytest"], "scenarios": []},
        "cross_domain": {"required": False, "approved_by": None, "reason": None},
    }
    payload.update(overrides)
    path = root / "docs/ai-governance/changes/WK-20261001-test.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def test_declared_write_passes(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    contract = write_contract(root)
    (root / "src/a/file.py").write_text("after\n", encoding="utf-8")

    result = evaluate_change_gate(root, contract)

    assert result.ok
    assert "src/a/file.py" in result.changed_files


def test_undeclared_write_blocks(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    contract = write_contract(root, forbidden_scope=[])
    (root / "src/b/file.py").write_text("after\n", encoding="utf-8")

    result = evaluate_change_gate(root, contract)

    assert not result.ok
    assert "undeclared write: src/b/file.py" in result.violations


def test_forbidden_write_blocks_even_if_write_scope_is_broad(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    contract = write_contract(root, write_scope=["src/**"])
    (root / "src/b/file.py").write_text("after\n", encoding="utf-8")

    result = evaluate_change_gate(root, contract)

    assert "forbidden write: src/b/file.py" in result.violations


def test_cross_domain_requires_explicit_approval(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    contract = write_contract(
        root,
        domains_write=["a", "b"],
        write_scope=["src/**"],
        forbidden_scope=[],
    )
    (root / "src/a/file.py").write_text("after\n", encoding="utf-8")

    result = evaluate_change_gate(root, contract)

    assert "cross_domain.required must be true when writing more than one domain" in result.violations


def test_cross_domain_with_approval_passes(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    contract = write_contract(
        root,
        domains_write=["a", "b"],
        write_scope=["src/**"],
        forbidden_scope=[],
        cross_domain={"required": True, "approved_by": "operator", "reason": "contract change"},
    )
    (root / "src/a/file.py").write_text("after\n", encoding="utf-8")
    (root / "src/b/file.py").write_text("after\n", encoding="utf-8")

    result = evaluate_change_gate(root, contract)

    assert result.ok


def test_contract_file_is_implicitly_allowed(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    contract = write_contract(root)

    result = evaluate_change_gate(root, contract)

    assert result.ok
    assert contract.relative_to(root).as_posix() in result.changed_files
