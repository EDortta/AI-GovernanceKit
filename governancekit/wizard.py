"""Interactive, occasional-use front door for AI GovernanceKit."""

from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .adoption import configured_adoption_provider, provider_label
from .adoption_flow import (
    DESCRIPTION_PROPOSAL_FILE,
    PLAN_FILE,
    PROJECT_DESCRIPTION_FILE,
    SOURCES_FILE,
    discover_documentation,
)


@dataclass(frozen=True)
class WizardState:
    root: Path
    provider: str | None
    provider_ready: bool
    documentation_candidates: int
    selected_sources: int
    description_proposal: bool
    description_accepted: bool
    adoption_plan: bool
    adoption_applied: bool

    @property
    def next_step(self) -> str:
        if self.provider is None:
            return "Configure the project LLM"
        if not self.provider_ready:
            return "Test the configured LLM"
        if self.selected_sources == 0:
            if self.documentation_candidates:
                return "Discover and select project documentation"
            return "Describe the project with operator-supplied facts"
        if not self.description_accepted:
            if self.description_proposal:
                return "Review the proposed project description"
            return "Let the LLM propose a description from selected sources"
        if not self.adoption_plan:
            return "Analyze which governance modules fit this project"
        if not self.adoption_applied:
            return "Review and apply the adoption plan"
        return "Run project health checks"


def inspect_wizard_state(root: Path, *, provider_ready: bool = False) -> WizardState:
    root = root.resolve()
    provider = configured_adoption_provider(root)

    selected_sources = 0
    try:
        payload = json.loads((root / SOURCES_FILE).read_text(encoding="utf-8"))
        values = payload.get("sources", [])
        if isinstance(values, list):
            selected_sources = sum(isinstance(value, str) for value in values)
    except (OSError, json.JSONDecodeError):
        pass

    provider_text = provider_label(provider) if provider is not None else None
    return WizardState(
        root=root,
        provider=provider_text,
        provider_ready=bool(provider and provider_ready),
        documentation_candidates=len(discover_documentation(root)),
        selected_sources=selected_sources,
        description_proposal=(root / DESCRIPTION_PROPOSAL_FILE).is_file(),
        description_accepted=(root / PROJECT_DESCRIPTION_FILE).is_file(),
        adoption_plan=(root / PLAN_FILE).is_file(),
        adoption_applied=(root / ".gk/adoption/manifest.json").is_file(),
    )


def _mark(value: bool) -> str:
    return "OK" if value else "--"


def render_home(state: WizardState) -> str:
    provider = state.provider or "not configured"
    provider_status = "ready" if state.provider_ready else "not tested/ready"
    lines = [
        "+--------------------------------------------------------------------+",
        "|                     AI GOVERNANCEKIT                               |",
        "|               Project setup and governance                         |",
        "+--------------------------------------------------------------------+",
        f" Project : {state.root}",
        f" LLM     : {provider} ({provider_status})",
        "",
        " Project state",
        f"   [{_mark(state.provider_ready)}] LLM configured and reachable",
        f"   [{_mark(state.selected_sources > 0)}] Documentation sources selected ({state.selected_sources})",
        f"   [{_mark(state.description_accepted)}] Project description accepted",
        f"   [{_mark(state.adoption_plan)}] Governance modules analyzed",
        f"   [{_mark(state.adoption_applied)}] Governance adoption applied",
        "",
        f" Recommended next step: {state.next_step}",
        "",
        "  1  Continue recommended setup",
        "  2  LLM configuration and test",
        "  3  Discover project documentation",
        "  4  Select or review documentation sources",
        "  5  Describe / review the project",
        "  6  Analyze governance modules",
        "  7  Review adoption plan",
        "  8  Apply governance modules",
        "  9  Project health / doctor",
        "  A  Advanced command help",
        "  Q  Quit",
        "+--------------------------------------------------------------------+",
    ]
    return "\n".join(lines)


