# Code Map · ai-governancekit

> Generated: 2026-08-03 · Root: `/home/esteban/Sync/Projects/AI/GovernanceKit-main-merge`
> Refresh: `governancekit --root /home/esteban/Sync/Projects/AI/GovernanceKit-main-merge map`

## Summary

- 53 file(s) · 420 symbol(s) indexed
- Languages: config (1), python (50), shell (2)
- Top-level areas: `.`, `governancekit`, `scripts`, `tests`

## Governance

- `AGENTS.md`
- `docs/required-reading.md`
- `.docs/software-overview.md`
- `.docs/limits.md`

## Ignored Paths

- Built-in: `.docs-migration-bak`, `.git`, `.idea`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.tox`, `.venv`, `.vscode`, `__pycache__`, `build`, `dist`, `env`, `node_modules`, `venv`
- `.gitignore`: `.env`, `.env.*`, `.credentials/`, `.governancekit-identity.json`, `.cache/`, `.tmp/`, `tmp/`, `logs/`, `*.log`, `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.venv/`, `venv/`, `node_modules/`, `dist/`, `build/`, `coverage/`, `.DS_Store`, `Thumbs.db`, `*.egg-info/`, `*.backup`, `.gk/`

## Entry Points

- `governancekit` command → `governancekit.cli:main`
- `governancekit/__main__.py` — `python -m governancekit`

## File Tree

```
governancekit/
  __init__.py  — "AI GovernanceKit runtime tools."
  __main__.py
  adoption.py  — "Evidence-based, review-first project adoption used by ``install-agents``."
  agent_scope.py  — "Read-only LLM proposals for project scope adoption."
  classification.py  — "Architecture change classification workflow."
  cli.py
  codemap.py
  config_session.py  — "Resumable configuration sessions with explicit approval gates."
  configure.py
  context.py  — "Deterministic context selection, budgeting, provenance, and inspection."
  discover.py  — "Read-only project discovery for adoption/configuration flows."
  doctor.py
  hooks.py  — "Local hook installation for governed repositories."
  identity.py  — "Per-host / per-instance programmer identity."
  install_agents.py
  integration.py  — "AI-Agents <-> GovernanceKit integration contract inspection."
  issue_bootstrap.py  — "Create local issue/epic scaffolding from installed templates."
  path_safety.py  — "Fail-closed path checks for commands operating below ``--root``."
  project_config.py  — "Project adoption/configuration state for AI-GovernanceKit."
  remove_agents.py  — "Conservative de-adoption planning for an installed AI-Agents kit."
  resume.py
  scope_conversation.py  — "Localized, guided project-scope interview."
  version.py  — "Version reporting for GovernanceKit and its installed AI-Agents policy pack."
  voice.py  — "Optional AI-ListenToMeOnCLI integration detection."
pyproject.toml
scripts/
  notify-nexo.sh
  validate-governance.sh
tests/
  test_adoption.py
  test_advanced_usage_docs.py
  test_agent_scope.py
  test_classification.py
  test_cli_help.py
  test_codemap.py
  test_config_session.py
  test_configure.py
  test_context.py
  test_discover.py
  test_doctor.py
  test_doctor_advisory_scan.py
  test_doctor_gitignore.py
  test_doctor_tracked_secrets.py
  test_hooks.py
  test_install_agents.py
  test_install_agents_integrity.py
  test_install_agents_safe_extract.py
  test_integration.py
  test_issue_bootstrap.py
  test_project_config.py
  test_remove_agents.py
  test_resume.py
  test_scope_conversation.py
  test_version.py
  test_voice.py
