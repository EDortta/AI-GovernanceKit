# AI GovernanceKit

AI GovernanceKit is a local-first runtime orchestration toolkit for agentic software work.

The project turns repository governance rules into executable workflows that can be reused by CLI tools, IDE agents, MCP-compatible agents, and CI jobs. Its first responsibility is not to replace coding agents, but to make their work predictable: restore context, validate boundaries, run checks, collect evidence, and close sessions consistently.

## Product Shape

- Policy pack: human-readable contracts such as `AGENTS.md`, role guides, limits, and project overview.
- CLI: commands for doctor checks, resume, start-work, validation, and session-close.
- Runtime core: orchestration logic that loads policy, evaluates gates, and records audit evidence.
- Integrations: optional MCP server, IDE extension, GitHub/Jira helpers, and CI hooks.

## Initial Status

This repository is being bootstrapped. The current executable scope is a minimal local `doctor` command that validates the governance scaffold.

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

## Local Usage

Run the current executable directly from the repository:

```bash
python3 -m governancekit doctor
```

Or install it in editable mode:

```bash
python3 -m pip install -e .
governancekit doctor
```

The `doctor` command validates required governance files, readiness flags, active issue structure, resume next step, and tracked secret-file paths.
