# AI GovernanceKit

```bash
governancekit --version
```

Reports the GovernanceKit version, its default AI-Agents release, and the release
recorded by the nearest parent project's `.gk/manifest.json`, including a local
upgrade indication when the installed semantic version is older.

AI GovernanceKit is a local-first runtime orchestration toolkit for agentic software work.

The project turns repository governance rules into executable workflows that can be reused by CLI tools, IDE agents, MCP-compatible agents, and CI jobs. Its first responsibility is not to replace coding agents, but to make their work predictable: restore context, validate boundaries, run checks, collect evidence, and close sessions consistently.

## Product Shape

- Policy pack: human-readable contracts such as `AGENTS.md`, role guides, limits, and project overview.
- CLI: commands for doctor checks, resume, start-work, validation, session-close,
  read-only discovery, project adoption planning, and architecture classification.
- Runtime core: orchestration logic that loads policy, evaluates gates, and records audit evidence.
- Integrations: optional MCP server, IDE extension, GitHub/Jira helpers, and CI hooks.

## Context budgets

- **`governancekit context inspect`** selects task/risk sources from
  `.docs/context-manifest.yaml` and reports category budgets, largest contributors,
  duplicates, and exact versus estimated counting.
- **`governancekit context build`** emits selected content with provenance. Required
  contracts are atomic: if one does not fit, the command fails instead of truncating.

```bash
governancekit context inspect
governancekit context inspect --json
governancekit context build --task implementation
governancekit context build --task implementation --risk runtime \
  --issue docs/issues/006-context-optimization-[finished]/epic.md
```

`context build --telemetry` appends local metadata-only JSONL under `.gk/`. It
requires a `work_id` and captures paths/counts, never prompt or source content.
Use `governancekit context telemetry prune` to apply manifest retention.

## Initial Status

Three CLI commands are available:

- **`governancekit resume`** — run at the start of every session. Prints the active work_id, branch, status, and next step from RESUME.md, plus the most recent handoff summary. Both agents and humans run this before touching code.

- **`governancekit doctor`** — validates the governance scaffold (required files, readiness flags, active issue, secret tracking). Fix every `[FAIL]` before starting work. `[HINT]` lines are advisory — address when convenient. Use `--json` for CI integration: `governancekit doctor --json | jq '.ok'`

- **`governancekit map`** — generates `docs/codemap.md`: a Markdown index of the project's file tree, entry points, and Python symbol index. AI agents read this file at session start instead of re-scanning the codebase. Run after significant changes and commit the result.

- **`governancekit discover`** — inspects a repository read-only and reports whether
  it looks like a new governed project or an existing one that must be adopted
  carefully before writes.

- **`governancekit configure-project`** — builds or applies a shareable
  `.gk/project-config.json` plus `docs/project-configuration.md`, based on
  discovery and explicit operator selections for domains, capabilities, agents,
  and provider modes.

- **`governancekit classify-change`** — records the required classification for a
  structural change before implementation (`additive`, `migration`,
  `contract-change`, `security-sensitive`, etc.).

- **`governancekit config-session`** — turns configuration into a resumable,
  locally acknowledged session; it is not an independent authorization boundary.
  `config-session start --interactive` loads every
  available source named by `docs/required-reading.md`, invokes the chosen,
  locally authenticated agent in read-only mode to propose domains with source
  evidence, then records the reviewed agent, domains, owned capabilities, LLM
  provider purpose, routing role, and credential reference without ever storing
  a secret. The guided interview explains each choice, validates providers in
  place, and uses saved or pending values as defaults on the next installation
  or upgrade. For a local credential symlink whose destination is outside the
  project, `install-agents` and `install-agents --upgrade` accept symlinks under
  `.credentials/` during their operator-started interactive interview. Direct
  `config-session` use requires `--credentials-allow-symlinks` when needed.
  Neither exception is saved or relaxes the read-only source boundary. A JSON credential profile may
  contain `api_key` (or `apiKey`/`key`) plus optional `model` and `base_url`;
  those values are used in memory only.

- **`governancekit bootstrap-issue`** — generates local epic/task scaffolding
  from the installed issue templates, reusing the current project config and
  change classification.

