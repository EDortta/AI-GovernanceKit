from __future__ import annotations

import argparse
import json
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

    doctor_parser = subparsers.add_parser(
        "doctor", help="Validate required governance files and readiness gates."
    )
    doctor_parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output results as JSON (useful for CI scripts).",
    )

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

    subparsers.add_parser(
        "resume", help="Print session-start context from RESUME.md and handoff.md."
    )

    install_parser = subparsers.add_parser(
        "install-agents",
        help="Install AI-Agents kit (github.com/[GITHUB_OWNER]/AI-Agents) into the project.",
    )
    from .install_agents import DEFAULT_REF, REPO

    install_parser.add_argument(
        "--ref",
        default=DEFAULT_REF,
        metavar="REF",
        help=f"Git ref (branch, tag, or commit) to download. Default: {DEFAULT_REF} (checksum-verified).",
    )
    install_parser.add_argument(
        "--repo",
        default=REPO,
        metavar="OWNER/REPO",
        help=f"GitHub repository in owner/repo format. Default: {REPO}.",
    )
    install_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing kit files in target.",
    )
    install_parser.add_argument(
        "--upgrade",
        action="store_true",
        help="Update kit-owned files while preserving project-local state.",
    )
    install_parser.add_argument(
        "--docs-only",
        dest="docs_only",
        action="store_true",
        help=(
            "Refresh only kit-owned documentation (.docs/agents, .docs/workflows, "
            "templates, ...) without touching AGENTS.md or per-tool rule files."
        ),
    )
    install_parser.add_argument(
        "--install-awt",
        dest="install_awt",
        action="store_true",
        help=(
            "Run the downloaded scripts/agent-worktree.sh install (symlinks 'awt' "
            "onto PATH). Off by default since it executes code from the kit."
        ),
    )
    track_group = install_parser.add_mutually_exclusive_group()
    track_group.add_argument(
        "--track",
        dest="track",
        action="store_true",
        default=None,
        help=(
            "Track the kit documentation (.docs/) in git (do NOT add it to "
            ".gitignore). The choice is saved to .governancekit. Secrets "
            "(.credentials, handoff.md) and rule files stay gitignored regardless."
        ),
    )
    track_group.add_argument(
        "--no-track",
        dest="track",
        action="store_false",
        default=None,
        help="Keep the kit documentation (.docs/) out of git. Saved to .governancekit.",
    )

    configure_parser = subparsers.add_parser(
        "configure",
        help="Fill kit placeholder variables (e.g. [OPERATOR_NAME]) across all docs.",
    )
    configure_parser.add_argument(
        "--set",
        dest="set_pairs",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Set a placeholder value non-interactively. Repeatable.",
    )
    identity_group = configure_parser.add_argument_group(
        "host identity", "Per-instance, gitignored identity (non-interactive flags)."
    )
    identity_group.add_argument("--operator-name", dest="operator_name", metavar="NAME")
    identity_group.add_argument("--host-id", dest="host_id", metavar="ID")
    identity_group.add_argument("--instance-path", dest="instance_path", metavar="PATH")
    identity_group.add_argument("--sibling-path", dest="sibling_path", metavar="PATH")
    identity_group.add_argument("--assigned-ports", dest="assigned_ports", metavar="PORTS")
    identity_group.add_argument("--branch-ownership", dest="branch_ownership", metavar="BRANCH")

    return parser


def format_doctor(result: DoctorResult) -> str:
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


def format_doctor_json(result: DoctorResult) -> str:
    return json.dumps({
        "ok": result.ok,
        "checks": [
            {
                "name": c.name,
                "passed": c.passed,
                "advisory": c.advisory,
                "message": c.message,
            }
            for c in result.checks
        ],
    })


