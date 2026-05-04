#!/usr/bin/env bash
# scripts/install_sentinel_hook.sh
# Per AGENTS.md / portfolio rule: install the Sentinel pre-push rule
# engine for this repo. Project-local rule: any commit touching src/,
# pilots/, or tests/ before .preregistration_commit.txt exists -> BLOCK.
#
# Prerequisite: .preregistration_commit.txt must exist (created by
# verify_prereg.py at preregistration time; anchors spec sha256 + OTS).
#
# Usage:
#   bash scripts/install_sentinel_hook.sh           # block mode (default for this repo)
#   SENTINEL_MODE=warn bash scripts/install_sentinel_hook.sh
#
# Manual install fallback (if python -m sentinel is unavailable):
#   python -c "
#   import sys, pathlib
#   sys.path.insert(0, r'C:\\Sentinel')
#   from sentinel import install_hook
#   install_hook.run(repo='.')
#   "
#   Or copy C:\Sentinel\sentinel\hooks\pre-push.tmpl -> .git/hooks/pre-push
#   and make it executable.
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"

if [[ ! -f "$REPO/.preregistration_commit.txt" ]]; then
    echo "REFUSING: .preregistration_commit.txt missing — Sentinel install requires the prereg manifest first." >&2
    exit 1
fi

# Default to block mode for this repo (preregistration integrity matters).
MODE="${SENTINEL_MODE:-block}"

python -m sentinel install-hook --repo "$REPO" --mode "$MODE"
echo "Sentinel hook installed in $MODE mode; project-local rule armed."
echo "Override per-push: SENTINEL_MODE=warn git push"
