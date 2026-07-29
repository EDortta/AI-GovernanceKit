#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$(pwd)}"

python3 -m governancekit.cli --root "$ROOT" doctor --json
python3 -m governancekit.cli --root "$ROOT" discover --json
