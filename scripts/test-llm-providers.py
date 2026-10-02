#!/usr/bin/env python3
"""Run a complete LLM provider diagnostic without exposing credentials."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from governancekit.llm_test import (
    LlmTestResult,
    check_configured_providers,
    check_well_known_from_directory,
)


def _category(detail: str) -> str:
    text = detail.casefold()
    if "http 401" in text or "http 403" in text or "credential" in text:
        return "authentication"
    if "http 404" in text or "http 410" in text:
        return "endpoint-or-model"
    if "could not reach" in text or "timed out" in text:
        return "connectivity"
    if "credential file not found" in text:
        return "missing-credential"
    return "provider"


def _render_group(title: str, results: list[LlmTestResult]) -> list[str]:
    lines = ["", title]
    if not results:
        lines.append("  no providers found")
        return lines
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        suffix = "" if result.ok else f" [{_category(result.detail)}]"
        lines.append(
            f"  {status} {result.name} / {result.model or '(unset)'}{suffix}: {result.detail}"
        )
    return lines


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test the project's configured LLM providers and, optionally, every "
            "well-known provider with credentials found in an external directory."
        )
    )
    parser.add_argument("--root", type=Path, required=True, help="Project root.")
    parser.add_argument(
        "--credentials-dir",
        type=Path,
        default=None,
        help="External credential directory, e.g. ~/.config/credentials/personal.",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def main() -> int:
    args = _args()
    root = args.root.expanduser().resolve()

    configured = check_configured_providers(root)
    external: list[LlmTestResult] = []
    external_error: str | None = None
    if args.credentials_dir is not None:
        try:
            external = check_well_known_from_directory(args.credentials_dir)
        except RuntimeError as exc:
            external_error = str(exc)

    all_results = [*configured, *external]
    if args.as_json:
        print(json.dumps({
            "root": str(root),
            "configured": [item.as_dict() | {"category": None if item.ok else _category(item.detail)}
                           for item in configured],
            "well_known": [item.as_dict() | {"category": None if item.ok else _category(item.detail)}
                           for item in external],
            "credentials_dir_error": external_error,
            "ok": bool(all_results) and all(item.ok for item in all_results) and external_error is None,
        }, ensure_ascii=False, sort_keys=True))
    else:
        lines = ["AI GovernanceKit complete LLM diagnostic", f"project: {root}"]
        lines += _render_group("CONFIGURED PROJECT PROVIDERS", configured)
        if args.credentials_dir is not None:
            lines.append(f"credentials directory: {args.credentials_dir.expanduser()}")
            if external_error:
                lines += ["", "WELL-KNOWN PROVIDERS", f"  ERROR: {external_error}"]
            else:
                lines += _render_group("WELL-KNOWN PROVIDERS", external)
        passed = [item for item in all_results if item.ok]
        failed = [item for item in all_results if not item.ok]
        lines += [
            "",
            "SUMMARY",
            f"  passing: {len(passed)}",
            f"  failing: {len(failed)}",
        ]
        if passed:
            lines.append("  usable now: " + ", ".join(
                f"{item.name}/{item.model or '(unset)'}" for item in passed
            ))
        print("\n".join(lines))

    if external_error:
        return 2
    return 0 if all_results and all(item.ok for item in all_results) else 1


if __name__ == "__main__":
    sys.exit(main())
