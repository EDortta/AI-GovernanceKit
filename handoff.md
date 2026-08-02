# Handoff

## Current Status

- work_id: GH-6-simplified-adoption
- branch: `feature/uc-011/simplified-adoption-flow`
- status: first implementation stage complete; proposal/apply core pending commit.
- delivered: normal `install-agents` now produces a consolidated, evidence-based
  adoption proposal. `--quick` applies generated docs, `--review` is interactive,
  `--advanced` retains config-session, and CI requires `--non-interactive
  --accept-generated`. Existing ready project documents are never overwritten.
- validation: `PYTHONPATH=. pytest -q` → 238 passed, 1 skipped.
- next: add provider-backed proposal enrichment and upgrade/drift coverage before
  closing GitHub #6.

- work_id: GH-5-remove-agents
- branch: `feature/uc-010/remove-agents-safe-plan`
- status: LLM-assisted extraction complete; pending commit, push, and GitHub close.
- delivered: `remove-agents plan` inventories only safe regular files below the
  selected root and writes `.gk/remove-agents-plan.json`; `apply` deletes only
  manifest-hash-identical, unreferenced files after a per-file backup and restore
  manifest. Modified, unknown, referenced, and symlink paths are preserved.
- validation: `PYTHONPATH=. pytest -q` → 236 passed.
- delivered next: `remove-agents plan --with-llm` sends only a modified, unreferenced
  candidate to the configured primary provider and records a structured split. Apply
  requires `--accept-project-extractions`, writes operator-owned content under
  `docs/project-rules/ai-agents-extracted/`, updates required reading, replaces the
  kit file with its proposed reusable remainder, and backs up the original first.
- validation: `PYTHONPATH=. pytest -q` → 237 passed.
- next: commit and push this branch, then close GitHub #5; start #6 separately.

- work_id: WK-20260729-secure-project-adoption
- work_id: WK-20260729-secure-project-adoption
- branch: `feature/project-scope-conversation`
- status: core interview implementation committed for review; epic remains in progress.
- scope: secure, localized conversational project adoption after `install-agents`,
  `install-agents --upgrade`, and interactive configuration sessions.
- evidence: a real CodexBridgeMobile upgrade produced a useful domain proposal in
  English under a PT-BR operational environment, then ended with an ambiguous
  `Domains (comma-separated...)` prompt. The epic makes locale precedence and
  explicit accept/edit/merge/discard decisions contractual.
- follow-up evidence: after completing domains and capabilities, the provider
  prompt accepted `openai:::general` without explaining that `general` is not a
  valid routing role. It failed only at the end and offered no local retry.
  Task 007 now requires guided provider collection, explanation/example/spacing,
  immediate validation, and resumable progress without secrets.
- delivered: operational locale, guided PT-BR/EN/ES prompts with visual spacing,
  in-place provider validation, saved/pending defaults, provider purpose/role,
  root-confined source selection, isolated temporary agent workspace, strict
  proposal validation, and Unicode-safe issue slugs.
- validation: GovernanceKit `pytest -q` -> 184 passed; AI-Agents
  `scripts/run-checks.sh` passed. Critical-review revision isolated the agent
  workspace from the full project root.
- remaining: durable mid-interview draft recovery, provider validation before
  scope-agent invocation, and dependency/sensitivity metadata remain open tasks;
  do not close the epic from this commit.
- next: test the interactive upgrade against CodexBridgeMobile before closing
  the remaining tasks.

## Prior Status

- work_id: WK-20260727-restore-landing
- status: finished
- Public landing uses EDortta links and restored Pix, ETH, and Ko-fi values.
- Reusable README/templates keep placeholders. Package version is 0.2.2.

## Prior Status


