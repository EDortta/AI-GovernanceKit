# Handoff

## Current Status

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
