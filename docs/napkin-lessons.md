# Napkin Lessons

- 2026-05-04: Keep the policy kit and runtime orchestrator conceptually separate; this project owns the runtime/tooling layer.
- 2026-05-04: Bootstrap the runtime project with ready context and limits before choosing CLI, MCP, or IDE implementation details.
- 2026-05-04: Start runtime work with a narrow `doctor` command so governance rules become executable before orchestration grows.
- 2026-06-29: Project-owned docs (`docs/required-reading.md`, `docs/project/`) must NOT sit in the installer's upgrade path list — otherwise `--upgrade`/`--docs-only` would clobber project-authored content. Fresh install seeds them via the wholesale `docs` copy; upgrade preserves them by omission.
- 2026-06-29: Default install gitignores `docs` wholesale, which would also hide the project-owned `docs/project/`. Git cannot re-include a child of an ignored dir, so a bare `docs` + `!docs/project/` fails. Fix: emit `docs/*` (non-opaque) + `!docs/project/`. Verified with `git check-ignore`.
- 2026-06-29: `configure` only fills *known* kit placeholders (the `_PLACEHOLDER_DESCRIPTIONS` set); scanning all files for any `[WORD]` token would wrongly match doctor's own `[FAIL]`/`[HINT]` samples in README.
