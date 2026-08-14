# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.1] - 2026-08-14

### Changed

- **`install-agents` now authors the two readiness documents instead of generating
  them.** It runs the same step `author-context` runs — discovery, then the project's
  own README and sources through a provider the operator consents to, then the
  operator confirming each document. Adoption owned a second generator that wrote both
  files itself; on a real target it produced neither, because of the two defects
  below, and reported success.

  **A missing provider is loud on every path, and never fatal.** The recorded `[MANDATORY]` policy —
  "a project remains operable in manual mode even when no provider is configured yet"
  — holds: without a provider the flow writes both documents from deterministic
  discovery, leaves the flags at `no` and says so. What changes is the silence: three
  code paths used to skip the LLM without a word, so an operator saw a clean run and
  concluded that was all the kit could do. They are now told what is available, that
  free does not mean keyless, and how to configure one.

- **Machine-generated content never declares readiness.** The generator emitted
  `- project_context_ready: yes` in the same file where it listed what it had failed
  to determine — a machine opening the Start Gate over text nobody had read. Both
  documents are now rendered by the one renderer that leaves the flag at `no`;
  `confirm_document` remains the only thing in the kit that writes `yes`.

- **The free-model catalog is data with provenance.** `governancekit/_llm_catalog.json`
  is derived from littlelm-proxy's catalog by `scripts/refresh-llm-catalog.py`, which
  has a `--check` mode, and the interview's presets are built from it. Precisely: the
  `openrouter` entry — 14 free models behind one key — is catalog-derived; the `openai`,
  `gemini` and `nvidia` endpoints remain hand-written, now in
  `llm_catalog._PAID_ENDPOINTS`, because a free-model catalog does not describe a paid
  tier. Those three model names moved rather than gaining a source, and the test that
  compares presets against the catalog cannot tell the difference. Stated plainly
  because the first draft of this entry claimed all four were derived.

### Fixed

- **Adoption stopped skipping its own write on a prose match.** The gate was
  `f"{marker}: yes" in old`, unanchored, over the whole file — and the template the
  installer seeds explains the flag in a sentence. So the SENTENCE matched, the kit
  concluded the project had declared itself ready, wrote nothing, and printed
  "existing project documents preserved" over its own boilerplate. `doctor` had the
  same defect and was anchored on 2026-08-04; the writer kept it for eight more days.
  The state now comes from `classify_document`, and deterministic writing replaces only
  text the kit itself put there.

- **`--force` no longer destroys `.credentials/` or the project's readiness documents.**
  `.credentials` was an ordinary conflict, so answering `y` — or passing `--force`,
  which never asks — ran `shutil.rmtree` over the operator's identity file, tokens and
  `.credentials/llm/*.key`. The kit now seeds only what is missing, file by file, and
  reports what it added and what it left alone. Same for `docs/software-overview.md`
  and `docs/limits.md`, which are the project's words. The shell installer has done
  both for months; this is the Python side converging on it.

- **Nothing under `.credentials/` reaches the tracked manifest.** `.gk/manifest.json`
  is shared deliberately, and it was recording a SHA-256 for every file in that
  directory — safe only because the directory was being deleted first. Making the
  seeding non-destructive without this would have started committing hashes of real
  tokens. Existing manifests lose those entries on the next run of any mode.

- **The generated `.gitignore` stopped contradicting its own comment.** A bare
  `.credentials` entry won over the `.credentials/*` + re-include patterns, and git
  does not descend into an excluded directory, so every file the kit seeds there was
  permanently untrackable. The gitignore test did not catch it because it
  **asserted the bare entry as correct**: it passed `.credentials` in its path list and
  checked for exactly the wrong string. This delivery flips that assertion. (The first
  draft of this entry blamed the path list, while the contradicting artifact was the
  very line being changed.)

- **The readiness reset is anchored**, like every other reader and writer of those
  flags. A plain `replace` also rewrote prose quoting the metadata line.

- **One eligibility predicate.** "Can this provider actually be called" was declared in
  `adoption` and again inline in `scope_conversation`. A provider that can never be
  called — the `--provider` grammar cannot express `base_url` or `model` — is now
  reported instead of being skipped in silence by every step.

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

### Security

