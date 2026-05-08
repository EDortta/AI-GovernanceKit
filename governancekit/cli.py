from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .doctor import DoctorResult, run_doctor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="governancekit",
        description="Validate and orchestrate AI GovernanceKit workflows.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root to inspect. Defaults to the current directory.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="Validate required governance files and readiness gates.")

    map_parser = subparsers.add_parser("map", help="Generate a Markdown code map of the project.")
    map_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="PATH",
        help="Output path (default: docs/codemap.md under root).",
    )
    map_parser.add_argument(
        "--all",
        dest="include_private",
        action="store_true",
        help="Include private (single-underscore) symbols.",
    )
    return parser


def format_result(result: DoctorResult) -> str:
    lines = ["AI GovernanceKit doctor"]
    for check in result.checks:
        if check.passed:
            marker = "PASS"
        elif check.advisory:
            marker = "HINT"
        else:
            marker = "FAIL"
        lines.append(f"[{marker}] {check.name}: {check.message}")
    lines.append("Result: PASS" if result.ok else "Result: FAIL")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        result = run_doctor(args.root)
        print(format_result(result))
        return 0 if result.ok else 1

    if args.command == "map":
        from .codemap import run_map
        result = run_map(args.root, output=args.output, include_private=args.include_private)
        print(f"Code map written to: {result.output_path}")
        print(f"  {result.file_count} file(s) · {result.symbol_count} symbol(s) indexed")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2

