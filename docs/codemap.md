# Code Map · ai-governancekit

> Generated: 2026-05-08 · Root: `[PROJECT_ROOT]Sync/Projects/AI-GovernanceKit`  
> Refresh: `governancekit map`

10 file(s) · 70 symbol(s) indexed

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
  doctor.py
  resume.py
pyproject.toml
tests/
  test_codemap.py
  test_doctor.py
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

### `governancekit/doctor.py`

- **`CheckResult`** *(class)*
- **`DoctorResult`** *(class)*
  - `ok` *(property)*
- `run_doctor(root)`

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
  - `test_creates_output_file(self)` *(method)*
  - `test_output_contains_project_name(self)` *(method)*
  - `test_output_contains_symbol(self)` *(method)*
  - `test_custom_output_path(self)` *(method)*
  - `test_file_and_symbol_counts(self)` *(method)*
  - `test_codemap_not_in_own_output(self)` *(method)*
  - `test_gitignore_excludes_files(self)` *(method)*

### `tests/test_doctor.py`

- **`DoctorTests`** *(class)*
  - `test_valid_repository_passes(self)` *(method)*
  - `test_missing_limits_ready_flag_fails(self)` *(method)*
  - `test_empty_resume_next_step_fails(self)` *(method)*
- `write_valid_repo(root)`
- `failed_check_names(result)`

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