- **A stored placeholder value can no longer smuggle another token into the render.**
  `.gk/manifest.json` is the half of the state a team shares and commits. Substitution
  ran sequentially over one buffer and used every key in state, so a shareable answer
  whose value was itself a token (`ORG_NAME` = `{{PIX_PAYLOAD}}`) made the next pass
  expand the victim's *local* secret into the text just injected, write it into a kit
  file and record its hash — and under `--track` that file is git-tracked. Substitution
  is now a single regex sweep over declared placeholders only, with a length cap. Not
  reachable at the pinned release, which ships no shareable token; one release away
  from being reachable.

### Fixed

- **The incoming source is rendered with the project's stored answers before anything
  is compared.** The upgrade judged a target the kit had already rendered (`Esteban`)
  against a source it had not (`{{OPERATOR_NAME}}`), so the kit's own substitution read
  as operator intent. Three consequences, each reproduced: a target with no manifest
  entry for `AGENTS.md` — a pre-`.gk` install, or a shell install whose manifest pass
  bailed — became permanently drifted and never received another contract; `configure`
  froze the file the same way, and now records what it filled so the answer survives;
  and the `.kit-new` handed over for merging carried raw placeholders, so following the
  instruction turned `doctor` red. The shell installer has rendered first since it grew
  the protection.

- **A project-authored file inside a kit directory is no longer claimed by the
  manifest.** Upgrade #1 preserved it and said so; `_write_state` then recorded it as
  kit-owned, and upgrade #2 deleted it in silence. The rule that keeps a drifted
  top-level file out of the manifest now covers preserved directory members too.

- **The parked `<file>.kit-new` no longer distorts `remove-agents`.** It was invisible
  to the planner — surviving de-adoption in the project root — and, being a verbatim
  kit contract, it counted as a citation of every kit path it names, flipping each from
  `remove` to `preserve` with the evidence line "current hash differs from recorded
  install hash" about files whose hash matched.

- **`.gk/pre-upgrade/` is cleared per upgrade and reported.** It accumulated, so after
  two upgrades it held the state before the *first* one, and nothing in the CLI ever
  named the directory. `.gk/.gitignore` also regained the shell's `pre-migrate/` entry,
  which this file's wholesale rewrite had been dropping on shell-installed targets, and
  gained `remove-agents-backup/`.

- **The §Sending Email check reports what it can actually see, and asks for what
  actually helps.** It claimed the "no carrier" case was already reported by
  `AI-Agents manifest`; that check compares paths against disk and never reads content,
  so nothing reported it. Its remedy promised a repair `--upgrade` does not perform (a
  protected file is *kept*; the upgrade parks the new version for a merge), and named a
  command that exits with a traceback on a target with a pending content migration. Its
  severity now mirrors the shell's: a kept file awaiting merge is reported, not a STOP —
  except when the kept body still prescribes the withdrawn transport, which blocks and
  is called out by name, as the shell has always done.

- **An upgrade no longer replaces a hand-edited root file without a word (R2-16').**
  `_do_upgrade` judged directories against the manifest — stashing kit files the
  project had edited, keeping project-authored ones — and then copied every *file*
  with a bare `shutil.copy2`. `AGENTS.md` is the first file every agent is told to
  read and therefore the first place anyone writes a project rule; the shell
  installer has refused to overwrite a drifted copy since 2026-07-23, after a target
  was found holding ~300 lines of project rules in it, including reviewer logins.
  This runtime replaced the same file for another twenty days. It now applies the
  same decision table: identical content is a silent no-op, a protected file that
  differs is kept with the new version beside it as `<file>.kit-new`, an edited
  non-protected file is stashed under `.gk/overwritten/`, unknown provenance fails
  closed for protected files, and every replaced file leaves a copy in
  `.gk/pre-upgrade/`. A kept file is left out of the manifest, so the *second*
  upgrade cannot read the project's own version as untouched kit content.

- **The two installers' protected-file lists are now compared, not asserted in prose.**
  `_kit_snapshot.json` records `protected_root_files` as read from the pinned
  release's `scripts/install-agents-kit.sh`; `tests/test_kit_drift.py` fails when the
  two sides disagree. A protection that exists in one of two implementations of the
  same contract reads as closed while half the fleet is unprotected — the third time
  that shape has cost this kit a delivery.

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
