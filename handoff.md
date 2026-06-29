# Handoff

## Current Status

- work_id: WK-20260629-docs-governance-tooling
- date: 2026-06-29
- branch: feature/WK-20260629-docs-governance-tooling
- status: implemented and validated (tests green), pending review/commit

## Summary

Four operator-requested capabilities, spanning AI-GovernanceKit (CLI logic) and
AI-Agents (kit source content):

1. **Granular docs update** — `install-agents --docs-only` refreshes only kit-owned
   documentation, leaving `AGENTS.md` and per-tool rule files untouched.
2. **Forced full-doc reading** — new `docs/required-reading.md` manifest, gated in
   `AGENTS.md` Required Context and enforced by a new `doctor` check.
3. **Reconfigure variables anytime** — new `governancekit configure` command fills
   `[PLACEHOLDER]` kit variables across all docs (interactive or `--set KEY=VALUE`),
   without reinstalling.
4. **Project-owned docs** — fresh install seeds `docs/project/` (tracked, never
   overwritten); `AGENTS.md` now forbids hand-editing kit-owned docs.

## Next Steps

- Review the diff in both repos; commit if accepted.
- Source-kit (AI-Agents) change requires human boundary approval before commit
  (it edits gates/templates).

## Blockers / Risks

- The shell installer (`install-agents-kit.sh`) was updated for parity but only
  smoke-validated via `bash -n`; a full end-to-end install was not run.
- `governancekit doctor` on this repo still reports `[FAIL] unfilled placeholders`
  (pre-existing: AGENTS.md ships template `[OPERATOR_NAME]`/`[SMTP_ACCOUNT]`) —
  now fixable with `governancekit configure`.

## Files Changed

AI-GovernanceKit:
- `governancekit/install_agents.py` — `--docs-only`, `_DOCS_PATHS`, `_ensure_project_docs`
- `governancekit/configure.py` (new) — placeholder fill across repo
- `governancekit/doctor.py` — `_check_required_reading`
- `governancekit/cli.py` — `--docs-only` flag, `configure` subcommand
- `docs/required-reading.md` (new), `docs/project/README.md` (new)
- `AGENTS.md`, `README.md`, `docs/software-overview.md`, `docs/napkin-lessons.md`
- `tests/test_configure.py` (new), `tests/test_install_agents.py` (new), `tests/test_doctor.py`

AI-Agents (source kit):
- `AGENTS.md` — required-reading gate + documentation-ownership rules
- `docs/required-reading.md` (new template)
- `scripts/install-agents-kit.sh` — create `docs/project/`, preserve new project files

## Checks / Tests Executed

- `python3 -m unittest discover -s tests` -> PASS, 48 tests.
- `python3 -m compileall governancekit tests` -> PASS.
- `governancekit configure --set OPERATOR_NAME=Ann` on temp dir -> filled, reported unfilled.
- `governancekit install-agents --help` -> shows `--docs-only`.
- `bash -n scripts/install-agents-kit.sh` (AI-Agents) -> PASS.

## Security Impact

- mitigated security impact
- Surface: `configure`/install write to local text files under the repo root only.
- `configure` substitutes only known kit tokens; no network, no secret exposure.
- Residual risk: operator-supplied values are written verbatim into tracked docs.

## Model / Migration Changes

- No model/migration changes.