- **`governancekit install-hooks`** — installs optional local git hooks (currently
  `pre-commit`) that run GovernanceKit checks before a commit lands.

- **`governancekit voice-integration detect`** — detects optional
  AI-ListenToMeOnCLI availability without making voice a hard dependency.

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

For a complete explanation of every command, parameter, identity field, and CI
workflow, see [Advanced usage details](https://edortta.github.io/AI-GovernanceKit/advanced-usage.html).

Run commands directly from the repository:

```bash
python3 -m governancekit resume   # print active session context
python3 -m governancekit doctor   # validate governance scaffold
python3 -m governancekit map      # generate docs/codemap.md
python3 -m governancekit discover # inspect whether this looks new or existing
python3 -m governancekit configure --set OPERATOR_NAME=Ann  # fill kit variables across docs
python3 -m governancekit install-hooks --hook-type pre-commit
```

### Installing & updating the AI-Agents kit

```bash
governancekit --root "$PWD" install-agents                 # fresh install (kit → .docs/, project owns docs/, prompts for variables)
governancekit --root "$PWD" install-agents --upgrade       # update all kit-owned files, preserve project state
governancekit --root "$PWD" install-agents --docs-only     # update only kit docs (not AGENTS.md / rule files)
governancekit --root "$PWD" configure                       # re-fill [PLACEHOLDER] variables without reinstalling
```

`--root` is the canonical project selector and must appear before the command.
It defaults to the current directory; use an absolute path when operating on a
different checkout. `--target` belongs only to the legacy AI-Agents shell installer.

After a fresh install, run `governancekit --root "$PWD" configure` once for each
host/checkout. It writes the local, gitignored `.governancekit-identity.json` required
by `doctor` before governed work can start.

`docs/` is yours to track; the kit lives under `.docs/` and is overwritten on
upgrade. `install-agents` asks whether to track `.docs/` in git (saved to
`.governancekit`); secrets stay gitignored regardless. Legacy installs (kit in
`docs/`) are migrated to `.docs/` automatically on `--upgrade`, with a backup in
`.docs-migration-bak/`. List mandatory pre-issue reading in `docs/required-reading.md`.

Or install in editable mode:

```bash
python3 -m pip install -e .
governancekit resume
governancekit doctor
governancekit doctor --json       # machine-readable output for CI
governancekit map
governancekit map --output path/to/custom.md   # custom output path
governancekit map --all                         # include private symbols
governancekit discover --json                   # read-only adoption report
governancekit configure-project plan            # preview shareable project-config state
governancekit configure-project apply           # write .gk/project-config.json + docs summary
governancekit classify-change plan              # preview required architecture classification
governancekit classify-change apply             # persist .gk/change-classification.json
governancekit config-session start --interactive # define scope from the agent reading index
governancekit config-session approve --approval project-config-review
governancekit config-session apply              # apply approved session
governancekit remove-agents plan                 # write a conservative provenance plan
governancekit remove-agents plan --with-llm      # propose reviewable project-content extraction
governancekit remove-agents apply --plan .gk/remove-agents-plan.json --accept-project-extractions
governancekit bootstrap-issue                   # scaffold local epic/task files from templates
governancekit install-hooks --hook-type pre-commit
governancekit voice-integration detect          # detect optional voice integration
```

`resume` reads the active epic's RESUME.md and handoff.md, and prints a compact session-start summary. Use it in agent prompt starters: *"Run `governancekit resume` and use the output to orient yourself before planning."*

`doctor` validates required governance files, readiness flags, active issue structure, resume next step, and tracked secret-file paths. It also hints when `docs/codemap.md` is missing or stale.

`map` writes a layered, human- and agent-readable Markdown document: a project
summary, detected governance contracts, ignored paths, entry points, file tree,
and Python symbol index. `doctor` asks for regeneration when the map is stale or
does not have those usable layers.

For CI, `scripts/validate-governance.sh /repo/path` runs `doctor --json` and
`discover --json` together so pipelines can fail on mandatory governance drift
while still receiving structured context about the repository shape.
