# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Default AI-Agents release is now checksum-pinned `v1.2.0` (was `v1.1.7`). It is a
  minor, not a patch: the kit's templates move from the project's `templates/` to
  `.docs/templates/`.
- `AGENTS.md` §Sending Email no longer prescribes an email transport. Transport, sender
  and recipient list are project-specific and declared in `docs/required-reading.md`
  (EDortta/AI-Agents#5, EDortta/AI-GovernanceKit#7).
- `docs/required-reading.md` is seeded from a neutral template instead of the kit's own
  index, which had been exporting the kit's local sources into every new project.

### Removed

- `SMTP_ACCOUNT` and `SMTP_DOMAIN` are no longer collected. A value stored by an earlier
  install is still substituted and stays out of the tracked manifest.

### Fixed

- `doctor` no longer reports a header-only `Fontes locais` table as malformed, no longer
  tells a project to index an email transport this kit has withdrawn, and no longer lets
  a stale contract mask the project's own declaration of the same path.
- `configure` can fill a retired placeholder again. Removing it from the descriptions
  left `doctor` failing non-advisory while naming a command that did nothing.

### Upgrade note

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
