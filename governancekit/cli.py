from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from . import __version__
from .doctor import DoctorResult, run_doctor

# Host-identity fields that answer a kit placeholder outright. Deliberately narrow:
# only pairs whose meaning is the same on both sides belong here, because a wrong
# guess writes itself into every managed file without asking. `instance_path` is NOT
# mapped to `PROJECT_ROOT` — the two are near-synonyms and that is exactly the kind of
# resemblance worth confirming with the operator before substituting it everywhere.
_IDENTITY_BACKED_PLACEHOLDERS: dict[str, str] = {
    "operator_name": "OPERATOR_NAME",
}
from .context import ContextError, build_context, format_context
from .path_safety import UnsafePathError, UnsafeRootError, assert_governable_root


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
  migrate-activity-monitor  Migrate the legacy Sync activity monitor to XDG state.
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

    concurrency_parser = subparsers.add_parser(
        "concurrency",
        help="Report how many worktrees and unmerged branches are open in this repository.",
    )
    concurrency_parser.add_argument(
        "--json", dest="as_json", action="store_true", help="Output the survey as JSON."
    )
    concurrency_parser.add_argument(
        "--closing",
        action="store_true",
        help="Phrase the report for session close: what stays open for the next day.",
    )

    council_parser = subparsers.add_parser(
        "council",
        help="Report or record the adversarial council required before a delivery commit.",
    )
    council_parser.add_argument(
        "--json", dest="as_json", action="store_true", help="Output the gate state as JSON."
    )
    council_parser.add_argument(
        "--record", type=Path, default=None,
        help="Record a council round from a JSON file, bound to the staged diff.",
    )
    council_parser.add_argument(
        "--waive", default=None, metavar="REASON",
        help="Clear the gate for this staged diff, recording why. A reason is required.",
    )
    council_parser.add_argument(
        "--requested", action="store_true",
        help="Treat this delivery as one the operator asked a council for (council.md §4).",
    )

    author_parser = subparsers.add_parser(
        "author-context",
        help="Draft or review docs/software-overview.md and docs/limits.md with the configured LLM.",
    )
    author_parser.add_argument(
        "--json", dest="as_json", action="store_true", help="Output the plan and proposals as JSON."
    )
    author_parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Report what would be drafted or reviewed, and stop. Calls no provider.",
    )
    author_parser.add_argument(
        "--yes",
        dest="assume_yes",
        action="store_true",
        help="Accept the proposals without prompting. Only for a non-interactive rerun of a reviewed result.",
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

    monitor_parser = subparsers.add_parser(
        "migrate-activity-monitor",
        help="Merge legacy agent-status.json copies into XDG state without deleting them.",
    )
    monitor_parser.add_argument(
        "--legacy-path", type=Path, default=None,
        help="Single legacy monitor path (default: every known legacy location).",
    )
    monitor_parser.add_argument(
        "--state-home", type=Path, default=None,
        help="XDG state-home override (default: $XDG_STATE_HOME or ~/.local/state).",
    )
    monitor_parser.add_argument(
        "--include-log", action="store_true",
        help="Also move ~/Sync/agent-log.md to XDG state (refused if a canonical log exists).",
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
    install_parser.add_argument(
        "--allow-unverified",
        dest="allow_unverified",
        action="store_true",
        help=(
            "Install a ref for which no checksum is pinned. The download's own "
            "error message has named this flag since the checksum gate was "
            "written, and the guide documents it — but the parser never accepted "
            "it, so the only remedy the refusal offered died with 'unrecognized "
            "arguments'. Off by default; the unverified install warns on stderr."
        ),
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
    remove_apply.add_argument(
        "--purge-state", dest="purge_state", action="store_true",
        help="Also eliminate the kit's state files: the LOCAL identity halves "
             "(manifest.override.json and the legacy pair) AND the shared "
             ".gk/manifest.json — kit residue, tracked, so it is recoverable "
             "from git and its deletion shows in git status. Explicit on "
             "purpose; the backup and the git history are not covered.",
    )

    mail_parser = subparsers.add_parser(
        "mail", help="Send from, and review, the operator's own mailbox.",
    )
    mail_commands = mail_parser.add_subparsers(dest="mail_command")
    mail_setup = mail_commands.add_parser(
        "setup", help="Show how to produce a credential for an address, and record it.",
    )
    mail_setup.add_argument("address", help="the operator's email address")
    mail_setup.add_argument(
        "--write", action="store_true",
        help="record the address in .credentials/identity.json (the token is never written)",
    )
    mail_send = mail_commands.add_parser("send", help="Send one message.")
    mail_send.add_argument("--to", action="append", default=[], help="Repeatable.")
    mail_send.add_argument("--subject", default="")
    mail_send.add_argument("--body", default="", help="Message text, or - to read stdin.")
    mail_send.add_argument(
        "--dry-run", action="store_true",
        help="render and validate without connecting — email cannot be recalled",
    )
    mail_inbox = mail_commands.add_parser("inbox", help="List recent headers, never bodies.")
    mail_inbox.add_argument("--limit", type=int, default=10)
    mail_inbox.add_argument("--mailbox", default="INBOX")

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
    configure_parser.add_argument(
        "--unset",
        dest="unset_keys",
        action="append",
        default=[],
        metavar="KEY",
        help="Eliminate a stored answer from the kit's state files. Repeatable. "
             "Files already rendered with the value, and the git history, are "
             "not touched.",
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
    if getattr(result, "concurrency", None) is not None:
        from .concurrency import format_survey

        rendered = format_survey(result.concurrency)
        if rendered:
            lines += ["", *rendered.splitlines()]

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


def _run_context(args) -> int:
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


def _run_doctor(args) -> int:
    result = run_doctor(args.root)
    if getattr(args, "as_json", False):
        print(format_doctor_json(result))
    else:
        print(format_doctor(result))
    return 0 if result.ok else 1


def _run_discover(args) -> int:
    from .discover import format_discovery, run_discover

    result = run_discover(args.root)
    if getattr(args, "as_json", False):
        print(format_discovery_json(result))
    else:
        print(format_discovery(result))
    return 0


def _run_map(args) -> int:
    from .codemap import run_map
    result = run_map(args.root, output=args.output, include_private=args.include_private)
    print(f"Code map written to: {result.output_path}")
    print(f"  {result.file_count} file(s) · {result.symbol_count} symbol(s) indexed")
    return 0


def _run_resume(args) -> int:
    from .resume import run_resume
    result = run_resume(args.root)
    print(format_resume(result))
    return 0 if result.next_step else 1


def _run_migrate_activity_monitor(args) -> int:
    from .activity_monitor import (
        ActivityMonitorError,
        migrate_activity_log,
        migrate_activity_monitor,
    )

    try:
        result = migrate_activity_monitor(
            source=args.legacy_path,
            state_home=args.state_home,
        )
        log = migrate_activity_log(state_home=args.state_home) if args.include_log else None
    except ActivityMonitorError as error:
        print(f"Activity monitor migration failed: {error}")
        return 1
    action = "updated" if result.wrote_destination else "already current"
    print(f"Activity monitor {action}: {result.destination}")
    sources = ", ".join(str(path) for path in result.sources) or "none found"
    print(
        f"  imported {result.imported_sessions} session(s); "
        f"{result.duplicate_sessions} duplicate(s); legacy source(s) preserved: {sources}"
    )
    if log is not None:
        state = "moved to" if log.moved else "not moved"
        print(f"Activity log {state} {log.destination} ({log.reason})")
    return 0


def _run_install_agents(args) -> int:
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
            allow_unverified=args.allow_unverified,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", flush=True)
        return 1
    action = "Upgraded" if result.upgraded else "Installed"
    print(f"{action} {len(result.paths_installed)} path(s) into: {result.target}")
    for p in result.paths_installed:
        print(f"  {p}")
    if result.seeded_paths:
        # Say it in the operator's terms: what was added, and — the part that matters
        # after this ran `rmtree` for months — what was left exactly as it was.
        print(
            f"Seeded {len(result.seeded_paths)} missing file(s) into .credentials/: "
            + ", ".join(Path(p).name for p in result.seeded_paths)
        )
    if result.preserved_paths:
        # Credential paths are counted, never named. The manifest filter exists because
        # "the paths alone say which providers a programmer holds keys for"; printing
        # them to stdout puts the same list in every install log that gets pasted into
        # an issue or a CI job. Found by the council's second-caller lens, against the
        # comment I had written one screen away.
        credentials = [p for p in result.preserved_paths if p.startswith(f"{Path('.credentials')}/")]
        others = [p for p in result.preserved_paths if p not in credentials]
        if others:
            print(
                f"Preserved {len(others)} project-authored file(s) "
                "inside kit directories (not shipped by this kit version):"
            )
            for p in others:
                print(f"  kept: {p}")
        if credentials:
            print(
                f"Kept {len(credentials)} existing file(s) in .credentials/ — your "
                "tokens, identity and provider keys were not touched."
            )
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
    if result.backed_up:
        print(
            f"Backed up {len(result.backed_up)} replaced file(s) under "
            ".gk/pre-upgrade/ — cleared at the start of the next upgrade."
        )
    if result.drifted_paths:
        from .doctor import _WITHDRAWN_CITATIONS

        print(
            f"Kept {len(result.drifted_paths)} protected file(s) that differ from what "
            "this kit installed — the new version is beside them, unmerged:"
        )
        for p in result.drifted_paths:
            print(f"  kept: {p} -> new version at {p}.kit-new")
        print(
            "  Merge what you want, then delete the .kit-new file. Until then this "
            "project keeps the older contract."
        )
        # "The older contract" is too mild for one specific body. A kept file that
        # still prescribes one operator's email transport is the rule that mis-sent
        # real material on 2026-08-04, and precedence means live agents follow the
        # kept file, not the .kit-new nobody merged. The shell installer says this;
        # the port said only the generic line, so the same target heard the danger
        # from one installer and not from the other.
        for p in result.drifted_paths:
            try:
                kept = (result.target / p).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if any(path in kept for path in _WITHDRAWN_CITATIONS):
                print(
                    f"  WARNING: the kept {p} still prescribes one operator's email "
                    "transport. That rule was WITHDRAWN (AI-Agents#5) — agents here "
                    "follow the withdrawn rule until you merge."
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

        print(
            "Analyzing project files for upgrade drift; this can take several "
            "minutes in a large project..."
        )
        drift = detect_project_drift(
            args.root,
            on_top_level_directory=lambda directory: print(f"  scanning: {directory}"),
        )
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
            # The two readiness documents are authored here, by the same step the
            # `author-context` command runs: discovery, then the project's own README
            # and sources through a provider the operator consents to, then the
            # operator confirming each document. Adoption used to own a second
            # generator that wrote both files itself and stamped them ready — a
            # machine opening the Start Gate over text nobody had read.
            print(
                "Preparing the project context from project files; this "
                "can take several minutes in a large project..."
            )
            scan = lambda directory: print(f"  scanning: {directory}")  # noqa: E731
            if args.non_interactive or args.quick:
                # No prompting, so no consent, so no provider call. Deterministic and
                # complete, with the flags left for a human.
                _deterministic_context(args.root.resolve(), on_top_level_directory=scan)
            elif sys.stdin.isatty():
                _context_step(args, deterministic_fallback=True, on_top_level_directory=scan)
            else:
                # Piped, and no flag asking for anything to be applied. The gate 20
                # lines up refuses `--non-interactive` without `--accept-generated`;
                # writing here anyway would let the same run bypass it by simply not
                # passing `--non-interactive`. Two branches of one `if` must not
                # disagree about whether an unattended run may write.
                from .adoption import (
                    build_adoption_proposal,
                    configured_adoption_provider,
                    format_adoption_proposal,
                    format_provider_offer,
                )

                if configured_adoption_provider(args.root) is None:
                    print()
                    print(format_provider_offer(args.root.resolve()))
                print()
                print(format_adoption_proposal(
                    build_adoption_proposal(args.root, on_top_level_directory=scan)
                ))
                print(
                    "Nothing was written. Run again with --non-interactive "
                    "--accept-generated to apply it."
                )
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


def _run_remove_agents(args) -> int:
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
        result = apply_removal_plan(
            args.root, plan,
            accept_project_extractions=args.accept_project_extractions,
            purge_state=args.purge_state,
        )
    except (OSError, ValueError, UnsafePathError) as exc:
        print(f"ERROR: {exc}")
        return 1
    payload = {
        "backup_dir": str(result.backup_dir), "removed": result.removed,
        "preserved": result.preserved, "extracted": result.extracted,
        "purged": result.purged, "surviving_state": result.surviving_state,
        "personal_backups": result.personal_backups,
    }
    if args.as_json:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    else:
        print("AI GovernanceKit remove-agents apply")
        print(f"Backup: {result.backup_dir}")
        for item in result.removed:
            print(f"  removed: {item}")
        for item in result.extracted:
            print(f"  extracted: {item}")
        for item in result.purged:
            print(f"  state eliminated: {item}")
        if not result.removed:
            print("  no files were eligible for automatic removal")
        # AC-21 — said here, not in the library, so `--json` stays parseable.
        if result.personal_backups:
            print(
                "Note: the backup just written contains the operator's rendered "
                "data in: " + ", ".join(result.personal_backups)
                + f"\n  It lives in {result.backup_dir} and is kept until you "
                "delete it — nothing expires it."
            )
        if result.purged:
            print(
                "Not covered by --purge-state: the git history (a value ever "
                "committed stays in it) and the backup this run just wrote."
            )
        elif result.surviving_state:
            from .remove_agents import _PERSONAL_STATE_FILES

            described = dict(_PERSONAL_STATE_FILES)
            print("State that survives de-adoption and may carry the operator's data:")
            for rel in result.surviving_state:
                detail = described.get(rel, "backups written by remove-agents apply")
                print(f"  {rel} — {detail}")
            print(
                "  Eliminate with `remove-agents apply --purge-state`, or one "
                "value at a time with `configure --unset <TOKEN>`."
            )
    return 0


def _run_configure(args) -> int:
    from .configure import parse_set_pairs, run_configure, run_configure_identity
    from .identity import ALL_FIELDS, load_identity

    # AC-21 — eliminations first, and each one reported by WHERE it was removed
    # from. An `--unset` of a key stored nowhere is said in as many words: a
    # mistyped token reporting the same success as a real elimination is the
    # "output says one thing, disk says another" class this epic audits.
    if args.unset_keys:
        from .install_agents import unset_placeholder_values

        removed, unreadable = unset_placeholder_values(args.root, args.unset_keys)
        print("AI GovernanceKit configure --unset")
        for key, sources in removed.items():
            if sources:
                print(f"  eliminated {key} from: " + ", ".join(sources))
            elif unreadable:
                # "Not stored anywhere" would be a claim no one verified: a state
                # file is sitting there unreadable, and the value may be inside.
                print(
                    f"  not found in any READABLE state file: {key} — but see the "
                    "warning below."
                )
            else:
                print(f"  not stored anywhere: {key} (nothing to eliminate)")
        if unreadable:
            print(
                "  Warning: unreadable/corrupt state file(s) still on disk: "
                + ", ".join(unreadable)
                + "\n  A stored value may survive inside — inspect or delete "
                "them by hand; this command does not guess."
            )
        print(
            "  Files already rendered with a value, and the git history, are "
            "not touched by this command."
        )
        if not args.set_pairs and not any(
            getattr(args, f, None) for f in ALL_FIELDS
        ):
            return 0

    try:
        preset = parse_set_pairs(args.set_pairs)
    except ValueError as exc:
        # `parser` is not in scope here and never was: this handler raised
        # `NameError` instead of printing a usage error, so a mistyped `--set`
        # produced a chained traceback — with the operator's value inside it, because
        # the message used to interpolate the raw argument. A council's LGPD lens
        # measured a secret reaching stderr this way.
        print(f"governancekit configure: {exc}", file=sys.stderr)
        return 2

    # The operator's name is already known — the identity file holds it — but the
    # placeholder pass used to ignore it and ask again, and could only ask on a TTY.
    # Off a terminal that made `doctor`'s non-advisory "kit not configured" name a
    # remedy that provably did nothing: `configure` reported the token still unfilled
    # while the answer sat in a file it had written itself. Explicit `--set` still wins.
    stored = load_identity(args.root)
    if stored is not None:
        for field, token in _IDENTITY_BACKED_PLACEHOLDERS.items():
            value = str(getattr(stored, field, "") or "").strip()
            if value and token not in preset:
                preset[token] = value

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
        # Canonical `{{TOKEN}}` form. Issue #7 item 3 reconciled the syntax in the
        # installer and missed this line, so the one place that tells an operator what
        # to look for named a form no kit file contains — grep for it finds nothing.
        print("Still unfilled: " + ", ".join(f"{{{{{t}}}}}" for t in result.unfilled))

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


def _run_configure_project(args) -> int:
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


def _run_classify_change(args) -> int:
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


def _run_bootstrap_issue(args) -> int:
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


def _run_config_session(args) -> int:
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


def _run_install_hooks(args) -> int:
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


def _run_voice_integration(args) -> int:
    from .voice import detect_voice_integration, format_voice_integration

    result = detect_voice_integration(args.root)
    if getattr(args, "as_json", False):
        print(json.dumps(result.as_dict(), sort_keys=True, ensure_ascii=False))
    else:
        print(format_voice_integration(result))
    return 0



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

    try:
        assert_governable_root(args.root)
    except UnsafeRootError as exc:
        print(f"Unsafe --root: {exc}", file=sys.stderr)
        return 2

    handler = _COMMANDS.get(args.command)
    if handler is None:
        parser.error(f"unknown command: {args.command}")
        return 2
    return handler(args)

def _confirm(question: str, *, assume_yes: bool) -> bool:
    """Ask the operator. Non-interactive without --yes means no, never a silent yes."""
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        return False
    return input(f"{question} [y/N]: ").strip().lower() in {"y", "yes"}


def _deterministic_context(
    root: Path, *, on_top_level_directory=None, announce_provider_offer: bool = True
) -> int:
    """Write the two documents from discovery alone, and say what is still shut.

    The branch that keeps a project without a provider operable — the `[MANDATORY]`
    rule in AI-Agents `.docs/agents/credentials-operations.md`: "A project remains
    operable in manual mode even when no provider is configured yet." Nothing here
    calls out, and nothing here declares readiness.
    """
    from .adoption import (
        apply_adoption_proposal,
        build_adoption_proposal,
        configured_adoption_provider,
        format_provider_offer,
        format_readiness_warning,
    )

    # Say it here too, not only on the interactive branch. The claim that "three code
    # paths now speak" was true of one: `--quick`, `--non-interactive` and the piped
    # run all land here, and those are the paths a fleet install actually takes — the
    # ones where nobody is watching to ask. A scripted run that never mentions the
    # option is the same silence, just harder to notice.
    if announce_provider_offer and configured_adoption_provider(root) is None:
        print()
        print(format_provider_offer(root, about_to_write=True))
        print()

    proposal = build_adoption_proposal(root, on_top_level_directory=on_top_level_directory)
    applied = apply_adoption_proposal(proposal)
    for rel in applied.written:
        print(f"  wrote: {rel}")
    for rel, why in applied.preserved:
        print(f"  kept:  {rel} — {why}")
    warning = format_readiness_warning(applied.unconfirmed, root, written=applied.written)
    if warning:
        print()
        print(warning)
    return 0


def _context_step(
    args,
    *,
    deterministic_fallback: bool,
    on_top_level_directory=None,
) -> int:
    """Draft and confirm the two readiness documents. Shared by two commands.

    `author-context` calls it with ``deterministic_fallback=False``: that command
    promises an LLM, so a missing provider is an error (exit 2) rather than something
    quietly different. `install-agents` calls it with ``True``: adoption must complete
    without a provider, loudly but successfully.
    """
    from .adoption import configured_adoption_provider, format_provider_offer, provider_label
    from .context_authoring import (
        DESCRIPTION_ADVICE,
        DESCRIPTION_CANDIDATES,
        build_authoring_plan,
        confirm_document,
        draft_documents,
        is_kit_authored,
        review_documents,
    )
    from .discover import run_discover

    root = args.root.resolve()
    discovery = run_discover(root, on_top_level_directory)
    evidence = [*discovery.frameworks, *discovery.languages, *discovery.package_managers]
    plan = build_authoring_plan(root, evidence=evidence)
    assume_yes = getattr(args, "assume_yes", False)
    plan_only = getattr(args, "plan_only", False)

    if getattr(args, "as_json", False) and plan_only:
        print(json.dumps(plan.as_dict(), indent=2, sort_keys=True, ensure_ascii=False))
        return 0

    print("Context authoring plan:")
    for doc in plan.documents:
        print(f"  {doc.rel}: {doc.state.value} -> {doc.action}")

    if plan.needs_description_advice:
        print()
        print(DESCRIPTION_ADVICE.format(candidates=", ".join(DESCRIPTION_CANDIDATES)))
        print()
        if not _confirm("Continue without a project description?", assume_yes=assume_yes):
            if not deterministic_fallback:
                print("Stopped. Write the description first, then run this again.")
                return 0
            # Inside an install, "stopped" cannot mean "left with nothing": that is the
            # silence this delivery exists to remove. Write what discovery can prove,
            # leave the flags shut, and say both things.
            print(
                "Writing what discovery can prove for now — write the description, then "
                "run 'author-context' to redo these two documents properly."
            )
            return _deterministic_context(root, on_top_level_directory=on_top_level_directory)

    if plan_only:
        return 0
    if all(doc.action == "skip" for doc in plan.documents):
        print("Both documents are already marked ready; nothing to do.")
        return 0

    provider = configured_adoption_provider(root)
    if provider is None:
        if not deterministic_fallback:
            print(
                "No primary LLM provider is configured for this project. Run "
                f"'governancekit --root {root} config-session' to configure one, or write the "
                "documents by hand.",
                file=sys.stderr,
            )
            return 2
        print()
        print(format_provider_offer(root))
        print()
        return _deterministic_context(
            root, on_top_level_directory=on_top_level_directory,
            announce_provider_offer=False,
        )

    # A configured provider is not consent: the operator says yes each time, because
    # this sends the project's own description and sources to a third party.
    # Name what actually goes on the wire. A DRAFT sends the project's description and
    # the detected evidence; a REVIEW sends the document under review in full — and a
    # limits document is exactly where production hostnames and vault paths are
    # written. The prompt said "description" for both. Found in council round 2, with
    # the outbound payload captured.
    reviewed = [doc.rel for doc in plan.documents if doc.action == "review"]
    what = "this project's description and detected evidence"
    if reviewed:
        what += f", plus the full text of {', '.join(reviewed)}"
    if not _confirm(
        f"Send {what} to {provider_label(provider)}?", assume_yes=assume_yes
    ):
        print("Stopped; no provider was called.")
        if deterministic_fallback:
            print("Continuing without it — discovery is deterministic.")
            return _deterministic_context(root, on_top_level_directory=on_top_level_directory)
        return 0

    try:
        proposals = [*draft_documents(root, plan, provider), *review_documents(root, plan, provider)]
    except RuntimeError as exc:
        print(f"Context authoring failed: {exc}", file=sys.stderr)
        if deterministic_fallback:
            # A provider's failure is a pending item, not a failed installation
            # (docs/napkin-lessons.md, 2026-08-02).
            print("Falling back to deterministic discovery; no LLM result was applied.")
            return _deterministic_context(root, on_top_level_directory=on_top_level_directory)
        return 2

    if getattr(args, "as_json", False):
        print(json.dumps([p.as_dict() for p in proposals], indent=2, sort_keys=True, ensure_ascii=False))
        return 0

    exit_code = 0
    for proposal in proposals:
        print()
        if proposal.action == "review":
            print(f"Review of {proposal.rel} (your file is untouched):")
            if not proposal.findings:
                print("  nothing missing was identified.")
            for finding in proposal.findings:
                print(f"  - [{finding.section}] {finding.detail}")
            question = f"Accept {proposal.rel} as it stands and mark it ready?"
            content = None
            replaces_project_text = False
        else:
            print(f"Draft for {proposal.rel}:")
            print("\n".join(f"  {line}" for line in (proposal.content or "").splitlines()))
            # A draft REPLACES the file. The review branch says "your file is untouched";
            # this one said nothing, and under `--yes` there was no prompt at all — so a
            # document the project wrote could be overwritten wholesale with no stash and
            # no backup. `apply_adoption_proposal` has guarded this since it started using
            # `is_kit_authored`; this path, which writes the same two files, did not.
            # Length is a poor judge of authorship: a real overview whose lines read
            # `Stack: FastAPI, Postgres` classifies TEMPLATE, because those look like
            # metadata. Found by the council's migrator lens.
            existing = root / proposal.rel
            replaces_project_text = (
                existing.is_file()
                and not is_kit_authored(existing.read_text(encoding="utf-8", errors="replace"))
            )
            if replaces_project_text:
                print(f"  NOTE: {proposal.rel} already holds text this kit did not write.")
                print(f"        Accepting REPLACES it. A copy is kept at {proposal.rel}.pre-draft.")
            question = f"Accept this draft for {proposal.rel} and mark it ready?"
            content = proposal.content

        if replaces_project_text and not assume_yes and not sys.stdin.isatty():
            # No terminal, so no answer: never replace project text unasked.
            print(f"  skipped: {proposal.rel} holds project text and there is no terminal to ask.")
            exit_code = 1
            continue

        if _confirm(question, assume_yes=assume_yes):
            if replaces_project_text:
                backup = _keep_pre_draft_copy(root, proposal.rel)
                if backup:
                    print(f"  previous version kept at {backup}")
            confirm_document(root, proposal.rel, content=content)
            print(f"  accepted: {proposal.rel} is now ready.")
        else:
            saved = _save_proposal(root, proposal)
            if saved:
                print(f"  not accepted. The proposal is at {saved} — edit {proposal.rel} in your IDE.")
            else:
                print(f"  not accepted. Edit {proposal.rel} in your IDE, then set its flag yourself.")
            exit_code = 1

    # The verdict comes off disk. What the loop above believes it accepted is not
    # evidence about the file, and the previous flow reported success from exactly
    # that kind of belief.
    from .adoption import format_readiness_warning
    from .context_authoring import LIMITS_REL, OVERVIEW_REL, DocState, classify_document

    unconfirmed = [
        rel for rel in (OVERVIEW_REL, LIMITS_REL)
        if classify_document(root, rel) is not DocState.READY
    ]
    warning = format_readiness_warning(unconfirmed, root)
    if warning:
        print()
        print(warning)
    if deterministic_fallback:
        # An unconfirmed document is a pending item for the operator, not a failed
        # installation. `author-context` still reports 1 so a script can see it.
        return 0
    return exit_code


def _run_author_context(args) -> int:
    return _context_step(args, deterministic_fallback=False)


def _keep_pre_draft_copy(root: Path, rel: str) -> str | None:
    """Copy a project-authored document aside before a draft replaces it.

    The kit has a stash for exactly this situation on the installer side
    (`.gk/overwritten/`) and had nothing on the authoring side, where the operator is
    one `y` away from losing prose they wrote by hand.
    """
    import shutil

    from .path_safety import safe_path

    source = safe_path(root, root / rel)
    if not source.is_file():
        return None
    backup = safe_path(root, source.parent / (source.name + ".pre-draft"))
    if backup.exists():
        # One slot, silently reused: accepting a second draft overwrote the FIRST
        # backup, which held the operator's own prose — and the message still said a
        # copy was kept. The remedy `doctor` prints (lower the flag by hand, then
        # redraft) walks straight into it. Keep the oldest, which is the only copy the
        # kit did not write.
        return backup.relative_to(root).as_posix()
    try:
        shutil.copy2(source, backup)
    except OSError:
        return None
    return backup.relative_to(root).as_posix()


def _save_proposal(root: Path, proposal) -> str | None:
    """Keep a rejected draft where the operator can diff it. Reviews have no file."""
    if not proposal.content:
        return None
    from .path_safety import safe_path

    rel = f".gk/context-proposal/{Path(proposal.rel).name}"
    path = safe_path(root, root / rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(proposal.content, encoding="utf-8")
    return rel


def _run_concurrency(args) -> int:
    from .concurrency import (
        format_survey,
        format_winddown,
        load_winddown_config,
        survey_concurrency,
        winddown_state,
    )

    survey = survey_concurrency(args.root)
    hour, budget = load_winddown_config(args.root)
    state = winddown_state(datetime.now().time(), hour=hour, budget_minutes=budget)

    if getattr(args, "as_json", False):
        payload = {"concurrency": survey.as_dict(), "winddown": state.as_dict()}
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0

    if not survey.available:
        # Not a git repository: nothing to report, and nothing to complain about.
        return 0
    print(format_survey(survey, moment="close" if args.closing else "start"))
    print()
    print(format_winddown(state))
    return 0


def _run_mail(args) -> int:
    """Send and review from the operator's own mailbox.

    `sending-email.md` tells an agent to read the project's own email documentation for
    the transport — and no project had anywhere to write it down. This is that place.
    Every failure here prints something the operator can act on, and never the secret.
    """
    import json as _json

    from .mailbox import (
        MailboxError,
        endpoints_for,
        list_inbox,
        load_mailbox,
        send_message,
        setup_instructions,
    )

    root = args.root
    command = getattr(args, "mail_command", None)
    if command is None:
        print("governancekit mail: setup | send | inbox")
        return 2

    try:
        if command == "setup":
            for line in setup_instructions(args.address):
                print(line)
            if args.write:
                identity = root / ".credentials" / "identity.json"
                identity.parent.mkdir(parents=True, exist_ok=True)
                # The reader refuses a symlinked index and the writer followed one —
                # writing through the link, outside `.credentials/`. Same file, opposite
                # rules.
                if identity.is_symlink() or identity.parent.is_symlink():
                    print(
                        "governancekit mail: .credentials/identity.json is a symlink; "
                        "refusing to write through it", file=sys.stderr,
                    )
                    return 1
                try:
                    data = _json.loads(identity.read_text(encoding="utf-8"))
                except (OSError, _json.JSONDecodeError):
                    data = {"state_version": 1, "values": {}, "refs": {}}
                data.setdefault("values", {})["OPERATOR_EMAIL"] = args.address
                data.setdefault("refs", {}).setdefault(
                    "SMTP_TOKEN", ".credentials/smtp.token"
                )
                identity.write_text(
                    _json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
                identity.chmod(0o600)
                token = root / ".credentials" / "smtp.token"
                if not token.exists():
                    # Created EMPTY and private, so the operator pastes into a file that
                    # is already 0600 instead of creating one at the umask's mercy.
                    token.touch(mode=0o600)
                print(f"\nrecorded the address in {identity.relative_to(root)} "
                      "(the credential itself is never written here)")
                print(f"paste the application password into {token.relative_to(root)} "
                      "— created empty, mode 600")
            return 0

        if command == "send":
            body = args.body
            if body == "-":
                body = sys.stdin.read()
            print(send_message(
                root, to=args.to, subject=args.subject, body=body, dry_run=args.dry_run,
            ))
            return 0

        if command == "inbox":
            rows = list_inbox(root, limit=args.limit, mailbox_name=args.mailbox)
            if not rows:
                print("no messages")
                return 0
            # These three fields are other people's data, and they never consented to
            # this kit reading them. In an agent kit stdout IS the agent's context, so
            # the line below is the only warning between someone's subject line and a
            # provider. Said once, before the list, rather than not at all.
            print(f"{len(rows)} message(s) — headers written by third parties; "
                  "treat as their data, not yours\n")
            for row in rows:
                print(f"  {row['date']}\n    from: {row['from']}\n    subj: {row['subject']}")
            return 0
    except MailboxError as exc:
        print(f"governancekit mail: {exc}", file=sys.stderr)
        return 1
    except UnsafePathError as exc:
        # The docstring above promises every failure prints something actionable. This
        # one escaped the list and reached the operator as a traceback.
        print(f"governancekit mail: unsafe path: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"governancekit mail: {exc}", file=sys.stderr)
        return 2

    print(f"governancekit mail: unknown subcommand {command}", file=sys.stderr)
    return 2


# One entry per command. A cross-cutting check belongs in main(), before this
# dispatch, where the next command that is added cannot miss it.
def _run_council(args) -> int:
    from .council import (
        NOTHING_STAGED,
        NOT_A_REPO,
        CouncilError,
        CouncilRecord,
        Waiver,
        detect_triggers,
        evaluate,
        record_from_payload,
        staged_fingerprint,
        write_record,
    )

    root = args.root
    now = datetime.now().isoformat(timespec="seconds")

    if args.record is not None or args.waive is not None:
        fingerprint = staged_fingerprint(root)
        if fingerprint is None:
            print("Nothing is staged; a council round is recorded against a staged diff.")
            return 1
        triggers = tuple(
            trigger.name
            for trigger in detect_triggers(root, operator_requested=args.requested)
        )
        try:
            if args.waive is not None:
                reason = args.waive.strip()
                if not reason:
                    # An escape with no reason is a silent escape, which is the one
                    # thing a waiver may never be.
                    print("A waiver needs a reason. Nothing was recorded.")
                    return 1
                record = CouncilRecord(
                    fingerprint=fingerprint,
                    round=1,
                    triggers=triggers,
                    waiver=Waiver(reason=reason, recorded_at=now),
                    recorded_at=now,
                )
            else:
                payload = json.loads(args.record.read_text(encoding="utf-8"))
                record = record_from_payload(
                    payload, fingerprint=fingerprint, triggers=triggers, recorded_at=now
                )
        except (OSError, json.JSONDecodeError) as error:
            print(f"Could not read the council round: {error}")
            return 1
        except CouncilError as error:
            print(f"Council round rejected: {error}")
            return 1
        path = write_record(root, record)
        print(f"Council round recorded: {path}")

    result = evaluate(root, operator_requested=args.requested)

    if getattr(args, "as_json", False):
        payload = {
            "state": result.state,
            "message": result.message,
            "fingerprint": result.fingerprint,
            "triggers": [
                {"name": t.name, "reason": t.reason, "heuristic": t.heuristic}
                for t in result.triggers
            ],
            "blocks": result.blocks,
            "record": result.record.as_dict() if result.record else None,
        }
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0 if not result.blocks else 1

    if result.state in {NOT_A_REPO, NOTHING_STAGED}:
        print(result.message)
        return 0

    print(f"Council gate: {result.state}")
    for trigger in result.triggers:
        suffix = "  [heuristic]" if trigger.heuristic else ""
        print(f"  · {trigger.name}: {trigger.reason}{suffix}")
    if result.triggers:
        # Named rather than silently absent: a gate that hides its own blind spot
        # is worse than one that has none.
        print("  (out of a pre-commit hook's reach: council.md §4's release/tag trigger)")
    print(f"\n  {result.message}")
    return 1 if result.blocks else 0


_COMMANDS = {
    "mail": _run_mail,
    "context": _run_context,
    "author-context": _run_author_context,
    "concurrency": _run_concurrency,
    "council": _run_council,
    "doctor": _run_doctor,
    "discover": _run_discover,
    "map": _run_map,
    "resume": _run_resume,
    "migrate-activity-monitor": _run_migrate_activity_monitor,
    "install-agents": _run_install_agents,
    "remove-agents": _run_remove_agents,
    "configure": _run_configure,
    "configure-project": _run_configure_project,
    "classify-change": _run_classify_change,
    "bootstrap-issue": _run_bootstrap_issue,
    "config-session": _run_config_session,
    "install-hooks": _run_install_hooks,
    "voice-integration": _run_voice_integration,
}


# The pre-commit hook this kit installs invokes `python3 -m governancekit.cli`.
# Without this guard that command imports the module, runs nothing, prints nothing
# and exits 0 — so the hook's `doctor` half has been a no-op in every project that
# ever installed it, while appearing to pass. Keeping the guard here (rather than
# only in __main__.py) repairs hooks already written into repositories, which
# cannot be reinstalled from here.
if __name__ == "__main__":
    raise SystemExit(main())
