# Software Overview

## Metadata

- work_id: WK-20260504-bootstrap-governancekit
- date: 2026-05-04
- owner: maintainer
- project_context_ready: yes

## Purpose

AI GovernanceKit is a local-first runtime orchestration toolkit for AI-assisted software delivery.

It provides executable support for governance rules that are usually written only as Markdown instructions. The project should help coding agents and human programmers restore work context, validate operational boundaries, run appropriate checks, record evidence, and close sessions predictably.

## Problem

Agent governance rules are often copied across repositories but not enforced. Programmers using different agents, such as Codex, Claude Code, Cursor, or IDE assistants, can drift from the intended workflow because each tool interprets instructions differently.

AI GovernanceKit addresses that gap by providing a tool-agnostic runtime layer around existing agents.

## Target Users

- Human programmers supervising AI-assisted work.
- Coding agents operating in local repositories.
- Teams that want repeatable issue, branch, validation, and handoff workflows.

## Core Components

- Policy documents: `AGENTS.md`, limits, role contracts, and workflow docs.
- Machine-readable policy model: future structured configuration for automation.
- CLI: commands for validation, code indexing, resume, start-work, session-close, and PR/issue checks.
- Runtime orchestrator: future service or library that evaluates gates and coordinates workflow steps.
- Integrations: future MCP server, IDE extension, GitHub/Jira helpers, and CI hooks.

## Current Scope

The current scope is repository bootstrap plus two executable CLI commands:

- define product context
- define operational limits
- create traceable local issue artifacts
- prepare resumable workflow files
- `governancekit doctor` — validate the governance scaffold (files, readiness flags, active issue, secrets)
- `governancekit map` — generate `docs/codemap.md`, a persistent Markdown code index (file tree, entry points, Python symbol index) for AI agents to read at session start instead of re-scanning source files
- `governancekit resume` — print the active work session at a glance (work_id, branch, status, next step from RESUME.md, recent handoff entry); run at session start by both agents and humans
- `governancekit install-agents` — install/update the AI-Agents kit; `--upgrade` refreshes all kit-owned files, `--docs-only` refreshes just kit docs, fresh install seeds the project-owned `docs/project/` folder
- `governancekit configure` — fill `[PLACEHOLDER]` kit variables across all docs without reinstalling (interactive or `--set KEY=VALUE`)

No long-running orchestration service, MCP server, IDE extension, or external issue/PR automation exists yet.