- work_id: WK-20260727-context-hardening
- branch: `feature/uc-007/context-hardening`
- status: finished
- delivered: honest tokenizer estimate metadata; semantic task/risk categories;
  enforced reserve; declared-order emission; required retrieval failure; weighted
  lexical ranking; containment; inspect diagnostics; timestamp/prune telemetry;
  `governancekit --version` with nearest-project version and upgrade indication.
- validation: 136 pytest PASS; real AI-Agents context 19,221 / 21,000 usable;
  AI-Agents gate PASS.
- not validated: three-project benchmark because only AI-Agents currently carries
  the compatible v1.1.3 context manifest.
- compatibility: Amazon Q Developer adapter added to installer; both landing pages
  now describe the shared, upgrade-protected mandatory context.

## Prior Status


- work_id: WK-20260727-context-optimization
- date: 2026-07-27
- branch: `feature/uc-006/context-optimization`
- status: finished
- summary: Added schema validation, deterministic task/risk selection,
  `full`/`sections`/lexical `retrieve`, token-counter injection, hard budgets,
  provenance, duplicate reporting, stable JSON, and metadata-only JSONL.
- validation: `python3 -m pytest -q` -> 125 passed; real AI-Agents manifest inspected
  at 19,692 / 22,000 exact tokens for implementation + runtime; JSON build parsed.
- not validated: third-party agent integrations.
- next: no implementation action remains; merge/push authorized. Release and deploy
  remain separate gated actions.
- release follow-up: AI-Agents `v1.1.2` published; GovernanceKit default installer
  ref and verified tarball SHA-256 updated to that immutable tag.
- published-ref install validated in a temporary target; manifest, schemas,
  context documentation, and telemetry ignore rule were present.

## Prior Status

- work_id: WK-20260717-doctor-false-positives
- date: 2026-07-20
- branch: `main` (mergeada e pushada — `origin/main` = `06ee872`)
- status: Épico `004-doctor-false-positives-[finished]` fechado. Duas tasks, ambas
  `[finished]`, na `main` e no GitHub.

### O que foi feito

Descoberto em uso real (`governancekit doctor` sobre `Lucedata/AcheiVc`, 2026-07-17):
o doctor produzia FAILs/HINTs falsos que treinam o operador a ignorar a saída, e aí
o sinal real se perde no ruído.

- **Task 001** — `.example` não é segredo. `_check_tracked_secret_files` reprovava
  `.env.example` e os `.credentials/*.example`/`README*` que o próprio AI-Agents
  distribui — o doctor reprovava o kit-fonte. Fix: `_is_secret_template()`, exclusão
  por sufixo de template, espelhando `run-checks.sh` §4 do gêmeo. `.env.local`/
  `.env.production` (SEC-0221) continuam reprovando.
- **Task 002** — advisory scan varria gitignored e descia em submódulo (4 dos 15
  hits do AcheiVc eram `main.dart.js` do Flutter). Fix pontual, **sem walker novo**:
  `_iter_source_files` pula subdir com `.git`; `_git_ignored_paths` filtra via
  `git check-ignore -z --stdin` (fail-open, §6). No AcheiVc: **15 → 7 hits**, os
  `shell injection` reais e um `weak password hash` antes afogado passaram a aparecer.

### Validação

`python3 -m pytest tests/` → **100 passed** (87 originais + 13 novos). Gêmeo
AI-Agents intocado (`run-checks.sh` verde).

### Aberto / próximo

- **`walk.py` do épico do arnês** (`WK-20260717-harness-generation`, ainda não
  aberto) deve **converter e deletar** `_iter_source_files` + `_git_ignored_paths`
  para o seam `Ignorer` compartilhado — os 4 walkers do pacote (`codemap.py:190`,
  `doctor.py` ×2, `configure.py:138`) continuam duplicados, com `SKIP_DIRS`/
  `_CODEMAP_SKIP` **já divergentes**. Este fix é conversão futura (§7), não
  coexistência.
