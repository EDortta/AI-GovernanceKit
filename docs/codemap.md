# Code Map · ai-governancekit

> Generated: 2026-07-27 · Root: `/home/esteban/Sync/Projects/AI/GovernanceKit`
> Refresh: `governancekit map`

23 file(s) · 206 symbol(s) indexed

## Entry Points

- `governancekit` command → `governancekit.cli:main`
- `governancekit/__main__.py` — `python -m governancekit`

## File Tree

```
governancekit/
  __init__.py  — "AI GovernanceKit runtime tools."
  __main__.py
  cli.py
  codemap.py
  configure.py
  context.py  — "Deterministic context selection, budgeting, provenance, and inspection."
  doctor.py
  identity.py  — "Per-host / per-instance programmer identity."
  install_agents.py
  resume.py
pyproject.toml
scripts/
  notify-nexo.sh
tests/
  test_codemap.py
  test_configure.py
  test_context.py
  test_doctor.py
  test_doctor_advisory_scan.py
  test_doctor_gitignore.py
  test_doctor_tracked_secrets.py
  test_install_agents.py
  test_install_agents_integrity.py
  test_install_agents_safe_extract.py
  test_resume.py
```

## Symbol Index

### `governancekit/cli.py`

- `build_parser()`
- `format_doctor(result)`
- `format_doctor_json(result)`
- `format_resume(result)`
- `main(argv)`

### `governancekit/codemap.py`

- **`SymbolInfo`** *(class)* — "Extracted symbol (class, function, or method) from a source file."
- **`FileEntry`** *(class)* — "Single source file with extracted metadata."
- **`EntryPoint`** *(class)* — "Detected project entry point."
- **`MapResult`** *(class)* — "Result of a map run."
  - `file_count` *(property)*
  - `symbol_count` *(property)*
- `run_map(root, output, include_private)` — "Generate a Markdown code map for the project at root and write it to output."

### `governancekit/configure.py`

- **`ConfigureResult`** *(class)*
- `parse_set_pairs(pairs)` — "Parse ``KEY=VALUE`` strings from ``--set`` into a mapping."
- **`IdentityResult`** *(class)*
- `run_configure_identity(root)` — "Collect, validate and persist per-host identity fields."
- `run_configure(root)` — "Fill kit placeholder variables across all text files under *root*."

### `governancekit/context.py`

> Deterministic context selection, budgeting, provenance, and inspection.

- **`ContextError`** *(class)* — "A context contract or hard budget limit was violated."
- **`TokenCounter`** *(class)*
  - `count(self, text)` *(method)* — "Return the token count for text."
- **`DeterministicTokenCounter`** *(class)* — "Provider-neutral fallback: one token per four Unicode characters."
  - `count(self, text)` *(method)*
- **`TiktokenCounter`** *(class)* — "Optional exact counter, activated only when tiktoken is installed."
  - `__init__(self)` *(method)*
  - `count(self, text)` *(method)*
- `default_token_counter()`
- **`Source`** *(class)*
  - `metadata(self)` *(method)*
- **`ContextResult`** *(class)*
  - `content` *(property)*
  - `as_dict(self, include_content)` *(method)*
- `load_manifest(root, manifest_path)`
- `build_context(root, task, risks, issue, manifest_path, counter, write_telemetry)`
- `format_context(result)`

### `governancekit/doctor.py`

- **`CheckResult`** *(class)*
- **`DoctorResult`** *(class)*
  - `ok` *(property)*
- `run_doctor(root)`

### `governancekit/identity.py`

> Per-host / per-instance programmer identity.

- **`Identity`** *(class)*
  - `missing_required(self)` *(method)*
  - `complete` *(property)*
  - `to_dict(self)` *(method)*
- `identity_path(root)`
- `load_identity(root)` — "Return the persisted Identity, or None when the file is absent/unreadable."
- `identity_from_values(values)` — "Build an Identity from a flat string mapping (e.g. CLI flags)."
- `save_identity(root, identity)` — "Persist *identity* to the local gitignored file and return its path."
- `ensure_gitignored(root)` — "Ensure the identity file is listed in .gitignore. Returns True if changed."
- `current_branch(root)` — "Return the current git branch, or '' when unavailable."
- `sibling_branch_conflict(identity, branch)` — "Return a warning if the current branch matches the instance's declared"

### `governancekit/install_agents.py`

- **`InstallResult`** *(class)*
- `run_install_agents(root)` — "Download and install AI-Agents kit into *root*."

### `governancekit/resume.py`

- **`HandoffEntry`** *(class)* — "Parsed snapshot from the most recent handoff.md entry."
- **`ResumeResult`** *(class)* — "Context assembled for the start of a new session."
- `run_resume(root)` — "Assemble session-start context from RESUME.md and handoff.md."

### `tests/test_codemap.py`

- **`IsPrivateTests`** *(class)*
  - `test_single_underscore_is_private(self)` *(method)*
  - `test_dunder_is_not_private(self)` *(method)*
  - `test_plain_name_is_not_private(self)` *(method)*
