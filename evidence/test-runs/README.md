# Test-run evidence

Run the repository test harness with:

```bash
bash scripts/test-with-evidence.sh
```

The harness is safe to rerun. It reuses the repository-local `.venv`, installs the
current checkout in editable mode, invokes pytest through that exact interpreter,
and refuses to continue if `governancekit` resolves outside this checkout.

Each execution creates:

```text
evidence/test-runs/YYYY-MM-DD-HH-MM-SS/
  environment.txt
  install.txt
  pytest.txt
  summary.txt
```

`evidence/test-runs/LATEST` contains the directory name of the most recent run.

These files deliberately use `.txt` rather than `.log` because repository test
evidence is meant to be reviewable and committable. No credentials or environment
variable values are recorded.
