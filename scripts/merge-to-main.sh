#!/usr/bin/env bash
# Merge development into main WITHOUT this repository's session memory.
#
# Session memory — issue artifacts, napkin lessons, handoff — is how the work gets
# done; it is not the product. It records what happened here, names the projects a
# lesson came from, and grows every session. main is what gets tagged and what an
# installer downloads, so it carries the product only.
#
# The exclusion is re-applied on every run: development keeps the files, main never
# has them, and a merge that reintroduces them resolves by removing them again.
#
# Usage:
#   scripts/merge-to-main.sh [--from <branch>] [--dry-run]
set -euo pipefail

# `git checkout main` below can remove this file from the worktree mid-run — main
# does not carry it until the first merge lands — and bash reads a script
# incrementally, so it would fail halfway. Re-exec from a copy that no branch owns.
if [[ "${MERGE_TO_MAIN_REEXEC:-}" != "1" ]]; then
  _self_copy="$(mktemp)"
  cat "$0" > "$_self_copy"
  MERGE_TO_MAIN_REEXEC=1 exec bash "$_self_copy" "$@"
fi
rm -f -- "$0"   # unlinked but still open: the copy cannot outlive this run

FROM="development"
DRY_RUN="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from) FROM="$2"; shift 2 ;;
    --dry-run) DRY_RUN="1"; shift ;;
    -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done

# Paths that must never reach main. Directories and files both work.
EXCLUDED=(
  "docs/issues"
  "docs/napkin-lessons.md"
  "handoff.md"
)

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: working tree is dirty; commit or stash first." >&2
  exit 3
fi
if ! git rev-parse --verify --quiet "$FROM" >/dev/null; then
  echo "ERROR: source branch does not exist: $FROM" >&2
  exit 3
fi

if [[ "$DRY_RUN" == "1" ]]; then
  echo "Would merge $FROM into main, then drop from main:"
  for p in "${EXCLUDED[@]}"; do
    if git cat-file -e "$FROM:$p" 2>/dev/null || git ls-tree -d --name-only "$FROM" -- "$p" | grep -q .; then
      echo "  - $p"
    else
      echo "  - $p (absent in $FROM)"
    fi
  done
  exit 0
fi

git checkout main

# A merge that only touches excluded paths still has to be recorded, so --no-commit
# is always used and the commit is made here, after the exclusion is applied.
if ! git merge --no-ff --no-commit "$FROM"; then
  echo "Merge reported conflicts; resolving the excluded paths by removal."
fi

for p in "${EXCLUDED[@]}"; do
  git rm -r -q --cached --ignore-unmatch -- "$p" || true
  rm -rf -- "${ROOT:?}/$p"
done

unresolved="$(git diff --name-only --diff-filter=U)"
if [[ -n "$unresolved" ]]; then
  echo "ERROR: conflicts remain outside the excluded paths:" >&2
  echo "$unresolved" >&2
  echo "Resolve them, then: git commit" >&2
  exit 4
fi

git commit -q -m "merge: $FROM into main (session memory excluded)"
echo "Merged $FROM into main; session memory kept out of main."
git --no-pager log --oneline -1
