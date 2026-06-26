# Task 001: Bootstrap Repository

## Metadata

- work_id: WK-20260504-bootstrap-governancekit
- date: 2026-05-04
- status: started

## Context

AI GovernanceKit is starting as a new repository. It needs baseline context and operating files before implementation work can safely begin.

## Objective

Create the initial repository foundation for a runtime orchestration toolkit and provide the first executable local validation command.

## In Scope

- `README.md`
- `AGENTS.md`
- `docs/software-overview.md`
- `docs/limits.md`
- `handoff.md`
- `docs/napkin-lessons.md`
- local issue and resume artifacts
- minimal `governancekit doctor` CLI
- focused tests for the doctor validation behavior

## Out of Scope

- MCP server.
- IDE extension.
- External issue or PR creation.
- GitHub/Jira automation.
- Long-running orchestration service.
- Agent dispatch.

## ARO

Acceptance:
- Context and limits files exist and are ready.
- Local issue artifacts contain `work_id` and date.
- Resume file contains one concrete next step.
- `governancekit doctor` validates the current repository.
- Tests cover pass/fail validation behavior for required files and readiness flags.

Risk:
- Over-scoping into implementation before product boundaries are agreed.

Operations:
- No deploy operation exists yet.
- The CLI runs locally and reads repository files only.

## Test Plan

- Inspect file structure.
- Confirm readiness flags are set to `yes`.
- Run `governancekit doctor`.
- Run focused CLI tests.

## Definition of Done

- Bootstrap files are present.
- Basic validation commands have been run and documented.
- First executable doctor command is present and tested.
- Session-close files are updated with current status and next step.
