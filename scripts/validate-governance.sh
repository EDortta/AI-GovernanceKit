#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$(pwd)}"

# Data files this kit ships must agree with what they claim to be derived from. Neither
# refresh script was wired to any gate, so both could go stale in silence while their
# own docstrings promised that "a release runner can prove" they were current.
#
# FIRST, and advisory. First because `doctor` exits non-zero on any governed project
# with an open finding, and `set -e` would mean these never ran at all — a gate placed
# after a failing command is a gate that only fires when nothing is wrong. Advisory
# because an unreachable source is not a broken repository: the stored data keeps
# working and carries its own `generated_at`.
# Resolved against THIS script, not the caller's cwd: the script takes its target as
# $1 and never cd's, so relative paths made the whole loop skip in silence from
# anywhere but the repository root — a gate that only fires where you already are.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for refresh in "$HERE/refresh-kit-snapshot.py" "$HERE/refresh-llm-catalog.py"; do
  [ -f "$refresh" ] || continue
  if ! python3 "$refresh" --check; then
    echo "WARN: $refresh --check did not pass; the data it guards may be stale." >&2
  fi
done

python3 -m governancekit.cli --root "$ROOT" doctor --json
python3 -m governancekit.cli --root "$ROOT" discover --json