- **AcheiVc** não recebeu o kit ainda — o operador vai testar `install-agents
  --upgrade` lá por conta própria (repo em layout legado `docs/`, 27 arquivos
  pendentes → limpar antes; a migração move `docs/` → `.docs/` com backup).

---

## Current Status (histórico)

- work_id: WK-20260702-per-host-identity-runtime
- date: 2026-07-02
- branch: (working tree — not committed)
- status: Per-host identity runtime implemented and validated (65 tests green),
  pending review/commit. Issue moved to `[review]`. Companion AI-Agents contract
  issue still `[draft]` (separate epic).

## Summary (2026-07-02, per-host identity)

Added runtime collection + enforcement of per-host/instance identity. New module
`governancekit/identity.py` persists `operator_name`, `host_id`, `instance_path`,
`sibling_path`, `assigned_ports`, `branch_ownership` to a gitignored per-instance
file `.governancekit-identity.json` (no secrets). `configure` collects the fields
(interactive prompts + `--operator-name/--host-id/--instance-path/--sibling-path/
--assigned-ports/--branch-ownership` flags), refuses to save while a required field
(operator_name/host_id/instance_path) is missing, and auto-adds the file to
`.gitignore`. `doctor` gained a MANDATORY `host identity` gate (`[FAIL]` /
`ok:false` when missing or incomplete) and an advisory `sibling branch` same-branch
guard. `resume` shows active `operator@host` + git branch and warns on sibling
collision. Field names align with the AI-Agents companion contract issue. Tests:
`test_configure.py` (identity collection), `test_doctor.py` (pass/fail on
presence/absence/incomplete), `test_resume.py` (display + missing warning).

### Next Steps (per-host identity)

- Review the working-tree diff; commit if accepted (do NOT deploy — gated step).
- Implement companion AI-Agents contract issue (`mandate-per-host-programmer-identity`).

## Prior Status (WK-20260701-dotdocs-kit-layout)

- branch: feature/WK-20260701-dotdocs-kit-layout
- status: AI-GovernanceKit side implemented and validated, pending
  review/commit. AI-Agents side scaffolded as epic (not yet implemented).

## Summary

Moved the kit out of `docs/` into `.docs/`, freeing `docs/` to be 100% the host
project's. Resolves three operator concerns: (1) legacy projects that already used
`docs/` are no longer invaded; (2) ownership is unambiguous (kit = `.docs/`, project
= `docs/`); (3) tracking kit docs in git is now a prompted, persisted choice.

Key mechanics in `governancekit/install_agents.py`:
- `_dest_rel()` maps source `docs/…` → dest `.docs/…` for kit docs, keeping
  project-owned seeds (`required-reading.md`, `napkin-lessons.md`) in `docs/`.
  Resilient even if the AI-Agents source repo still uses `docs/`.
- `_FRESH_PATHS` replaces the wholesale `docs` copy with explicit kit paths, so a
  new project never inherits the source repo's active issues/project docs.
- `_migrate_legacy_layout()` (run before `--upgrade`/`--docs-only`) moves kit docs
  `docs/*` → `.docs/`, promotes `docs/project/*` → `docs/`, backs up to
  `.docs-migration-bak/`, reports collisions, idempotent (no-op once `.docs/` exists).
- `_resolve_track_kit_docs()` + `.governancekit` config: CLI flag → config → prompt
  → default (untracked). `.gitignore` emits a single `.docs/` entry (or omits it when
  tracking); secrets (`.credentials`, `handoff.md`) stay ignored regardless.

This repo migrated in place (`git mv` docs → .docs; `docs/project/README.md` →
`docs/README.md`). Doctor readiness checks now read `.docs/`.

## Next Steps

- Review the diff; commit if accepted (do NOT deploy — separate gated step).
- Implement the twin AI-Agents epic `docs/issues/002-dotdocs-kit-layout-[draft]/`
  (restructure source to `.docs/`, update `install-agents-kit.sh` + migration,
  update AGENTS.md/CLAUDE.md/READMEs). Coordinate merges so installer and source
  don't diverge.