- **`ParsePythonTests`** *(class)*
  - `test_extracts_module_docstring(self)` *(method)*
  - `test_extracts_function(self)` *(method)*
  - `test_extracts_async_function(self)` *(method)*
  - `test_extracts_class_with_methods(self)` *(method)*
  - `test_skips_private_by_default(self)` *(method)*
  - `test_includes_private_when_flag_set(self)` *(method)*
  - `test_property_kind(self)` *(method)*
  - `test_syntax_error_returns_empty(self)` *(method)*
  - `test_vararg_and_kwarg(self)` *(method)*
- **`DetectProjectNameTests`** *(class)*
  - `test_reads_pyproject_toml(self)` *(method)*
  - `test_reads_package_json(self)` *(method)*
  - `test_falls_back_to_directory_name(self)` *(method)*
- **`DetectEntryPointsTests`** *(class)*
  - `test_reads_project_scripts(self)` *(method)*
  - `test_detects_main_py(self)` *(method)*
- **`RunMapTests`** *(class)*
  - `test_generated_map_has_no_trailing_whitespace(self)` *(method)*
  - `test_creates_output_file(self)` *(method)*
  - `test_output_contains_project_name(self)` *(method)*
  - `test_output_contains_symbol(self)` *(method)*
  - `test_custom_output_path(self)` *(method)*
  - `test_file_and_symbol_counts(self)` *(method)*
  - `test_codemap_not_in_own_output(self)` *(method)*
  - `test_gitignore_excludes_files(self)` *(method)*

### `tests/test_configure.py`

- **`ConfigureTests`** *(class)*
  - `test_set_pairs_parsing(self)` *(method)*
  - `test_fills_known_placeholder_across_files(self)` *(method)*
  - `test_ignores_unknown_tokens(self)` *(method)*
  - `test_reports_unfilled(self)` *(method)*
- **`ConfigureIdentityTests`** *(class)*
  - `test_non_interactive_missing_required_does_not_save(self)` *(method)*
  - `test_non_interactive_complete_saves_and_gitignores(self)` *(method)*
  - `test_gitignore_entry_not_duplicated(self)` *(method)*
  - `test_cli_configure_set_ok_when_identity_unconfigured(self)` *(method)*
  - `test_cli_configure_errors_when_identity_flags_incomplete(self)` *(method)*

### `tests/test_context.py`

- `source(path, text)`
- `make_repo(tmp_path)`
- `paths(result)`
- `test_task_and_risk_selection_is_explicit(tmp_path)`
- `test_council_only_loads_for_council_task(tmp_path)`
- `test_history_is_not_loaded_by_default(tmp_path)`
- `test_required_over_budget_fails_without_truncation(tmp_path)`
- `test_optional_over_budget_is_omitted_with_warning(tmp_path)`
- `test_duplicate_path_is_selected_once_and_reported(tmp_path)`
- `test_identical_content_and_provenance_are_reported(tmp_path)`
- `test_sections_and_lexical_retrieve_are_deterministic(tmp_path)`
- `test_fallback_count_and_json_are_stable(tmp_path)`
- `test_category_budget_is_enforced(tmp_path)`
- `test_metadata_only_telemetry_requires_and_records_work_id(tmp_path)`
- `test_human_output_shows_budget_categories_and_largest_sources(tmp_path)`
- `test_real_base_context_stays_under_declared_budget()`

### `tests/test_doctor.py`

- **`DoctorTests`** *(class)*
  - `test_valid_repository_passes(self)` *(method)*
  - `test_missing_limits_ready_flag_fails(self)` *(method)*
  - `test_empty_resume_next_step_fails(self)` *(method)*
  - `test_missing_required_reading_fails(self)` *(method)*
  - `test_required_reading_none_sentinel_passes(self)` *(method)*
  - `test_required_reading_only_stub_fails(self)` *(method)*
  - `test_missing_identity_file_fails(self)` *(method)*
  - `test_incomplete_identity_file_fails(self)` *(method)*
  - `test_complete_identity_file_passes(self)` *(method)*
  - `test_security_advisories_flag_antipatterns_without_failing(self)` *(method)*
  - `test_security_advisories_clean_passes(self)` *(method)*
  - `test_tracked_private_key_material_fails(self)` *(method)*
- `write_valid_repo(root)`
- `failed_check_names(result)`

### `tests/test_doctor_advisory_scan.py`

- **`AdvisoryScanScopeTests`** *(class)*
  - `test_scan_skips_gitignored_files(self)` *(method)*
  - `test_scan_does_not_descend_into_submodule(self)` *(method)*
  - `test_scan_still_flags_tracked_source(self)` *(method)*
  - `test_scan_flags_non_ignored_sibling_of_ignored_dir(self)` *(method)*
  - `test_scan_without_git_still_scans_everything(self)` *(method)*

### `tests/test_doctor_gitignore.py`

- **`GitignoreSecretsTests`** *(class)*
  - `test_covering_gitignore_passes(self)` *(method)*
  - `test_env_variant_glob_still_covers_dotenv(self)` *(method)*
  - `test_missing_credentials_pattern_fails(self)` *(method)*
  - `test_no_gitignore_fails(self)` *(method)*
  - `test_non_git_directory_passes(self)` *(method)*