```

## Symbol Index

### `governancekit/adoption.py`

> Evidence-based, review-first project adoption used by ``install-agents``.

- **`AdoptionProposal`** *(class)*
  - `as_dict(self)` *(method)*
- **`LlmEnrichmentWarning`** *(class)*
  - `as_dict(self)` *(method)*
- `configured_adoption_provider(root)` — "Return the eligible primary provider without invoking it."
- `provider_label(provider)` — "Render only the non-secret provider identity shown to an operator."
- `build_adoption_proposal(root)`
- `apply_adoption_proposal(proposal)`
- `detect_project_drift(root)` — "Report new observable project facts without rewriting accepted policy."
- `format_adoption_proposal(proposal)`

### `governancekit/agent_scope.py`

> Read-only LLM proposals for project scope adoption.

- **`ProposedDomain`** *(class)*
- **`ScopeProposal`** *(class)*
  - `domain_names` *(property)*
  - `capabilities_for(self, name)` *(method)*
  - `render(self)` *(method)*
- `supported_scope_agents(discovered)`
- `propose_project_scope(root, agent, sources)` — "Ask the selected, locally authenticated agent for a read-only proposal."

### `governancekit/classification.py`

> Architecture change classification workflow.

- **`ChangeClassification`** *(class)*
  - `as_dict(self)` *(method)*
- `build_change_classification()`
- `save_change_classification(root, classification)`
- `load_change_classification(root)`
- `format_change_classification(classification)`

### `governancekit/cli.py`

- `build_parser()`
- `format_doctor(result)`
- `format_doctor_json(result)`
- `format_discovery_json(result)`
- `format_project_config_json(result)`
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

### `governancekit/config_session.py`

> Resumable configuration sessions with explicit approval gates.

- **`ConfigSession`** *(class)*
  - `as_dict(self)` *(method)*
- `start_config_session(root)`
- `load_config_session(root)`
- `grant_config_approval(root, approval)`
- `apply_config_session(root)`
- `format_config_session(session, root)`

### `governancekit/configure.py`

- **`ConfigureResult`** *(class)*
- `parse_set_pairs(pairs)` — "Parse ``KEY=VALUE`` strings from ``--set`` into a mapping."
- **`IdentityResult`** *(class)*
- `run_configure_identity(root)` — "Collect, validate and persist per-host identity fields."
- `run_configure(root)` — "Fill kit placeholder variables only in managed kit files under *root*."

### `governancekit/context.py`

> Deterministic context selection, budgeting, provenance, and inspection.

- **`ContextError`** *(class)* — "A context contract or hard budget limit was violated."
- **`TokenCounter`** *(class)*
  - `count(self, text)` *(method)* — "Return the token count for text."
- **`DeterministicTokenCounter`** *(class)* — "Provider-neutral fallback: one token per four Unicode characters."
  - `count(self, text)` *(method)*
- **`TiktokenCounter`** *(class)* — "Tokenizer-specific estimate, activated only when tiktoken is installed."
  - `__init__(self)` *(method)*
  - `count(self, text)` *(method)*
- `default_token_counter()`
- **`Source`** *(class)*
  - `metadata(self)` *(method)*
- **`ContextResult`** *(class)*
  - `content` *(property)*
  - `as_dict(self, include_content)` *(method)*
- `load_manifest(root, manifest_path)`
- `build_context(root, task, risks, issue, manifest_path, counter, write_telemetry, strict)`
- `prune_telemetry(root, manifest_path, now)`
- `format_context(result)`

### `governancekit/discover.py`

> Read-only project discovery for adoption/configuration flows.

- **`DiscoveryReport`** *(class)*
  - `as_dict(self)` *(method)*
- `run_discover(root, on_top_level_directory)`
- `format_discovery(report)`

### `governancekit/doctor.py`

- **`CheckResult`** *(class)*
- **`DoctorResult`** *(class)*
  - `ok` *(property)*
- `run_doctor(root)`

### `governancekit/hooks.py`

> Local hook installation for governed repositories.

- **`HookInstallResult`** *(class)*
  - `as_dict(self)` *(method)*
- `install_hook(root)`

### `governancekit/identity.py`

> Per-host / per-instance programmer identity.

- **`Identity`** *(class)*
  - `missing_required(self)` *(method)*
  - `complete` *(property)*
  - `to_dict(self)` *(method)*
- `identity_path(root)`
- `load_identity(root)` — "Return the persisted Identity, or None when the file is absent/unreadable."
- `read_existing_operator_name(root)` — "Read an existing local operator value without following credential links."
- `identity_from_values(values)` — "Build an Identity from a flat string mapping (e.g. CLI flags)."
- `save_identity(root, identity)` — "Persist *identity* to the local gitignored file and return its path."
- `ensure_gitignored(root)` — "Ensure the identity file is listed in .gitignore. Returns True if changed."
- `current_branch(root)` — "Return the current git branch, or '' when unavailable."
- `sibling_branch_conflict(identity, branch)` — "Return a warning if the current branch matches the instance's declared"

### `governancekit/install_agents.py`

- **`InstallResult`** *(class)*
- `run_install_agents(root)` — "Download and install AI-Agents kit into *root*."

### `governancekit/integration.py`

> AI-Agents <-> GovernanceKit integration contract inspection.

- **`IntegrationContract`** *(class)*
- **`IntegrationStatus`** *(class)*
- `find_integration_contract(start)`
- `load_integration_contract(path)`
- `inspect_integration_contract(root)`

### `governancekit/issue_bootstrap.py`

> Create local issue/epic scaffolding from installed templates.

- **`IssueBootstrapResult`** *(class)*
- `bootstrap_issue(root)`

### `governancekit/path_safety.py`

> Fail-closed path checks for commands operating below ``--root``.

- **`UnsafePathError`** *(class)* — "A requested path escapes the governed project or traverses a symlink."
- `safe_path(root, path)` — "Return *path* only when it is contained by *root* without symlinks."
- `safe_regular_file(root, path)` — "Whether *path* is a non-symlink regular file safely below *root*."

### `governancekit/project_config.py`

> Project adoption/configuration state for AI-GovernanceKit.

- **`ProviderConfig`** *(class)*
- **`ProjectConfig`** *(class)*
  - `as_dict(self)` *(method)*
- **`PlanAction`** *(class)*
- **`ProjectConfigPlan`** *(class)*
  - `as_dict(self)` *(method)*
- `parse_provider_specs(specs)`
- `provider_warnings(providers)`
- `load_project_config(root)`
- `build_project_config_plan(root)`
- `render_project_config_markdown(config)`
- `apply_project_config_plan(plan)`
- `apply_project_config(root, config)`
- `format_project_config_plan(plan)`

### `governancekit/remove_agents.py`

> Conservative de-adoption planning for an installed AI-Agents kit.

- **`RemovalItem`** *(class)*
- **`RemovalPlan`** *(class)*
  - `as_dict(self)` *(method)*
- **`ApplyResult`** *(class)*
- `build_removal_plan(root)`
- `write_removal_plan(root, plan, output)`
- `load_removal_plan(root, plan_path)`
- `apply_removal_plan(root, plan)`
- `format_removal_plan(plan)`

### `governancekit/resume.py`

- **`HandoffEntry`** *(class)* — "Parsed snapshot from the most recent handoff.md entry."
- **`ResumeResult`** *(class)* — "Context assembled for the start of a new session."
- `run_resume(root)` — "Assemble session-start context from RESUME.md and handoff.md."

### `governancekit/scope_conversation.py`

> Localized, guided project-scope interview.

- **`ScopeConversation`** *(class)*
- **`DomainCandidate`** *(class)*
- `resolve_locale(environ, root)` — "Choose the operational language without relying on a model default."
- `load_required_reading(root)` — "Follow project documentation only when every resolved path stays in root."
- `run_scope_conversation(root)`

### `governancekit/version.py`

> Version reporting for GovernanceKit and its installed AI-Agents policy pack.

- **`VersionInfo`** *(class)*
- `get_version_info(root)`
- `format_version(info)`

### `governancekit/voice.py`

> Optional AI-ListenToMeOnCLI integration detection.

- **`VoiceIntegrationStatus`** *(class)*
  - `as_dict(self)` *(method)*
- `detect_voice_integration(root)`
- `format_voice_integration(status)`

### `tests/test_adoption.py`

- `test_generated_adoption_is_evidence_based_and_sets_readiness(tmp_path)`
- `test_adoption_never_overwrites_complete_project_documents(tmp_path)`
- `test_drift_is_advisory_and_compares_current_discovery_to_accepted_config(tmp_path)`
- `test_configured_primary_llm_enriches_proposal_without_persisting_credentials(tmp_path, monkeypatch)`
- `test_configured_primary_llm_is_not_invoked_without_explicit_enrichment(tmp_path, monkeypatch)`
- `test_provider_failure_names_configured_provider_and_model(tmp_path, monkeypatch)`
- `test_invalid_llm_evidence_explains_the_expected_operator_action(tmp_path, monkeypatch)`

### `tests/test_advanced_usage_docs.py`

- `test_advanced_guide_documents_every_cli_parameter()`
- `test_credentials_allow_symlinks_is_an_interactive_scope_option()`
- `test_landing_links_advanced_guide_and_identity_is_unambiguous()`
- `test_advanced_guide_is_available_in_all_landing_languages()`
- `test_landing_navigation_is_translated_compact_and_agents_install_is_separate()`
- `test_default_agents_release_is_current_and_checksum_pinned()`
- `test_cli_help_uses_real_upstream_owner()`

### `tests/test_agent_scope.py`

- `test_codex_scope_proposal_is_read_only_and_parsed(tmp_path, monkeypatch)`
- `test_scope_proposal_rejects_evidence_outside_selected_sources(tmp_path, monkeypatch)`
- `test_cursor_scope_adapter_trusts_only_the_generated_workspace(tmp_path)`
- `test_scope_proposal_labels_domains_capabilities_and_open_questions()`
- `test_provider_failure_detail_does_not_expose_response_data()`
- `test_llm_scope_adapter_reads_a_project_local_protected_credential_file(tmp_path, monkeypatch)`
- `test_llm_scope_adapter_allows_a_credential_symlink_when_explicitly_enabled(tmp_path, monkeypatch)`
- `test_llm_scope_adapter_rejects_a_credential_symlink_outside_the_trusted_root(tmp_path)`

### `tests/test_classification.py`

- `test_build_requires_valid_labels()`
- `test_save_and_load_roundtrip(tmp_path)`
- `test_cli_plan_apply_show_roundtrip(tmp_path, capsys)`

### `tests/test_cli_help.py`

- `test_main_without_command_prints_expanded_help()`
- `test_format_doctor_indents_multiline_messages(tmp_path)`
- `test_install_agents_prints_identity_setup_for_unconfigured_host(monkeypatch, tmp_path)`
- `test_install_agents_prints_identity_setup_for_incomplete_identity(monkeypatch, tmp_path)`
- `test_upgrade_announces_project_analysis_duration(monkeypatch, tmp_path)`
- `test_install_agents_does_not_report_optional_awt_as_manual_step(monkeypatch, tmp_path)`
- `test_install_agents_silently_skips_optional_awt(monkeypatch, tmp_path)`
- `test_install_agents_asks_before_using_configured_llm(monkeypatch, tmp_path)`
- `test_docs_only_does_not_modify_root_gitignore(monkeypatch, tmp_path)`

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
  - `test_output_has_summary_governance_and_ignored_layers(self)` *(method)*
  - `test_custom_output_path(self)` *(method)*
  - `test_file_and_symbol_counts(self)` *(method)*
  - `test_codemap_not_in_own_output(self)` *(method)*
  - `test_gitignore_excludes_files(self)` *(method)*
  - `test_skips_symlinked_directory_outside_root(self)` *(method)*
  - `test_refuses_output_outside_root(self)` *(method)*

### `tests/test_config_session.py`

- `test_session_requires_approvals_before_apply(tmp_path, capsys)`
- `test_show_session_as_json(tmp_path, capsys)`
- `test_approval_output_explains_next_command(tmp_path, capsys)`
- `test_session_commands_quote_root_with_spaces(tmp_path)`
- `test_session_rejects_configured_provider_without_credential_reference(tmp_path, capsys)`

### `tests/test_configure.py`

- **`ConfigureTests`** *(class)*
  - `test_set_pairs_parsing(self)` *(method)*
  - `test_fills_known_placeholder_without_touching_project_docs(self)` *(method)*
  - `test_ignores_unknown_tokens(self)` *(method)*
  - `test_reports_unfilled(self)` *(method)*
  - `test_ignores_placeholders_in_migration_backup(self)` *(method)*
  - `test_refuses_symlinked_managed_file(self)` *(method)*
  - `test_ignores_credential_symlinks(self)` *(method)*
- **`ConfigureIdentityTests`** *(class)*
  - `test_all_branch_ownership_allows_any_branch(self)` *(method)*
  - `test_non_interactive_missing_required_does_not_save(self)` *(method)*
  - `test_identity_prefills_existing_operator_and_checkout_path(self)` *(method)*
  - `test_identity_does_not_follow_credential_identity_symlink(self)` *(method)*
  - `test_non_interactive_complete_saves_and_gitignores(self)` *(method)*
  - `test_gitignore_entry_not_duplicated(self)` *(method)*
  - `test_cli_configure_set_ok_when_identity_unconfigured(self)` *(method)*
  - `test_cli_configure_errors_when_identity_flags_incomplete(self)` *(method)*
  - `test_bracketed_policy_markers_are_not_treated_as_placeholders(self)` *(method)*

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
- `test_reserve_reduces_usable_budget_and_declared_order_is_preserved(tmp_path)`
- `test_required_retrieve_without_match_fails(tmp_path)`
- `test_inspect_mode_returns_hard_violations_instead_of_raising(tmp_path)`
- `test_containment_detects_small_document_inside_large_one(tmp_path)`
- `test_telemetry_has_timestamp_and_prune_applies_retention(tmp_path)`

### `tests/test_discover.py`

- `test_reports_new_project_when_only_governance_files_exist(tmp_path)`
- `test_reports_existing_python_project(tmp_path)`
- `test_detects_node_frameworks_and_scripts(tmp_path)`
- `test_detects_available_agents(tmp_path)`
- `test_human_format_is_stable(tmp_path)`
- `test_discovery_reports_top_level_folders_and_skips_nested_git_roots(tmp_path)`

### `tests/test_doctor.py`

- **`DoctorTests`** *(class)*
  - `test_valid_repository_passes(self)` *(method)*
  - `test_missing_limits_ready_flag_fails(self)` *(method)*
  - `test_empty_resume_next_step_fails(self)` *(method)*
  - `test_missing_required_reading_fails(self)` *(method)*
  - `test_required_reading_none_sentinel_passes(self)` *(method)*
  - `test_required_reading_none_fails_when_legacy_agents_are_orphaned(self)` *(method)*
  - `test_legacy_rule_traps_warn_without_blocking_ready_repo(self)` *(method)*
  - `test_required_reading_fails_for_missing_listed_path(self)` *(method)*
  - `test_existing_config_requires_integration_contract(self)` *(method)*
  - `test_manifest_missing_tracked_path_fails(self)` *(method)*
  - `test_required_reading_only_stub_fails(self)` *(method)*
  - `test_codemap_requires_current_layered_format(self)` *(method)*
  - `test_missing_identity_file_fails(self)` *(method)*
  - `test_incomplete_identity_file_fails(self)` *(method)*
  - `test_complete_identity_file_passes(self)` *(method)*
  - `test_policy_markers_do_not_fail_placeholder_check(self)` *(method)*
  - `test_placeholder_guidance_uses_configure(self)` *(method)*
  - `test_missing_project_config_is_advisory_only(self)` *(method)*
  - `test_present_project_config_is_reported(self)` *(method)*
  - `test_provider_without_credential_ref_is_advisory(self)` *(method)*
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
  - `test_known_scaffolding_markers_are_not_tracked_secrets(self)` *(method)*
  - `test_credentials_translated_readme_is_not_a_tracked_secret(self)` *(method)*
  - `test_env_local_is_still_a_tracked_secret(self)` *(method)*
  - `test_real_credentials_file_is_still_a_tracked_secret(self)` *(method)*
  - `test_example_suffix_does_not_whitelist_a_key_by_name(self)` *(method)*

### `tests/test_hooks.py`

- `test_install_pre_commit_hook(tmp_path)`
- `test_existing_hook_requires_force(tmp_path)`

### `tests/test_install_agents.py`

- **`InstallAgentsTests`** *(class)*
  - `test_dest_rel_maps_kit_docs_but_not_project(self)` *(method)*
  - `test_resolve_src_prefers_dotdocs_source(self)` *(method)*
  - `test_fresh_install_reads_dotdocs_source(self)` *(method)*
  - `test_ensure_project_docs_creates_once(self)` *(method)*
  - `test_ensure_project_docs_adds_missing_index_to_existing_docs(self)` *(method)*
  - `test_docs_only_installs_into_dotdocs(self)` *(method)*
  - `test_upgrade_preserves_project_authored_agent(self)` *(method)*
  - `test_upgrade_retires_untouched_kit_file(self)` *(method)*
  - `test_upgrade_keeps_locally_edited_kit_file(self)` *(method)*
  - `test_state_roundtrip_and_merge(self)` *(method)*
  - `test_full_upgrade_state_prunes_missing_paths_but_docs_only_does_not(self)` *(method)*
  - `test_metadata_reapplied_without_a_terminal(self)` *(method)*
  - `test_unknown_metadata_survives_as_unfilled(self)` *(method)*
  - `test_state_hash_matches_file_after_placeholder_fill(self)` *(method)*
  - `test_edited_kit_file_is_stashed_before_being_replaced(self)` *(method)*
  - `test_unedited_kit_file_is_replaced_without_stashing(self)` *(method)*
  - `test_secrets_ignored_but_manifest_shared(self)` *(method)*
  - `test_operator_and_secrets_split_from_shareable_metadata(self)` *(method)*
  - `test_no_secrets_file_when_nothing_sensitive(self)` *(method)*
  - `test_legacy_manifest_operator_metadata_is_ignored_until_reentered(self)` *(method)*
  - `test_operator_metadata_is_not_shared_in_manifest_after_rewrite(self)` *(method)*
  - `test_gitignore_uses_dotdocs_and_leaves_docs_tracked(self)` *(method)*
  - `test_gitignore_tracks_kit_docs_when_opted_in(self)` *(method)*
  - `test_gitignore_section_keeps_secrets_across_modes(self)` *(method)*
  - `test_track_config_persists_and_is_read(self)` *(method)*
  - `test_migrate_legacy_layout_moves_kit_and_promotes_project(self)` *(method)*
  - `test_migrate_ignores_non_kit_project_with_generic_docs(self)` *(method)*
  - `test_migrate_completes_interrupted_run_without_overwriting(self)` *(method)*
  - `test_required_reading_stays_project_owned(self)` *(method)*
  - `test_content_migration_extracts_only_project_or_changed_contracts(self)` *(method)*
  - `test_upgrade_refuses_orphaned_content_without_explicit_migration(self)` *(method)*
  - `test_upgrade_refuses_symlinked_managed_directory(self)` *(method)*
  - `test_fill_placeholders_ignores_doc_example_tokens(self)` *(method)*
  - `test_fill_placeholders_only_supports_canonical_syntax(self)` *(method)*

### `tests/test_install_agents_integrity.py`

- **`DefaultRefPinTests`** *(class)*
  - `test_default_ref_is_not_the_mutable_main_branch(self)` *(method)*
  - `test_default_repo_ref_has_a_known_checksum(self)` *(method)*
  - `test_amazon_q_adapter_is_installed_and_upgraded(self)` *(method)*
- **`DownloadChecksumTests`** *(class)*
  - `test_matching_checksum_is_accepted(self)` *(method)*
  - `test_mismatched_checksum_is_rejected_before_extraction(self)` *(method)*

### `tests/test_install_agents_safe_extract.py`

- **`SafeExtractallTests`** *(class)*
  - `test_extracts_normal_members(self)` *(method)*
  - `test_rejects_path_traversal_member(self)` *(method)*
  - `test_absolute_path_member_stays_inside_dest(self)` *(method)*

### `tests/test_integration.py`

- `write_contract(root)`
- `test_reports_missing_contract(tmp_path)`
- `test_reports_compatible_contract(tmp_path)`
- `test_reports_incompatible_contract(tmp_path)`
- `test_custom_repo_contract_is_advisory(tmp_path)`

### `tests/test_issue_bootstrap.py`

- `test_bootstrap_issue_uses_project_config_and_classification(tmp_path)`
- `test_bootstrap_issue_normalizes_unicode_titles(tmp_path)`

### `tests/test_project_config.py`

- `test_build_plan_uses_discovery_defaults(tmp_path)`
- `test_apply_writes_shareable_files(tmp_path)`
- `test_parse_provider_specs_supports_modes_and_refs()`
- `test_guided_provider_purpose_persists_without_a_secret(tmp_path)`
- `test_cli_plan_and_apply_roundtrip(tmp_path, capsys)`

### `tests/test_remove_agents.py`

- `digest(value)`
- `make_installed(root)`
- `test_plan_classifies_exact_manifest_file_as_removable(tmp_path)`
- `test_plan_preserves_modified_or_unknown_files(tmp_path)`
- `test_apply_creates_backup_before_removing_only_verified_files(tmp_path)`
- `test_cli_plan_writes_json_and_apply_uses_it(tmp_path, capsys)`
- `test_plan_output_cannot_escape_root(tmp_path)`
- `test_llm_extraction_moves_project_content_only_after_explicit_acceptance(tmp_path)`

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

### `tests/test_scope_conversation.py`

- `test_locale_prefers_operational_ptbr()`
- `test_neutral_shell_uses_project_language_before_inherited_language(tmp_path)`
- `test_nvidia_preset_uses_its_openai_compatible_endpoint()`
- `test_provider_catalog_lists_nvidia_nim_as_openai_compatible(capsys)`
- `test_provider_help_limits_llm_use_to_the_scope_interview(capsys)`
- `test_domain_selection_can_accept_the_complete_agent_proposal(capsys)`
- `test_domain_candidates_merge_declared_and_llm_origins_without_merging_similar_names()`
- `test_legacy_pending_adoption_baseline_does_not_override_scope_proposal(tmp_path)`
- `test_analysis_notice_explains_the_delay_and_read_only_boundary(capsys)`
- `test_created_credential_file_is_private_and_not_part_of_provider_config(tmp_path)`
- `test_manual_placeholder_is_not_presented_as_a_saved_llm_provider()`
- `test_provider_interview_can_create_a_hidden_local_credential_file(tmp_path, monkeypatch, capsys)`
- `test_detected_nvidia_credential_uses_the_nim_preset_without_reading_the_secret(tmp_path, monkeypatch)`
- `test_provider_interview_offers_a_detected_nvidia_configuration(tmp_path, monkeypatch, capsys)`
- `test_load_required_reading_rejects_traversal_and_symlink_escape(tmp_path)`
- `test_ptbr_interview_guides_provider_and_retries_invalid_role(tmp_path, monkeypatch, capsys)`
- `test_scope_conversation_reuses_pending_configuration_as_defaults(tmp_path, monkeypatch, capsys)`

### `tests/test_version.py`

- `write_manifest(root, ref, repo)`
- `test_reports_runtime_and_default_without_project(tmp_path)`
- `test_finds_project_manifest_from_nested_directory(tmp_path)`
- `test_reports_upgrade_when_project_ref_is_older(tmp_path)`
- `test_custom_repository_is_not_compared_as_an_upgrade(tmp_path)`
- `test_human_format_contains_all_versions(tmp_path)`

### `tests/test_voice.py`

- `test_voice_detection_reports_absent_by_default(tmp_path)`
- `test_voice_detection_uses_env_override(tmp_path, monkeypatch)`