## Blockers / Risks

- Cross-repo: AI-Agents source still uses `docs/`. `_dest_rel` mapping makes this
  non-blocking, but the source should be restructured for consistency.
- Legacy migration validated by unit test, not a full network end-to-end install.
- `install-agents-kit.sh` (AI-Agents shell mirror) NOT yet updated — tracked as
  task 002 in the AI-Agents epic.

## Files Changed

AI-GovernanceKit:
- `governancekit/install_agents.py` — `.docs/` layout, `_dest_rel`, legacy migration,
  track-kit-docs prompt/config, `_FRESH_PATHS`/`_UPGRADE_PATHS` rework
- `governancekit/cli.py` — `--track`/`--no-track` group, migration/gitignore output
- `governancekit/doctor.py` — readiness checks read `.docs/`
- `AGENTS.md`, `README.md`, `docs/required-reading.md`, `docs/README.md`,
  `docs/napkin-lessons.md`, `.docs/software-overview.md`, `.docs/agents/README.md`
- moved: `docs/{agents,workflows,software-overview.md,limits.md,issues/templates}`
  → `.docs/…`; `docs/project/README.md` → `docs/README.md`
- `tests/test_install_agents.py`, `tests/test_doctor.py`

Issue 002 (installer ↔ source alignment) — IMPLEMENTED (pending review):
- `governancekit/install_agents.py` — new `_resolve_src()` reads kit docs from the
  source's `.docs/` (restructured source, AI-Agents commit 6a5e6ba) with fallback to
  `docs/` (legacy source); project seeds always from `docs/`. Wired into
  `_do_fresh`/`_do_upgrade`. Folder renamed `002-…-[draft]` → `[review]`.
- `tests/test_install_agents.py` — +2 tests (57 total, green).

WhatsApp notification (wa-hub / Nexo):
- `scripts/notify-nexo.sh` (new) — sends an operator DM as "*GovernanceKit* —"
  (identity via text signature; ensureSenderTag idempotent, no alias hijack).
  Config in `~/.config/wa-hub/governancekit.env` (0600, local-only) — currently an
  INTERIM shared key; proper provisioning requested in wa-hub issue 014.
- Completion DM sent (id 3EB06519843829755B7736).

Landing / docs pages:
- `docs/index.html` — new trilingual (PT/ES/EN) "Novidades / What's new" band for a
  semi-technical audience (benefit-first), nav link `#whatsnew`, button → melhorias.html
- `docs/melhorias.html` (new) — beautiful technical backlog page: what/why/how/impact/
  migration/roadmap, with a docs/ → .docs/ directory-diff signature. Reuses the brand
  tokens (Uruguay palette, Fraunces/Inter/JetBrains Mono). The roadmap has a "outras
  coisas" placeholder to extend. NOTE: mirror/link from the AI-Agents index later.

AI-Agents (source kit) — scaffolded, not implemented:
- `docs/issues/002-dotdocs-kit-layout-[draft]/` (epic + 3 tasks)

## Checks / Tests Executed

- `python3 -m pytest -q` -> PASS, 55 tests.
- Local integration (no network): `_do_fresh` + `_ensure_project_docs` on a fake
  source -> kit in `.docs/`, project files in `docs/`, readiness flag reset,
  `.gitignore` emits single `.docs/`.
- Legacy migration covered by `test_migrate_legacy_layout_moves_kit_and_promotes_project`.

## Security Impact

- mitigated security impact
- Secrets (`.credentials`, `handoff.md`) remain in the managed `.gitignore` section
  regardless of the track-kit-docs choice — verified by regression test.
- `.governancekit` stores only the boolean track preference; no secrets.

## Model / Migration Changes

- No DB/model migrations. Repo-layout migration only (docs → .docs), reversible via
  `.docs-migration-bak/` when the installer performs it on legacy projects.