### `tests/test_doctor_tracked_secrets.py`

- **`TrackedSecretFilesTests`** *(class)*
  - `test_tracked_dotcredentials_file_fails(self)` *(method)*
  - `test_tracked_env_variant_fails(self)` *(method)*
  - `test_unrelated_tracked_file_passes(self)` *(method)*
  - `test_env_example_is_not_a_tracked_secret(self)` *(method)*
  - `test_nested_env_example_is_not_a_tracked_secret(self)` *(method)*
  - `test_credentials_example_is_not_a_tracked_secret(self)` *(method)*
  - `test_credentials_readme_and_gitignore_are_not_tracked_secrets(self)` *(method)*
  - `test_credentials_translated_readme_is_not_a_tracked_secret(self)` *(method)*
  - `test_env_local_is_still_a_tracked_secret(self)` *(method)*
  - `test_real_credentials_file_is_still_a_tracked_secret(self)` *(method)*
  - `test_example_suffix_does_not_whitelist_a_key_by_name(self)` *(method)*

### `tests/test_install_agents.py`

- **`InstallAgentsTests`** *(class)*
  - `test_dest_rel_maps_kit_docs_but_not_project(self)` *(method)*
  - `test_resolve_src_prefers_dotdocs_source(self)` *(method)*
  - `test_fresh_install_reads_dotdocs_source(self)` *(method)*
  - `test_ensure_project_docs_creates_once(self)` *(method)*
  - `test_docs_only_installs_into_dotdocs(self)` *(method)*
  - `test_upgrade_preserves_project_authored_agent(self)` *(method)*
  - `test_upgrade_retires_untouched_kit_file(self)` *(method)*
  - `test_upgrade_keeps_locally_edited_kit_file(self)` *(method)*
  - `test_state_roundtrip_and_merge(self)` *(method)*
  - `test_metadata_reapplied_without_a_terminal(self)` *(method)*
  - `test_unknown_metadata_survives_as_unfilled(self)` *(method)*
  - `test_state_hash_matches_file_after_placeholder_fill(self)` *(method)*
  - `test_edited_kit_file_is_stashed_before_being_replaced(self)` *(method)*
  - `test_unedited_kit_file_is_replaced_without_stashing(self)` *(method)*
  - `test_secrets_ignored_but_manifest_shared(self)` *(method)*
  - `test_secrets_split_from_shareable_metadata(self)` *(method)*
  - `test_no_secrets_file_when_nothing_sensitive(self)` *(method)*
  - `test_gitignore_uses_dotdocs_and_leaves_docs_tracked(self)` *(method)*
  - `test_gitignore_tracks_kit_docs_when_opted_in(self)` *(method)*
  - `test_gitignore_section_keeps_secrets_across_modes(self)` *(method)*
  - `test_track_config_persists_and_is_read(self)` *(method)*
  - `test_migrate_legacy_layout_moves_kit_and_promotes_project(self)` *(method)*
  - `test_migrate_ignores_non_kit_project_with_generic_docs(self)` *(method)*
  - `test_migrate_completes_interrupted_run_without_overwriting(self)` *(method)*
  - `test_required_reading_stays_project_owned(self)` *(method)*
  - `test_fill_placeholders_ignores_doc_example_tokens(self)` *(method)*

### `tests/test_install_agents_integrity.py`

- **`DefaultRefPinTests`** *(class)*
  - `test_default_ref_is_not_the_mutable_main_branch(self)` *(method)*
  - `test_default_repo_ref_has_a_known_checksum(self)` *(method)*
- **`DownloadChecksumTests`** *(class)*
  - `test_matching_checksum_is_accepted(self)` *(method)*
  - `test_mismatched_checksum_is_rejected_before_extraction(self)` *(method)*

### `tests/test_install_agents_safe_extract.py`

- **`SafeExtractallTests`** *(class)*
  - `test_extracts_normal_members(self)` *(method)*
  - `test_rejects_path_traversal_member(self)` *(method)*
  - `test_absolute_path_member_stays_inside_dest(self)` *(method)*

### `tests/test_resume.py`

- `write_resume_md(path, work_id, branch, status, next_step)`
- `write_valid_repo(root, next_step)`
- **`ParseResumeMdTests`** *(class)*
  - `test_extracts_metadata(self)` *(method)*
  - `test_extracts_next_step(self)` *(method)*
  - `test_next_step_stops_at_next_heading(self)` *(method)*
  - `test_missing_next_step_returns_empty(self)` *(method)*
- **`ParseHandoffMdTests`** *(class)*
  - `test_single_entry_format(self)` *(method)*
  - `test_multi_entry_format(self)` *(method)*
  - `test_unparseable_returns_none(self)` *(method)*
- **`RunResumeTests`** *(class)*
  - `test_valid_repo(self)` *(method)*
  - `test_missing_resume_md(self)` *(method)*
  - `test_missing_handoff_warns(self)` *(method)*
  - `test_prefers_started_epic(self)` *(method)*
- **`ResumeIdentityTests`** *(class)*
  - `test_displays_operator_and_host(self)` *(method)*
  - `test_warns_when_identity_missing(self)` *(method)*