def format_resume(result) -> str:
    from .resume import ResumeResult
    lines = ["AI GovernanceKit resume"]

    # ── Active identity (session start) ─────────────────────────────────────
    operator = result.operator_name or "(no identity)"
    host = result.host_id or "(unknown host)"
    lines.append(f"operator: {operator} @ host: {host}")
    if result.active_branch:
        lines.append(f"active branch: {result.active_branch}")
    if result.identity_warning:
        lines.append(f"WARNING: {result.identity_warning}")

    if not result.next_step and not result.work_id:
        lines.append(f"Error: {result.warning}")
        return "\n".join(lines)

    lines.append(f"work_id : {result.work_id or '(unknown)'}")
    if result.branch:
        lines.append(f"branch  : {result.branch}")
    lines.append(f"status  : {result.status or '(unknown)'}")

    if result.next_step:
        lines += ["", "── Next Step " + "─" * 35]
        for line in result.next_step.splitlines():
            lines.append(f"  {line}" if line.strip() else "")
    else:
        lines += ["", "── Next Step " + "─" * 35, "  (none found in RESUME.md)"]

    if result.handoff:
        h = result.handoff
        lines += ["", "── Recent Handoff " + "─" * 30]
        if h.date:
            lines.append(f"date    : {h.date}")
        if h.summary:
            lines.append(f"summary : {h.summary}")
        if h.next_steps:
            lines.append("next steps:")
            for l in h.next_steps.splitlines():
                stripped = l.strip()
                if stripped:
                    lines.append(f"  · {stripped.lstrip('- ')}")
        if h.blockers:
            first_blocker = h.blockers.splitlines()[0].strip().lstrip('- ')
            lines.append(f"blockers: {first_blocker}")

    if result.warning:
        lines += ["", f"Note: {result.warning}"]

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        result = run_doctor(args.root)
        if getattr(args, "as_json", False):
            print(format_doctor_json(result))
        else:
            print(format_doctor(result))
        return 0 if result.ok else 1

    if args.command == "map":
        from .codemap import run_map
        result = run_map(args.root, output=args.output, include_private=args.include_private)
        print(f"Code map written to: {result.output_path}")
        print(f"  {result.file_count} file(s) · {result.symbol_count} symbol(s) indexed")
        return 0

    if args.command == "resume":
        from .resume import run_resume
        result = run_resume(args.root)
        print(format_resume(result))
        return 0 if result.next_step else 1

    if args.command == "install-agents":
        modes = [args.force, args.upgrade, args.docs_only]
        if sum(bool(m) for m in modes) > 1:
            parser.error("--force, --upgrade, and --docs-only are mutually exclusive.")
        from .install_agents import run_install_agents
        try:
            result = run_install_agents(
                args.root,
                ref=args.ref,
                repo=args.repo,
                force=args.force,
                upgrade=args.upgrade,
                docs_only=args.docs_only,
                track=args.track,
                install_awt=args.install_awt,
            )
        except RuntimeError as exc:
            print(f"ERROR: {exc}", flush=True)
            return 1
        action = "Upgraded" if result.upgraded else "Installed"
        print(f"AI GovernanceKit install-agents")
        print(f"{action} {len(result.paths_installed)} path(s) into: {result.target}")
        for p in result.paths_installed:
            print(f"  {p}")
        if result.migrated:
            print("Migrated legacy docs/ layout to .docs/:")
            for note in result.migration_notes:
                print(f"  {note}")
        if result.gitignore_updated:
            docs_state = "tracked in git" if result.track_kit_docs else "gitignored"
            print(f".gitignore updated: {result.gitignore_path} (.docs/ {docs_state})")
        if result.awt_message:
            label = "awt" if result.awt_installed else "awt (manual step needed)"
            for line in result.awt_message.splitlines():
                print(f"{label}: {line}")
        return 0

    if args.command == "configure":
        from .configure import parse_set_pairs, run_configure, run_configure_identity
        from .identity import ALL_FIELDS
        try:
            preset = parse_set_pairs(args.set_pairs)
        except ValueError as exc:
            parser.error(str(exc))
        result = run_configure(args.root, preset=preset)
        print("AI GovernanceKit configure")
        if not result.found_tokens:
            print("No kit placeholders found — nothing to configure.")
        elif result.changed_files:
            print(f"Filled {len(result.values)} variable(s) in {len(result.changed_files)} file(s):")
            for p in result.changed_files:
                print(f"  {p}")
        else:
            print("No values applied.")
        if result.unfilled:
            print("Still unfilled: " + ", ".join(f"[{t}]" for t in result.unfilled))

        # ── host identity ──────────────────────────────────────────────────
        identity_preset = {f: getattr(args, f) for f in ALL_FIELDS}
        identity_flags_given = any(v is not None for v in identity_preset.values())
        interactive = None if identity_flags_given is False else False
        id_result = run_configure_identity(
            args.root, preset=identity_preset, interactive=interactive
        )
        if id_result.saved:
            print(f"Host identity saved: {id_result.path} (gitignored)")
        elif id_result.missing_required:
            missing = ", ".join(id_result.missing_required)
            if identity_flags_given:
                # The user explicitly tried to set identity but left fields out → error.
                print(
                    "ERROR: host identity incomplete — missing required field(s): "
                    + missing
                    + "\n  provide via --operator-name/--host-id/--instance-path "
                    "(or run interactively)."
                )
                return 1
            # No identity flags were given — this invocation is about kit placeholders
            # (e.g. `configure --set OPERATOR_NAME=...`). Don't fail the command just
            # because host identity isn't configured yet; advise and fall through so the
            # exit code reflects whether the placeholder fill succeeded.
            print(
                "Note: host identity not configured yet (missing: "
                + missing
                + "). Run `configure` interactively or pass "
                "--operator-name/--host-id/--instance-path to set it."
            )

        placeholders_ok = not result.unfilled
        return 0 if placeholders_ok else 1

    parser.error(f"unknown command: {args.command}")
    return 2
