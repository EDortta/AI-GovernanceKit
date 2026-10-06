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


def _pause(input_fn: Callable[[str], str]) -> None:
    input_fn("\nPress Enter to return to the menu...")


def _run(execute: Callable[[Sequence[str]], int], root: Path, development: bool, args: list[str]) -> int:
    prefix = ["--root", str(root)]
    if development:
        prefix.insert(0, "--development")
    return execute([*prefix, *args])


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
    state: WizardState,
    execute: Callable[[Sequence[str]], int],
    development: bool,
    input_fn: Callable[[str], str],
) -> None:
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
    if choice in commands:
        print("--[BEGIN]----")
        _run(execute, state.root, development, commands[choice])
        print("--[FINISH]----")
        _pause(input_fn)


def _llm_menu(
    state: WizardState,
    execute: Callable[[Sequence[str]], int],
    development: bool,
    input_fn: Callable[[str], str],
) -> None:
    while True:
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
        if choice in commands:
            _run(execute, state.root, development, commands[choice])
            # _pause(input_fn)
        elif choice == 'b':
            break


def _continue_recommended(
    state: WizardState,
    execute: Callable[[Sequence[str]], int],
    development: bool,
    input_fn: Callable[[str], str],
) -> bool | None:
    llm_status: bool | None = None
    if state.provider is None:
        _run(execute, state.root, development, ["llm", "configure"])
        llm_status = False
    elif not state.provider_ready:
        llm_status = _run(execute, state.root, development, ["llm", "test"]) == 0
    elif state.selected_sources == 0 and state.documentation_candidates:
        _run(execute, state.root, development, ["adoption", "sources"])
    elif state.selected_sources == 0:
        _run(execute, state.root, development, ["adoption", "describe"])
    elif not state.description_accepted and state.description_proposal:
        _run(execute, state.root, development, ["adoption", "describe", "--show"])
        print("\nUse menu option 5 to accept, reject, or regenerate this proposal.")
    elif not state.description_accepted:
        _run(execute, state.root, development, ["adoption", "describe", "--from-sources"])
    elif not state.adoption_plan:
        _run(execute, state.root, development, ["adoption", "analyze"])
    elif not state.adoption_applied:
        _show_plan(state.root)
        print("\nReview the plan above. Use option 8 when you want to apply it.")
    else:
        _run(execute, state.root, development, ["doctor"])
    _pause(input_fn)
    return llm_status


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
        # print("\n" * 2)
        os.system('cls' if os.name=='nt' else 'clear')
        state = inspect_wizard_state(root, provider_ready=provider_ready)
        print(render_home(state))
        choice = input_fn("Choice: ").strip().lower()

        if choice in {"q", "quit", "exit"}:
            print("GovernanceKit closed.")
            return 0
        if choice == "1":
            result = _continue_recommended(state, execute, development, input_fn)
            if result is not None:
                provider_ready = result
        elif choice == "2":
            _llm_menu(state, execute, development, input_fn)
        elif choice == "3":
            _run(execute, state.root, development, ["adoption", "discover"])
            _pause(input_fn)
        elif choice == "4":
            _show_selected_sources(state.root)
            print("\n  1  Change source selection")
            print("  B  Back")
            sub = input_fn("Choice: ").strip().lower()
            if sub == "1":
                _run(execute, state.root, development, ["adoption", "sources"])
                _pause(input_fn)
        elif choice == "5":
            _description_menu(state, execute, development, input_fn)
        elif choice == "6":
            _run(execute, state.root, development, ["adoption", "analyze"])
            _pause(input_fn)
        elif choice == "7":
            _show_plan(state.root)
            _pause(input_fn)
        elif choice == "8":
            print("This copies the modules currently marked selected=true in the reviewed plan.")
            confirm = input_fn("Apply the reviewed adoption plan? [y/N]: ").strip().lower()
            if confirm in {"y", "yes", "s", "sim"}:
                _run(execute, state.root, development, ["adoption", "apply"])
            else:
                print("Nothing changed.")
            _pause(input_fn)
        elif choice == "9":
            _run(execute, state.root, development, ["doctor"])
            _pause(input_fn)
        elif choice == "a":
            print("\nAdvanced commands remain available exactly as before.")
            print("Use: governancekit --help")
            print("     governancekit <command> --help")
            _pause(input_fn)
        else:
            print("Unknown option.")
            _pause(input_fn)