def _run_section(
    execute: Callable[[Sequence[str]], int],
    root: Path,
    development: bool,
    args: list[str],
) -> int:
    print("\n[BEGIN]------------------------------------------------------------")
    exit_code = _run(execute, root, development, args)
    print("[FINISH]-----------------------------------------------------------\n")
    return exit_code

def _run(execute: Callable[[Sequence[str]], int], root: Path, development: bool, args: list[str]) -> int:
    prefix = ["--root", str(root)]
    if development:
        prefix.insert(0, "--development")
    try:
        return execute([*prefix, *args])
    except SystemExit as exc:
        # argparse uses SystemExit for --help. Inside the wizard, help is only
        # another submenu result and must never terminate the whole application.
        return int(exc.code or 0)


def _show_selected_sources(root: Path) -> None:
    try:
        payload = json.loads((root / SOURCES_FILE).read_text(encoding="utf-8"))
        sources = payload.get("sources", [])
    except (OSError, json.JSONDecodeError):
        sources = []
    if not sources:
        print("No documentation sources have been selected yet.")
        return
    print("Selected documentation sources:")
    for index, source in enumerate(sources, 1):
        print(f"  {index:02d}. {source}")


def _show_plan(root: Path) -> None:
    try:
        payload = json.loads((root / PLAN_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("No adoption plan exists yet. Run analysis first.")
        return
    modules = payload.get("modules", [])
    print("Reviewed adoption plan:")
    for priority in ("core", "high", "on-demand", "low", "exclude"):
        rows = [
            row for row in modules
            if isinstance(row, dict) and row.get("priority") == priority
        ]
        if not rows:
            continue
        print(f"\n{priority.upper()} ({len(rows)})")
        for row in rows:
            selected = "x" if row.get("selected") else " "
            print(f"  [{selected}] {row.get('path', '?')} - {row.get('reason', '')}")
    print(f"\nPlan file: {PLAN_FILE}")
    print("You may edit selected=true/false before applying.")


def _description_menu(
    root: Path,
    provider_ready: bool,
    execute: Callable[[Sequence[str]], int],
    development: bool,
    input_fn: Callable[[str], str],
) -> None:
    while True:
        state = inspect_wizard_state(root, provider_ready=provider_ready)
        print("\nProject description")
        if state.description_accepted:
            print(f"  Accepted: {PROJECT_DESCRIPTION_FILE}")
        if state.description_proposal:
            print(f"  Proposal: {DESCRIPTION_PROPOSAL_FILE}")
        print("  1  Generate proposal from selected sources")
        print("  2  Describe project by answering questions")
        print("  3  Show current proposal")
        print("  4  Accept current proposal")
        print("  5  Reject current proposal")
        print("  B  Back")
        choice = input_fn("Choice: ").strip().lower()
        commands = {
            "1": ["adoption", "describe", "--from-sources"],
            "2": ["adoption", "describe"],
            "3": ["adoption", "describe", "--show"],
            "4": ["adoption", "describe", "--accept"],
            "5": ["adoption", "describe", "--reject"],
        }
        if choice == "b":
            return
        if choice in commands:
            _run_section(execute, state.root, development, commands[choice])
        else:
            print("Unknown option.")

def _llm_menu(
    root: Path,
    provider_ready: bool,
    execute: Callable[[Sequence[str]], int],
    development: bool,
    input_fn: Callable[[str], str],
) -> bool:
    llm_ready = provider_ready
    while True:
        state = inspect_wizard_state(root, provider_ready=llm_ready)
        print("\nLLM configuration")
        print(f"  Current: {state.provider or 'not configured'}")
        print(f"  Status : {'ready' if state.provider_ready else 'not tested/ready'}")
        print("  1  Show configuration")
        print("  2  Configure")
        print("  3  Test connectivity")
        print("  B  Back")
        choice = input_fn("Choice: ").strip().lower()
        commands = {
            "1": ["llm", "show"],
            "2": ["llm", "configure"],
            "3": ["llm", "test"],
        }
        if choice == "b":
            return llm_ready
        if choice not in commands:
            print("Unknown option.")
            continue

        exit_code = _run_section(execute, state.root, development, commands[choice])
        if choice == "2":
            llm_ready = False
        elif choice == "3":
            llm_ready = exit_code == 0

def _continue_recommended(
    state: WizardState,
    execute: Callable[[Sequence[str]], int],
    development: bool,
) -> bool | None:
    llm_status: bool | None = None
    if state.provider is None:
        _run_section(execute, state.root, development, ["llm", "configure"])
        llm_status = False
    elif not state.provider_ready:
        llm_status = (
            _run_section(execute, state.root, development, ["llm", "test"]) == 0
        )
    elif state.selected_sources == 0 and state.documentation_candidates:
        _run_section(execute, state.root, development, ["adoption", "sources"])
    elif state.selected_sources == 0:
        _run_section(execute, state.root, development, ["adoption", "describe"])
    elif not state.description_accepted and state.description_proposal:
        _run_section(
            execute, state.root, development,
            ["adoption", "describe", "--show"],
        )
        print("Use Project description to accept, reject, or regenerate this proposal.")
    elif not state.description_accepted:
        _run_section(
            execute, state.root, development,
            ["adoption", "describe", "--from-sources"],
        )
    elif not state.adoption_plan:
        _run_section(execute, state.root, development, ["adoption", "analyze"])
    elif not state.adoption_applied:
        print("\n[BEGIN]------------------------------------------------------------")
        _show_plan(state.root)
        print("[FINISH]-----------------------------------------------------------\n")
        print("Use Governance adoption to apply the reviewed plan.")
    else:
        _run_section(execute, state.root, development, ["doctor"])
    return llm_status


def _documentation_menu(
    root: Path,
    provider_ready: bool,
    execute: Callable[[Sequence[str]], int],
    development: bool,
    input_fn: Callable[[str], str],
) -> None:
    while True:
        state = inspect_wizard_state(root, provider_ready=provider_ready)
        print("\nProject documentation")
        print(f"  Candidates found : {state.documentation_candidates}")
        print(f"  Sources selected : {state.selected_sources}")
        print("  1  Discover documentation")
        print("  2  Show selected sources")
        print("  3  Select / change sources")
        print("  B  Back")
        choice = input_fn("Choice: ").strip().lower()
        if choice == "b":
            return
        if choice == "1":
            _run_section(execute, state.root, development, ["adoption", "discover"])
        elif choice == "2":
            print("\n[BEGIN]------------------------------------------------------------")
            _show_selected_sources(state.root)
            print("[FINISH]-----------------------------------------------------------\n")
        elif choice == "3":
            _run_section(execute, state.root, development, ["adoption", "sources"])
        else:
            print("Unknown option.")


def _analysis_menu(
    root: Path,
    provider_ready: bool,
    execute: Callable[[Sequence[str]], int],
    development: bool,
    input_fn: Callable[[str], str],
) -> None:
    while True:
        state = inspect_wizard_state(root, provider_ready=provider_ready)
        print("\nGovernance analysis")
        print(f"  Existing plan: {'yes' if state.adoption_plan else 'no'}")
        print("  1  Analyze governance modules")
        print("  2  Reassess governance modules")
        print("  3  Review current adoption plan")
        print("  B  Back")
        choice = input_fn("Choice: ").strip().lower()
        if choice == "b":
            return
        if choice == "1":
            _run_section(execute, state.root, development, ["adoption", "analyze"])
        elif choice == "2":
            _run_section(execute, state.root, development, ["adoption", "reassess"])
        elif choice == "3":
            print("\n[BEGIN]------------------------------------------------------------")
            _show_plan(state.root)
            print("[FINISH]-----------------------------------------------------------\n")
        else:
            print("Unknown option.")


def _adoption_menu(
    root: Path,
    provider_ready: bool,
    execute: Callable[[Sequence[str]], int],
    development: bool,
    input_fn: Callable[[str], str],
) -> None:
    while True:
        state = inspect_wizard_state(root, provider_ready=provider_ready)
        print("\nGovernance adoption")
        print(f"  Plan available : {'yes' if state.adoption_plan else 'no'}")
        print(f"  Applied        : {'yes' if state.adoption_applied else 'no'}")
        print("  1  Review current plan")
        print("  2  Apply selected governance modules")
        print("  3  Plan/remove managed governance")
        print("  B  Back")
        choice = input_fn("Choice: ").strip().lower()
        if choice == "b":
            return
        if choice == "1":
            print("\n[BEGIN]------------------------------------------------------------")
            _show_plan(state.root)
            print("[FINISH]-----------------------------------------------------------\n")
        elif choice == "2":
            confirm = input_fn("Apply the reviewed adoption plan? [y/N]: ").strip().lower()
            if confirm in {"y", "yes", "s", "sim"}:
                _run_section(execute, state.root, development, ["adoption", "apply"])
            else:
                print("Nothing changed.")
        elif choice == "3":
            _run_section(execute, state.root, development, ["adoption", "remove"])
        else:
            print("Unknown option.")


def _health_menu(
    root: Path,
    provider_ready: bool,
    execute: Callable[[Sequence[str]], int],
    development: bool,
    input_fn: Callable[[str], str],
) -> None:
    while True:
        print("\nProject health")
        print("  1  Run doctor")
        print("  2  Show session resume")
        print("  3  Refresh code map")
        print("  B  Back")
        choice = input_fn("Choice: ").strip().lower()
        if choice == "b":
            return
        commands = {
            "1": ["doctor"],
            "2": ["resume"],
            "3": ["map"],
        }
        if choice in commands:
            _run_section(execute, root, development, commands[choice])
        else:
            print("Unknown option.")


def _advanced_menu(
    root: Path,
    development: bool,
    execute: Callable[[Sequence[str]], int],
    input_fn: Callable[[str], str],
) -> None:
    while True:
        print("\nAdvanced tools")
        print("  1  Show top-level command help")
        print("  2  Show adoption command help")
        print("  3  Show LLM command help")
        print("  B  Back")
        choice = input_fn("Choice: ").strip().lower()
        if choice == "b":
            return
        if choice == "1":
            _run_section(execute, root, development, ["--help"])
        elif choice == "2":
            _run_section(execute, root, development, ["adoption", "--help"])
        elif choice == "3":
            _run_section(execute, root, development, ["llm", "--help"])
        else:
            print("Unknown option.")

def run_wizard(
    root: Path,
    *,
    development: bool,
    execute: Callable[[Sequence[str]], int],
    input_fn: Callable[[str], str] = input,
) -> int:
    """Run the interactive front door while preserving every advanced subcommand."""
    provider_ready = False
    while True:
        # Only the main menu clears the terminal. Submenus preserve their history.
        os.system("cls" if os.name == "nt" else "clear")
        state = inspect_wizard_state(root, provider_ready=provider_ready)
        print(render_home(state))
        choice = input_fn("Choice: ").strip().lower()

        if choice in {"q", "quit", "exit"}:
            print("GovernanceKit closed.")
            return 0
        if choice == "1":
            result = _continue_recommended(state, execute, development)
            if result is not None:
                provider_ready = result
        elif choice == "2":
            provider_ready = _llm_menu(
                root, provider_ready, execute, development, input_fn
            )
        elif choice in {"3", "4"}:
            _documentation_menu(
                root, provider_ready, execute, development, input_fn
            )
        elif choice == "5":
            _description_menu(
                root, provider_ready, execute, development, input_fn
            )
        elif choice in {"6", "7"}:
            _analysis_menu(
                root, provider_ready, execute, development, input_fn
            )
        elif choice == "8":
            _adoption_menu(
                root, provider_ready, execute, development, input_fn
            )
        elif choice == "9":
            _health_menu(
                root, provider_ready, execute, development, input_fn
            )
        elif choice == "a":
            _advanced_menu(root, development, execute, input_fn)
        else:
            print("Unknown option.")
