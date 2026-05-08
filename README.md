# AI GovernanceKit

AI GovernanceKit is a local-first runtime orchestration toolkit for agentic software work.

The project turns repository governance rules into executable workflows that can be reused by CLI tools, IDE agents, MCP-compatible agents, and CI jobs. Its first responsibility is not to replace coding agents, but to make their work predictable: restore context, validate boundaries, run checks, collect evidence, and close sessions consistently.

## Product Shape

- Policy pack: human-readable contracts such as `AGENTS.md`, role guides, limits, and project overview.
- CLI: commands for doctor checks, resume, start-work, validation, and session-close.
- Runtime core: orchestration logic that loads policy, evaluates gates, and records audit evidence.
- Integrations: optional MCP server, IDE extension, GitHub/Jira helpers, and CI hooks.

## Initial Status

Three CLI commands are available:

- **`governancekit resume`** — run at the start of every session. Prints the active work_id, branch, status, and next step from RESUME.md, plus the most recent handoff summary. Both agents and humans run this before touching code.

- **`governancekit doctor`** — validates the governance scaffold (required files, readiness flags, active issue, secret tracking). Fix every `[FAIL]` before starting work. `[HINT]` lines are advisory — address when convenient. Use `--json` for CI integration: `governancekit doctor --json | jq '.ok'`

- **`governancekit map`** — generates `docs/codemap.md`: a Markdown index of the project's file tree, entry points, and Python symbol index. AI agents read this file at session start instead of re-scanning the codebase. Run after significant changes and commit the result.

  **Why map matters:** every time an AI agent starts a fresh session it re-reads source files to orient itself — burning tokens and adding latency with no persistent benefit. A committed `codemap.md` replaces that repeated traversal with a single, cheap document read. The map lives in the repository so it is always available immediately, survives context resets, and is readable by humans too.

## Companion: AI-Agents Policy Pack

AI-GovernanceKit is designed to work alongside [AI-Agents](https://github.com/EDortta/AI-Agents), the reusable governance policy pack.

- **AI-Agents** = policy pack — the "what and why" (AGENTS.md, role contracts, issue templates)
- **AI-GovernanceKit** = runtime CLI — the "how" (doctor, future: session automation, CI hooks)

They have no formal dependency:
- AI-Agents installs by copying files into a target project
- AI-GovernanceKit installs as a Python package (`pip install ai-governancekit`)
- The `doctor` command validates the AI-Agents file structure (`AGENTS.md`, `software-overview.md`, `limits.md`, active issue, `RESUME.md`)

Use both together for governed, auditable agentic work. Either can be used independently.

---

## Daily Workflow

Three commands cover the full session lifecycle:

```bash
# Start of session — always first
governancekit resume

# Before touching code — fix any [FAIL] before starting
governancekit doctor

# After a batch of changes — commit the result
governancekit map
git add docs/codemap.md
git commit -m "refresh codemap"
```

## Local Usage

Run commands directly from the repository:

```bash
python3 -m governancekit resume   # print active session context
python3 -m governancekit doctor   # validate governance scaffold
python3 -m governancekit map      # generate docs/codemap.md
```

Or install in editable mode:

```bash
python3 -m pip install -e .
governancekit resume
governancekit doctor
governancekit doctor --json       # machine-readable output for CI
governancekit map
governancekit map --output path/to/custom.md   # custom output path
governancekit map --all                         # include private symbols
```

`resume` reads the active epic's RESUME.md and handoff.md, and prints a compact session-start summary. Use it in agent prompt starters: *"Run `governancekit resume` and use the output to orient yourself before planning."*

`doctor` validates required governance files, readiness flags, active issue structure, resume next step, and tracked secret-file paths. It also hints when `docs/codemap.md` is missing or stale.

`map` traverses the project, extracts the Python symbol tree via the standard-library `ast` module, and writes a human- and agent-readable Markdown document.
