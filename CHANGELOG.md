# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Drift gate between the two kits** (`governancekit/kit_drift.py`). Three things this
  repository states about AI-Agents are now asserted instead of asked for in prose: the
  release it pins, the version range that release declares, and the shared `§Sending
  Email` body it carries a copy of. `governancekit/_kit_snapshot.json` records what the
  pinned release says; `scripts/refresh-kit-snapshot.py` re-derives it from the
  checksum-verified tarball, and `--check` proves the stored snapshot is current without
  trusting that whoever bumped the pin remembered to refresh it. The tests themselves
  need no network.

- **Drift gate now also covers the seed templates.** `_TEMPLATE_SEEDS` names three
  sources in the pinned release; a source the release does not carry is not an error
  anywhere — `_resolve_src` falls back to the source's own file, so the target silently
  receives the *kit's* handoff and reading index instead of an empty template. That was
  R2-15, and it shipped across three releases. The snapshot now records which seeds the
  release actually carries.

### Fixed

- **`configure` can fill `{{OPERATOR_NAME}}` without a terminal.** The placeholder pass
  ran before host identity was collected and never read the identity file at all, so off
  a TTY it filled nothing while the answer sat in `.governancekit-identity.json` — a file
  the same command had just written. Since `doctor`'s `unfilled placeholders` check is
  non-advisory and names `configure` as the remedy, every scripted install was left
  permanently red with a remedy that provably did nothing. Explicit `--set` still wins.
- **`configure` reports the placeholder form the files actually contain.** The syntax
  reconciliation reached the installer and missed the one line an operator reads to learn
  what to look for: it named `[OPERATOR_NAME]`, which greps to nothing.
- **A manifest entry the kit could never have written no longer becomes a deletion.**
  `_write_state` merges the previous manifest forward and prunes only entries whose file
  vanished, so a path wrongly claimed once survives every upgrade — and `manifest.json` is
  the tracked half of the state, so the wrong claim reaches every clone. In
  `remove-agents` such an entry matched its own recorded hash and became `remove` at
  confidence 1.0 with `requires_operator_review: false`. The hash is now checked against a
  second, independent question — is this a path the installer writes at all — which
  repairs manifests already committed in the field without a migration.
- `test_the_hook_does_not_block_when_the_toolchain_is_missing` never produced the
  condition it names on a machine where this kit is installed per user — which, since it
  is installed per user by design, is the normal machine. Clearing `PATH` and
  `PYTHONPATH` leaves the user site directory on `sys.path`, so the hook still found a
  toolchain; the test passed only while the installed copy was too old to run the gate it
  reaches. Now isolated with `PYTHONNOUSERSITE`.

## [0.3.0] - 2026-08-11

### Changed

- Default AI-Agents release is now checksum-pinned `v1.2.1` (was `v1.1.7`). It is a
  minor, not a patch: the kit's templates move from the project's `templates/` to
  `.docs/templates/`.
- **This runtime is `0.3.0`, so it no longer satisfies a contract that declares
  `>=0.2.2,<0.3.0`.** AI-Agents `v1.2.1` widens the declared range to
  `>=0.2.2,<0.4.0`, which makes the two kits upgradable in either order — but only
  for a project that already carries the `v1.2.1` contract. A project still on an
  older kit keeps its own `<0.3.0` range and will report the integration contract as
  incompatible until it is upgraded. See the upgrade note below.
- `AGENTS.md` §Sending Email no longer prescribes an email transport. Transport, sender
  and recipient list are project-specific and declared in `docs/required-reading.md`
  (EDortta/AI-Agents#5, EDortta/AI-GovernanceKit#7).
- `docs/required-reading.md` is seeded from a neutral template instead of the kit's own
  index, which had been exporting the kit's local sources into every new project.

### Removed

- `SMTP_ACCOUNT` and `SMTP_DOMAIN` are no longer collected. A value stored by an earlier
  install is still substituted and stays out of the tracked manifest.

### Fixed

- `doctor` no longer dies on a directory it cannot search. `_iter_source_files` guarded
  `iterdir()` but not the per-item probes, so the `.git` `exists()` test that detects a
  nested repo raised `PermissionError` and ended the whole run in a traceback with no
  verdict printed. Found against a governed project holding a root-owned `drwx------`
  data directory; the advisory scan now costs that directory, not the report.
- `doctor` no longer reports a header-only `Fontes locais` table as malformed, no longer
  tells a project to index an email transport this kit has withdrawn, and no longer lets
  a stale contract mask the project's own declaration of the same path.
- `configure` can fill a retired placeholder again. Removing it from the descriptions
  left `doctor` failing non-advisory while naming a command that did nothing.

### Upgrade note

**Upgrade the governed projects' kit to `v1.2.1` before installing this runtime, or
expect `doctor` to fail on them.** A project whose `.docs/governancekit-integration.json`
still declares `>=0.2.2,<0.3.0` reports `AI-Agents integration contract requires
GovernanceKit >=0.2.2,<0.3.0, current version is 0.3.0`. That finding is **not
advisory** for a project whose `.gk/project-config.json` says `project_state:
existing` (`doctor.py:239`), and a non-advisory failure is a STOP under the contract's
§8b. Measured on the maintainer's machine when `0.3.0` was cut: 29 projects carried
`.gk/manifest.json`, 4 of them had completed scope configuration, and all 4 were on
kit `v1.1.6`. Widening the range in `v1.2.1` does not reach them — they hold their own
copy of the old range.

**A project with its own `templates/` directory should check `.gk/manifest.json`.** An
install made between 2026-08-07 and 2026-08-10 may have recorded the project's own
template files as kit-owned; `remove-agents` would then offer to delete them at full
confidence. The entry is no longer created, but an existing one is not repaired
automatically.

## [0.2.2] - 2026-07-27

### Added

- Advanced usage documentation in English, Brazilian Portuguese, and Spanish.
- Separate, copy-ready commands for fresh AI-Agents installs and upgrades.

### Changed

- Default AI-Agents release updated to checksum-pinned `v1.1.6`.
- Landing-page navigation and installation guidance corrected and completed.

## [0.1.0] - 2026-05-21

### Added

- `install-agents` command — downloads and installs [[GITHUB_OWNER]/AI-Agents](https://github.com/[GITHUB_OWNER]/AI-Agents) kit into a target project.
  - Installed paths are added to `.gitignore` by default so kit files stay out of the host repository; `--track` opts out.
  - Interactive conflict resolution: warns per file and asks whether to overwrite; suggests `--force` when conflicts exceed 10% of kit paths.
  - Supports `--force`, `--upgrade`, `--ref`, and `--repo` flags.
  - README files from AI-Agents are excluded to preserve the host project's own README.
- `resume` command — prints session-start context assembled from `RESUME.md` and `handoff.md`.
- `map` command — generates a persistent Markdown code index (`docs/codemap.md`) for AI agents, listing files and public symbols.
- `doctor --json` flag — outputs validation results as JSON for use in CI scripts.
- GitHub Pages landing page (`docs/index.html`) with EN/PT-BR/ES language switcher, Code Map section, and Resume section.
- Concepts intro page (`docs/intro.html`) with trilingual language switcher.

### Fixed

- Install instructions corrected — package is not yet published to PyPI.

[Unreleased]: https://github.com/EDortta/AI-GovernanceKit/compare/v0.2.2...HEAD
[0.2.2]: https://github.com/EDortta/AI-GovernanceKit/compare/v0.2.1...v0.2.2
[0.1.0]: https://github.com/EDortta/AI-GovernanceKit/releases/tag/v0.1.0
