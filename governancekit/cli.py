from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .doctor import DoctorResult, run_doctor
from .context import ContextError, build_context, format_context
from .path_safety import UnsafePathError


_ROOT_HELP_EPILOG = """Start here:
  governancekit --root /project install-agents
  governancekit --root /project doctor
  governancekit --root /project resume

Use --root before the command to target another project. It defaults to the current directory.

Advanced commands:
  configure              Fill kit placeholders and local host identity.
  configure-project      Inspect or edit project configuration directly.
  config-session         Run the resumable granular configuration workflow.
  classify-change        Record an architectural classification.
  context                Inspect, build, or prune deterministic task context.
  remove-agents          Plan or apply conservative kit de-adoption.
  bootstrap-issue        Create local issue artifacts.
  install-hooks          Install optional local Git hooks.
  voice-integration      Inspect optional voice integration.

Use `governancekit <command> -h` for a command's full help, including advanced commands."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="governancekit",
        description="Governed project adoption and day-to-day readiness checks.",
        epilog=_ROOT_HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root to inspect. Defaults to the current directory.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        dest="show_version",
        help="Show GovernanceKit, default AI-Agents, and project AI-Agents versions.",
    )

    subparsers = parser.add_subparsers(dest="command")

    doctor_parser = subparsers.add_parser(
        "doctor", help="Validate required governance files and readiness gates."
    )
    doctor_parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output results as JSON (useful for CI scripts).",
    )

    discover_parser = subparsers.add_parser(
        "discover",
        help="Inspect a repository read-only and report whether it looks new or existing.",
    )
    discover_parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output the discovery report as JSON.",
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

    context_parser = subparsers.add_parser(
        "context", help="Advanced: deterministic task context tools (see below)."
    )
    context_commands = context_parser.add_subparsers(dest="context_command", required=True)
    for command in ("inspect", "build"):
        command_parser = context_commands.add_parser(command)
        command_parser.add_argument("--task", default="implementation")
        command_parser.add_argument("--risk", action="append", default=[], dest="risks")
        command_parser.add_argument("--issue", type=Path)
        command_parser.add_argument("--manifest", type=Path)
        command_parser.add_argument("--json", action="store_true", dest="as_json")
    context_commands.choices["build"].add_argument(
        "--telemetry", action="store_true", help="Append metadata-only JSONL telemetry."
    )
    telemetry_parser = context_commands.add_parser("telemetry")
    telemetry_commands = telemetry_parser.add_subparsers(
        dest="telemetry_command", required=True
    )
    prune_parser = telemetry_commands.add_parser("prune")
    prune_parser.add_argument("--manifest", type=Path)

    install_parser = subparsers.add_parser(
        "install-agents",
        help="Install AI-Agents kit (github.com/EDortta/AI-Agents) into the project.",
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
        "--migrate-content",
        action="store_true",
        help="Extract project-specific legacy agent contracts from .docs-migration-bak/ into docs/project-rules/.",
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
    install_parser.add_argument(
        "--skip-project-configuration",
        action="store_true",
        help="Do not offer the required-reading-driven scope interview after installation.",
    )
    adoption_mode = install_parser.add_mutually_exclusive_group()
    adoption_mode.add_argument("--quick", action="store_true", help="Apply high-confidence generated adoption defaults.")
    adoption_mode.add_argument("--review", action="store_true", help="Show the consolidated adoption proposal (interactive default).")
    adoption_mode.add_argument("--advanced", action="store_true", help="Use the granular configuration-session workflow.")
    install_parser.add_argument("--non-interactive", action="store_true", help="Never prompt; requires --accept-generated to apply generated policy.")
    install_parser.add_argument("--accept-generated", action="store_true", help="Explicitly accept generated overview and limits in non-interactive mode.")
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

    remove_parser = subparsers.add_parser(
        "remove-agents", help="Advanced: conservative kit de-adoption (see below).",
    )
    remove_commands = remove_parser.add_subparsers(dest="remove_command", required=True)
    remove_plan = remove_commands.add_parser("plan", help="Inspect provenance and write a reviewable plan.")
    remove_plan.add_argument("--json", dest="as_json", action="store_true")
    remove_plan.add_argument("--with-llm", action="store_true", help="Use the configured primary LLM to propose project-content extractions.")
    remove_plan.add_argument("--output", type=Path, help="Plan output below --root (default: .gk/remove-agents-plan.json).")
    remove_apply = remove_commands.add_parser("apply", help="Apply only manifest-verified removals after backup.")
    remove_apply.add_argument("--plan", type=Path, help="Reviewed plan below --root (default: .gk/remove-agents-plan.json).")
    remove_apply.add_argument("--json", dest="as_json", action="store_true")
    remove_apply.add_argument("--accept-project-extractions", action="store_true", help="Confirm review of every LLM-proposed extraction in the plan.")

    configure_parser = subparsers.add_parser(
        "configure", help="Advanced: placeholders and local host identity (see below).",
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

    project_parser = subparsers.add_parser(
        "configure-project", help="Advanced: direct project configuration (see below).",
    )
    project_commands = project_parser.add_subparsers(dest="project_command", required=True)
    for name in ("plan", "apply"):
        sub = project_commands.add_parser(name)
        sub.add_argument("--project-name")
        sub.add_argument("--domain", dest="domains", action="append", default=[])
        sub.add_argument("--capability", dest="capabilities", action="append", default=[])
        sub.add_argument("--agent", dest="agents", action="append", default=[])
        sub.add_argument(
            "--provider",
            dest="providers",
            action="append",
            default=[],
            metavar="NAME[:MODE[:CREDENTIAL_REF[:ROLE]]]",
            help="Provider spec. MODE is manual, env, or file-ref; ROLE is primary, fallback, or optional.",
        )
        sub.add_argument("--json", dest="as_json", action="store_true")
    project_commands.add_parser("show").add_argument(
        "--json", dest="as_json", action="store_true"
    )

    classify_parser = subparsers.add_parser(
        "classify-change", help="Advanced: architectural classification (see below).",
    )
    classify_commands = classify_parser.add_subparsers(
        dest="classification_command", required=True
    )
    for name in ("plan", "apply"):
        sub = classify_commands.add_parser(name)
        sub.add_argument("--summary", required=True)
        sub.add_argument("--label", dest="labels", action="append", default=[])
        sub.add_argument("--rationale", required=True)
        sub.add_argument("--domain", dest="domains", action="append", default=[])
        sub.add_argument("--capability", dest="capabilities", action="append", default=[])
        sub.add_argument("--compatibility", required=True)
        sub.add_argument("--residual-risk", default="not declared")
        sub.add_argument("--json", dest="as_json", action="store_true")
    classify_commands.add_parser("show").add_argument(
        "--json", dest="as_json", action="store_true"
    )

    bootstrap_parser = subparsers.add_parser(
        "bootstrap-issue", help="Advanced: local issue scaffolding (see below).",
    )
    bootstrap_parser.add_argument("--epic-number", required=True, metavar="NNN")
    bootstrap_parser.add_argument("--epic-title", required=True)
    bootstrap_parser.add_argument("--task-title", required=True)
    bootstrap_parser.add_argument("--owner", default="operator")
    bootstrap_parser.add_argument("--related-commit", default="planned")

    session_parser = subparsers.add_parser(
        "config-session", help="Advanced: resumable granular configuration (see below).",
    )
    session_commands = session_parser.add_subparsers(dest="session_command", required=True)
    start_parser = session_commands.add_parser("start")
    start_parser.add_argument("--project-name")
    start_parser.add_argument("--domain", dest="domains", action="append", default=[])
    start_parser.add_argument("--capability", dest="capabilities", action="append", default=[])
    start_parser.add_argument("--agent", dest="agents", action="append", default=[])
    start_parser.add_argument(
        "--provider",
        dest="providers",
        action="append",
        default=[],
        metavar="NAME[:MODE[:CREDENTIAL_REF[:ROLE]]]",
    )
    start_parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run the required-reading-driven project scope interview.",
    )
    start_parser.add_argument(
        "--credentials-allow-symlinks",
        action="store_true",
        help="Allow credential-file symlinks below .credentials/ for this interactive interview.",
    )
    start_parser.add_argument("--json", dest="as_json", action="store_true")
    approve_parser = session_commands.add_parser("approve")
    approve_parser.add_argument("--approval", required=True)
    approve_parser.add_argument("--json", dest="as_json", action="store_true")
    session_commands.add_parser("show").add_argument("--json", dest="as_json", action="store_true")
    session_commands.add_parser("apply")

    hooks_parser = subparsers.add_parser(
        "install-hooks", help="Advanced: optional local Git hooks (see below).",
    )
    hooks_parser.add_argument("--hook-type", default="pre-commit")
    hooks_parser.add_argument("--force", action="store_true")
    hooks_parser.add_argument("--json", dest="as_json", action="store_true")

    voice_parser = subparsers.add_parser(
        "voice-integration", help="Advanced: optional voice integration (see below).",
    )
    voice_commands = voice_parser.add_subparsers(dest="voice_command", required=True)
    voice_commands.add_parser("detect").add_argument("--json", dest="as_json", action="store_true")

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
        message_lines = check.message.splitlines() or [""]
        if len(message_lines) == 1:
            lines.append(f"[{marker}] {check.name}: {message_lines[0]}")
            continue
        lines.append(f"[{marker}] {check.name}:")
        lines.extend(f"  {line}" if line else "" for line in message_lines)
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


def format_discovery_json(result) -> str:
    return json.dumps(result.as_dict(), sort_keys=True, ensure_ascii=False)


def format_project_config_json(result) -> str:
    return json.dumps(result.as_dict(), sort_keys=True, ensure_ascii=False)


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

    if args.show_version:
        from .version import format_version, get_version_info

        print(format_version(get_version_info(args.root)))
        return 0
    if args.command is None:
        parser.print_help()
        print("\ngovernancekit: error: a command is required")
        return 2

    if args.command == "context":
        if args.context_command == "telemetry":
            from .context import prune_telemetry

            try:
                removed = prune_telemetry(args.root, args.manifest)
            except ContextError as exc:
                print(f"Context error: {exc}")
                return 2
            print(f"Telemetry entries pruned: {removed}")
            return 0
        try:
            result = build_context(
                args.root,
                args.task,
                risks=args.risks,
                issue=args.issue,
                manifest_path=args.manifest,
                write_telemetry=getattr(args, "telemetry", False),
                strict=args.context_command == "build",
            )
        except ContextError as exc:
            if args.as_json:
                print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
            else:
                print(f"Context error: {exc}")
            return 2
        if args.as_json:
            print(json.dumps(result.as_dict(include_content=args.context_command == "build"),
                             sort_keys=True, ensure_ascii=False))
        elif args.context_command == "build":
            print(result.content)
        else:
            print(format_context(result))
        return 1 if result.exceeded or result.hard_violations else 0

    if args.command == "doctor":
        result = run_doctor(args.root)
        if getattr(args, "as_json", False):
            print(format_doctor_json(result))
        else:
            print(format_doctor(result))
        return 0 if result.ok else 1

    if args.command == "discover":
        from .discover import format_discovery, run_discover

        result = run_discover(args.root)
        if getattr(args, "as_json", False):
            print(format_discovery_json(result))
        else:
            print(format_discovery(result))
        return 0

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
        print(f"AI GovernanceKit {__version__} · install-agents")
        from .install_agents import run_install_agents
        try:
            result = run_install_agents(
                args.root,
                ref=args.ref,
                repo=args.repo,
                force=args.force,
                upgrade=args.upgrade,
                docs_only=args.docs_only,
                migrate_content=args.migrate_content,
                track=args.track,
                install_awt=args.install_awt,
            )
        except RuntimeError as exc:
            print(f"ERROR: {exc}", flush=True)
            return 1
        action = "Upgraded" if result.upgraded else "Installed"
        print(f"{action} {len(result.paths_installed)} path(s) into: {result.target}")
        for p in result.paths_installed:
            print(f"  {p}")
        if result.preserved_paths:
            print(
                f"Preserved {len(result.preserved_paths)} project-authored file(s) "
                "inside kit directories (not shipped by this kit version):"
            )
            for p in result.preserved_paths:
                print(f"  kept: {p}")
        if result.overwritten_edits:
            print(
                f"Replaced {len(result.overwritten_edits)} kit file(s) you had edited "
                "by hand — your version was stashed under .gk/overwritten/:"
            )
            for p in result.overwritten_edits:
                print(f"  stashed: {p}")
            print(
                "  Kit files are kit-owned. Move lasting project rules into your own "
                "files so they are preserved instead of stashed."
            )
        if result.upgraded and not result.had_state:
            print(
                "Note: no kit state existed before this run, so nothing was deleted. "
                "This run wrote one; later upgrades can retire files the kit drops."
            )
        if result.migrated:
            print("Migrated legacy docs/ layout to .docs/:")
            for note in result.migration_notes:
                print(f"  {note}")
        if result.gitignore_updated:
            docs_state = "tracked in git" if result.track_kit_docs else "gitignored"
            print(f".gitignore updated: {result.gitignore_path} (.docs/ {docs_state})")
        if result.awt_message:
            for line in result.awt_message.splitlines():
                print(f"awt: {line}")
        if args.upgrade:
            from .adoption import detect_project_drift
            drift = detect_project_drift(args.root)
            if drift:
                print("Project drift detected (advisory; accepted documents were not changed):")
                for item in drift:
                    print(f"  - {item}")
        if not args.docs_only:
            from .identity import load_identity

            identity = load_identity(args.root)
            if identity is None or identity.missing_required():
                root_command = shlex.quote(str(args.root.resolve()))
                print("Next required local setup (per host/checkout):")
                print(f"  governancekit --root {root_command} configure")
        if not args.docs_only and not args.skip_project_configuration:
            if args.non_interactive and not args.accept_generated:
                print("Adoption proposal not applied: --non-interactive requires --accept-generated.")
            elif not args.advanced:
                from .adoption import (
                    apply_adoption_proposal,
                    build_adoption_proposal,
                    configured_adoption_provider,
                    format_adoption_proposal,
                    provider_label,
                )
                proposal = build_adoption_proposal(args.root)
                if args.non_interactive or args.quick:
                    written = apply_adoption_proposal(proposal)
                    print("Generated adoption applied: " + (", ".join(written) or "existing project documents preserved"))
                elif sys.stdin.isatty():
                    provider = configured_adoption_provider(args.root)
                    if provider:
                        answer = input(
                            "Use configured LLM provider "
                            f"{provider_label(provider)} to enrich this proposal? [y/N] "
                        ).strip().lower()
                        if answer in {"y", "yes"}:
                            proposal = build_adoption_proposal(args.root, enrich_with_llm=True)
                    print(format_adoption_proposal(proposal))
                    if input("Apply these suggestions? [Y/n] ").strip().lower() not in {"n", "no"}:
                        written = apply_adoption_proposal(proposal)
                        print("Generated adoption applied: " + (", ".join(written) or "existing project documents preserved"))
                else:
                    print(format_adoption_proposal(proposal))
                    print("Run again with --non-interactive --accept-generated to apply it.")
            elif sys.stdin.isatty():
                answer = input("Review project scope now? [Y/n] ").strip().lower()
                if answer not in {"n", "no"}:
                    from .config_session import format_config_session, start_config_session
                    from .scope_conversation import run_scope_conversation

                    try:
                        conversation = run_scope_conversation(
                            args.root,
                            allow_project_credential_symlinks=True,
                        )
                    except RuntimeError as exc:
                        print(f"ERROR: {exc}")
                        return 1
                    try:
                        session = start_config_session(
                            args.root,
                            project_name=conversation.project_name,
                            domains=conversation.domains,
                            capabilities=conversation.capabilities,
                            agents=conversation.agents,
                            provider_configs=conversation.providers,
                            selected_agent=conversation.selected_agent,
                            capability_domains=conversation.capability_domains,
                            required_reading=conversation.required_reading,
                            scope_summary=conversation.scope_summary,
                        )
                    except ValueError as exc:
                        print(f"ERROR: {exc}")
                        return 1
                    print(format_config_session(session, args.root))
            else:
                root_command = shlex.quote(str(args.root.resolve()))
                print(f"Run: governancekit --root {root_command} config-session start --interactive to review project scope.")
        return 0

    if args.command == "remove-agents":
        from .remove_agents import (
            apply_removal_plan,
            build_removal_plan,
            format_removal_plan,
            load_removal_plan,
            write_removal_plan,
        )
        try:
            if args.remove_command == "plan":
                plan = build_removal_plan(args.root, with_llm=args.with_llm)
                output = write_removal_plan(args.root, plan, args.output)
                payload = plan.as_dict() | {"plan_path": str(output)}
                print(json.dumps(payload, sort_keys=True, ensure_ascii=False) if args.as_json else format_removal_plan(plan) + f"\nPlan written: {output}")
                return 0
            plan = load_removal_plan(args.root, args.plan)
            result = apply_removal_plan(args.root, plan, accept_project_extractions=args.accept_project_extractions)
        except (OSError, ValueError, UnsafePathError) as exc:
            print(f"ERROR: {exc}")
            return 1
        payload = {"backup_dir": str(result.backup_dir), "removed": result.removed, "preserved": result.preserved, "extracted": result.extracted}
        if args.as_json:
            print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
        else:
            print("AI GovernanceKit remove-agents apply")
            print(f"Backup: {result.backup_dir}")
            for item in result.removed:
                print(f"  removed: {item}")
            for item in result.extracted:
                print(f"  extracted: {item}")
            if not result.removed:
                print("  no files were eligible for automatic removal")
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

    if args.command == "configure-project":
        from .project_config import (
            apply_project_config_plan,
            build_project_config_plan,
            format_project_config_plan,
            load_project_config,
            parse_provider_specs,
            render_project_config_markdown,
        )

        if args.project_command == "show":
            current = load_project_config(args.root)
            if current is None:
                print("No project configuration found.")
                return 1
            if getattr(args, "as_json", False):
                print(json.dumps(current.as_dict(), sort_keys=True, ensure_ascii=False))
            else:
                print(render_project_config_markdown(current).rstrip())
            return 0

        try:
            parse_provider_specs(args.providers)
        except ValueError as exc:
            parser.error(str(exc))

        plan = build_project_config_plan(
            args.root,
            project_name=args.project_name,
            domains=args.domains,
            capabilities=args.capabilities,
            agents=args.agents,
            provider_names=args.providers,
        )
        if args.project_command == "plan":
            if getattr(args, "as_json", False):
                print(format_project_config_json(plan))
            else:
                print(format_project_config_plan(plan))
            return 0

        written = apply_project_config_plan(plan)
        print("AI GovernanceKit configure-project apply")
        for rel in written:
            print(f"  wrote: {rel}")
        return 0

    if args.command == "classify-change":
        from .classification import (
            build_change_classification,
            format_change_classification,
            load_change_classification,
            save_change_classification,
        )

        if args.classification_command == "show":
            current = load_change_classification(args.root)
            if current is None:
                print("No change classification found.")
                return 1
            if getattr(args, "as_json", False):
                print(json.dumps(current.as_dict(), sort_keys=True, ensure_ascii=False))
            else:
                print(format_change_classification(current))
            return 0

        classification = build_change_classification(
            summary=args.summary,
            labels=args.labels,
            rationale=args.rationale,
            affected_domains=args.domains,
            affected_capabilities=args.capabilities,
            compatibility=args.compatibility,
            residual_risk=args.residual_risk,
        )
        if args.classification_command == "plan":
            if getattr(args, "as_json", False):
                print(json.dumps(classification.as_dict(), sort_keys=True, ensure_ascii=False))
            else:
                print(format_change_classification(classification))
            return 0

        rel = save_change_classification(args.root, classification)
        print("AI GovernanceKit classify-change apply")
        print(f"  wrote: {rel}")
        return 0

    if args.command == "bootstrap-issue":
        from .issue_bootstrap import bootstrap_issue

        try:
            result = bootstrap_issue(
                args.root,
                epic_number=args.epic_number,
                epic_title=args.epic_title,
                task_title=args.task_title,
                owner=args.owner,
                related_commit=args.related_commit,
            )
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            return 1
        print("AI GovernanceKit bootstrap-issue")
        print(f"  epic: {result.epic_dir}")
        for rel in result.files:
            print(f"  wrote: {rel}")
        return 0

    if args.command == "config-session":
        from .config_session import (
            apply_config_session,
            format_config_session,
            grant_config_approval,
            load_config_session,
            start_config_session,
        )
        from .project_config import parse_provider_specs

        if args.session_command == "show":
            session = load_config_session(args.root)
            if session is None:
                print("No configuration session found.")
                return 1
            if getattr(args, "as_json", False):
                print(json.dumps(session.as_dict(), sort_keys=True, ensure_ascii=False))
            else:
                print(format_config_session(session, args.root))
            return 0

        if args.session_command == "start":
            conversation = None
            if args.interactive:
                if not sys.stdin.isatty():
                    print("ERROR: --interactive requires a terminal.")
                    return 1
                if any([args.project_name, args.domains, args.capabilities, args.agents, args.providers]):
                    parser.error("--interactive cannot be combined with project scope flags")
                from .scope_conversation import run_scope_conversation

                try:
                    conversation = run_scope_conversation(
                        args.root,
                        allow_project_credential_symlinks=args.credentials_allow_symlinks,
                    )
                except RuntimeError as exc:
                    print(f"ERROR: {exc}")
                    return 1
            if conversation is None:
                try:
                    parse_provider_specs(args.providers)
                except ValueError as exc:
                    parser.error(str(exc))
            try:
                session = start_config_session(
                    args.root,
                    project_name=conversation.project_name if conversation else args.project_name,
                    domains=conversation.domains if conversation else args.domains,
                    capabilities=conversation.capabilities if conversation else args.capabilities,
                    agents=conversation.agents if conversation else args.agents,
                    provider_names=args.providers if conversation is None else None,
                    provider_configs=conversation.providers if conversation else None,
                    selected_agent=conversation.selected_agent if conversation else None,
                    capability_domains=conversation.capability_domains if conversation else None,
                    required_reading=conversation.required_reading if conversation else None,
                    scope_summary=conversation.scope_summary if conversation else None,
                )
            except ValueError as exc:
                print(f"ERROR: {exc}")
                return 1
            if getattr(args, "as_json", False):
                print(json.dumps(session.as_dict(), sort_keys=True, ensure_ascii=False))
            else:
                print(format_config_session(session, args.root))
            return 0

        if args.session_command == "approve":
            try:
                session = grant_config_approval(args.root, args.approval)
            except RuntimeError as exc:
                print(f"ERROR: {exc}")
                return 1
            if getattr(args, "as_json", False):
                print(json.dumps(session.as_dict(), sort_keys=True, ensure_ascii=False))
            else:
                print(format_config_session(session, args.root))
            return 0

        try:
            written = apply_config_session(args.root)
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            return 1
        print("AI GovernanceKit config-session apply")
        for rel in written:
            print(f"  wrote: {rel}")
        return 0

    if args.command == "install-hooks":
        from .hooks import install_hook

        try:
            result = install_hook(args.root, hook_type=args.hook_type, force=args.force)
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            return 1
        if getattr(args, "as_json", False):
            print(json.dumps(result.as_dict(), sort_keys=True, ensure_ascii=False))
        else:
            print("AI GovernanceKit install-hooks")
            print(f"  hook: {result.hook_type}")
            print(f"  path: {result.path}")
            print(f"  replaced: {'yes' if result.replaced else 'no'}")
        return 0

    if args.command == "voice-integration":
        from .voice import detect_voice_integration, format_voice_integration

        result = detect_voice_integration(args.root)
        if getattr(args, "as_json", False):
            print(json.dumps(result.as_dict(), sort_keys=True, ensure_ascii=False))
        else:
            print(format_voice_integration(result))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2
