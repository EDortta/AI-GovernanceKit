#!/usr/bin/env bash
set -u
set -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y-%m-%d-%H-%M-%S)"
EVIDENCE_ROOT="$ROOT/evidence/test-runs"
RUN_DIR="$EVIDENCE_ROOT/$STAMP"
LATEST_FILE="$EVIDENCE_ROOT/LATEST"
VENV="$ROOT/.venv"
PY="$VENV/bin/python"

mkdir -p "$RUN_DIR"

summary="$RUN_DIR/summary.txt"
env_file="$RUN_DIR/environment.txt"
install_file="$RUN_DIR/install.txt"
pytest_file="$RUN_DIR/pytest.txt"

finish() {
  local rc="$1"
  {
    echo "timestamp=$STAMP"
    echo "exit_code=$rc"
    echo "result=$([[ "$rc" -eq 0 ]] && echo PASS || echo FAIL)"
    echo "evidence_dir=evidence/test-runs/$STAMP"
  } > "$summary"
  printf '%s\n' "$STAMP" > "$LATEST_FILE"

  echo
  if [[ "$rc" -eq 0 ]]; then
    echo "TEST RESULT: PASS"
  else
    echo "TEST RESULT: FAIL (exit $rc)"
  fi
  echo "Evidence: evidence/test-runs/$STAMP"
  return "$rc"
}

{
  echo "AI-GovernanceKit test evidence"
  echo "timestamp=$STAMP"
  echo "root=$ROOT"
  echo "branch=$(git branch --show-current 2>/dev/null || true)"
  echo "head=$(git rev-parse HEAD 2>/dev/null || true)"
  echo "python3=$(command -v python3 || true)"
  python3 --version 2>&1 || true
  echo
  echo "[git status before]"
  git status --short 2>/dev/null || true
} > "$env_file"

if [[ ! -x "$PY" ]]; then
  echo "Creating isolated virtual environment at .venv" | tee "$install_file"
  if ! python3 -m venv "$VENV" >> "$install_file" 2>&1; then
    echo "ERROR: could not create .venv" | tee -a "$install_file"
    finish 20
    exit $?
  fi
else
  echo "Reusing isolated virtual environment at .venv" | tee "$install_file"
fi

echo "Installing this checkout and test runner into .venv" | tee -a "$install_file"
if ! env PYTHONNOUSERSITE=1 "$PY" -m pip install -e . pytest >> "$install_file" 2>&1; then
  echo "ERROR: dependency/install step failed" | tee -a "$install_file"
  finish 21
  exit $?
fi

{
  echo
  echo "[isolated interpreter]"
  env PYTHONNOUSERSITE=1 "$PY" - <<'PY'
import sys
import governancekit
print(f"sys.executable={sys.executable}")
print(f"governancekit.__file__={governancekit.__file__}")
print(f"governancekit.__version__={governancekit.__version__}")
PY
} >> "$env_file" 2>&1

module_path="$(
  env PYTHONNOUSERSITE=1 "$PY" - <<'PY'
from pathlib import Path
import governancekit
print(Path(governancekit.__file__).resolve())
PY
)"

case "$module_path" in
  "$ROOT"/governancekit/*) ;;
  *)
    echo "ERROR: governancekit imported from outside this checkout: $module_path" | tee -a "$env_file"
    finish 22
    exit $?
    ;;
esac

echo "Running pytest with the .venv interpreter" | tee "$pytest_file"
set +e
env   PYTHONNOUSERSITE=1   PYTEST_DISABLE_PLUGIN_AUTOLOAD=1   PYTHONPATH="$ROOT"   "$PY" -m pytest -ra "$@" 2>&1 | tee -a "$pytest_file"
pytest_rc=${PIPESTATUS[0]}
set -e

{
  echo
  echo "[git status after]"
  git status --short 2>/dev/null || true
} >> "$env_file"

finish "$pytest_rc"
exit $?
