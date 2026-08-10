# Project-Specific Rules

Rules, conventions and constraints that apply to **this project only**.

`AGENTS.md` is kit-owned and `install-agents --upgrade` replaces it, so a rule
written there disappears on the next upgrade. This file is project-owned: the
installer creates it once and never touches it again. Write project rules here.

## Rules

### Session memory stays out of `main`

Work starts from `development` and returns to `development`. `main` receives only
what the product is, never how it was built.

These paths must never reach `main`:

- `docs/issues/` — epics, tasks, RESUME files
- `docs/napkin-lessons.md`
- `handoff.md`

They record what happened in THIS repository — including the names of the projects a
lesson came from — and they grow every session. `main` is what gets released and
installed from, so it carries the product only.

Merge with `scripts/merge-to-main.sh` (`--dry-run` first). It re-applies the
exclusion on every run, so a merge that reintroduces the files resolves by removing
them again. Never merge `development` into `main` by hand.

Related: the installer seeds targets with EMPTY `handoff.md`,
`docs/napkin-lessons.md` **and `docs/required-reading.md`** templates, never with the
source repository's own copies (`_TEMPLATE_SEEDS` in
`governancekit/install_agents.py`). Same principle, one level out: session memory does
not travel — and neither does the kit's own list of local sources, which since
2026-08-10 includes the email transport a project is required to declare for itself.

### The readiness files are project-owned

`docs/software-overview.md` and `docs/limits.md` live in `docs/`, not `.docs/`. The
kit ships a template; the project writes the content and owns the readiness flags,
and the Start Gate must read the file the project maintains. See
`_PROJECT_SEED_PATHS` and `_migrate_readiness_files_to_docs`.
