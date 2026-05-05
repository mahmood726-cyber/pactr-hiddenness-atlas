#!/usr/bin/env bash
# scripts/release_v010.sh — Task 22 v0.1.0 release ritual orchestrator.
#
# Requires: Git Bash (Windows) or any POSIX-compatible shell (macOS/Linux).
# Run from the repo root.
#
# Usage:
#   bash scripts/release_v010.sh                                     # DRY-RUN (default)
#   bash scripts/release_v010.sh --execute                           # perform each step; halt on FAIL
#   bash scripts/release_v010.sh --execute --ack-spotcheck-disagreement
#                                                                    # acknowledge documented spot-check
#                                                                    # failure (Amendment 2) and continue
#
# Default mode is DRY-RUN.  Pass --execute to make destructive operations real.
# The script halts on the first FAIL (set -euo pipefail) UNLESS the failure is
# the validation_gates spot-check AND --ack-spotcheck-disagreement is set, in
# which case the failure is logged and the v0.1.0 tag annotation records it.
# This is for v0.1.0 only — see AMENDMENTS.md Amendment 2 for the rationale.
#
# Steps covered:
#   1  Preflight reminder (paths.toml + snapshot integrity)
#   2  Run pipeline against real ICTRP/CDSR data
#   3  Build dashboard from real atlas.csv
#   4  (MANUAL — not executed) 30-trial spot-check
#   5  Validation gates (TrialScout sanity + spot-check + ensemble disagreement)
#   6  Fill paper placeholders (produces *.filled; human reviews before overwrite)
#   7  Commit baseline + spotcheck + filled papers
#   8  Tag v0.1.0 and push
#   9  OTS-stamp baseline + spotcheck; commit + push
#  10  Internet Archive snapshot of v0.1.0 tag tree
#  11  Pages confirmation reminder
#  12  Workbook + memory bookkeeping reminder
#
# NOT automated:
#   Step 4  — 30-trial spot-check is always a human step.
#   Step 6  — paper review after fill; user must inspect .filled and cp manually.
#   Step 10 — IA FINAL_URL must be pasted into the manifest by the user.

set -euo pipefail

# ---------------------------------------------------------------------------
# Mode
# ---------------------------------------------------------------------------
DRY_RUN=1
ACK_SPOTCHECK=0
for arg in "$@"; do
    case "$arg" in
        --execute) DRY_RUN=0 ;;
        --ack-spotcheck-disagreement) ACK_SPOTCHECK=1 ;;
        *) echo "unknown arg: $arg" >&2; exit 2 ;;
    esac
done

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

run() {
    # In dry-run mode: print the command. In execute mode: run it.
    if [[ $DRY_RUN -eq 1 ]]; then
        echo "  [DRY] $*"
    else
        echo "  [RUN] $*"
        eval "$*"
    fi
}

halt_unless() {
    # Always evaluated (even in dry-run) — pre-conditions are not optional.
    local description="$1"
    local cmd="$2"
    if eval "$cmd" >/dev/null 2>&1; then
        echo "  + precondition OK: $description"
    else
        echo "  ! FAIL precondition: $description"
        echo "  ! command was: $cmd"
        exit 1
    fi
}

banner() {
    echo ""
    echo "=== $* ==="
}

# ---------------------------------------------------------------------------
# Pre-conditions (always checked, even in dry-run)
# ---------------------------------------------------------------------------
banner "Pre-conditions"

halt_unless "paths.toml exists" "[[ -f paths.toml ]]"
halt_unless "spotcheck CSV exists (Step 4 must be done first)" \
    "[[ -f data/processed/spotcheck_v0.1.0.csv ]]"
halt_unless "prereg manifest verifies" \
    "python scripts/verify_prereg.py"
halt_unless "git working tree is clean" \
    "[[ -z \"\$(git status --porcelain)\" ]]"

# ---------------------------------------------------------------------------
# Step 1 — Preflight
# ---------------------------------------------------------------------------
banner "Step 1: Preflight (paths.toml snapshot integrity)"
run "python -m pilots.preflight"

# ---------------------------------------------------------------------------
# Step 2 — Run pipeline against real data
# ---------------------------------------------------------------------------
banner "Step 2: Run pipeline against real ICTRP/CDSR data"
run "python -m pilots.run_all"

# ---------------------------------------------------------------------------
# Step 3 — Build dashboard
# ---------------------------------------------------------------------------
banner "Step 3: Build dashboard from real atlas.csv"
run "python -c \"import pandas as pd; from pactr_atlas.dashboard_builder import build_dashboard; build_dashboard(pd.read_csv('data/processed/atlas.csv'), 'dashboard')\""

# ---------------------------------------------------------------------------
# Step 4 — MANUAL (not executed)
# ---------------------------------------------------------------------------
banner "Step 4 (MANUAL — not executed by this script)"
echo "  Perform 30-trial spot-check by hand:"
echo "    seed=20260503; sample 30 trials at random; verify gate verdicts;"
echo "    record each trial's gates in data/processed/spotcheck_v0.1.0.csv"
echo "    per Task 21 §3 schema."
echo "  Continue only after spotcheck CSV has exactly 30 rows."

# ---------------------------------------------------------------------------
# Step 5 — Validation gates
# ---------------------------------------------------------------------------
banner "Step 5: Validation gates (TrialScout sanity + spotcheck + ensemble)"
if [[ $ACK_SPOTCHECK -eq 1 ]]; then
    if [[ $DRY_RUN -eq 1 ]]; then
        echo "  [DRY] python scripts/validation_gates.py  (acknowledged failure mode)"
    else
        echo "  [RUN] python scripts/validation_gates.py  (--ack-spotcheck-disagreement set)"
        if python scripts/validation_gates.py; then
            echo "  + validation_gates PASSED"
        else
            echo "  ! validation_gates FAILED — acknowledged per AMENDMENTS.md Amendment 2"
            echo "  ! the v0.1.0 tag annotation will record this acknowledgment"
        fi
    fi
else
    run "python scripts/validation_gates.py"
fi

# ---------------------------------------------------------------------------
# Step 6 — Fill paper placeholders
# ---------------------------------------------------------------------------
banner "Step 6: Fill paper placeholders"
run "python scripts/fill_paper_placeholders.py"
echo "  REVIEW: open and check these files before proceeding:"
echo "    e156-submission/body.md.filled"
echo "    e156-submission/synthesis-methods-note.md.filled"
echo "  If satisfied:"
echo "    cp e156-submission/body.md.filled e156-submission/body.md"
echo "    cp e156-submission/synthesis-methods-note.md.filled e156-submission/synthesis-methods-note.md"
echo "    python scripts/validate_e156_body.py"
echo "    python scripts/validate_synthesis_note.py"
echo "  Then re-run with --execute to proceed from Step 7."

# ---------------------------------------------------------------------------
# Step 7 — Commit baseline + spotcheck + filled papers
# ---------------------------------------------------------------------------
banner "Step 7: Commit baseline + spotcheck + filled papers"
run "git add data/processed/atlas_baseline.csv \
         data/processed/spotcheck_v0.1.0.csv \
         e156-submission/body.md \
         e156-submission/synthesis-methods-note.md"
run "git commit -m 'release: v0.1.0 atlas baseline + spotcheck + filled papers'"

# ---------------------------------------------------------------------------
# Step 8 — Tag and push
# ---------------------------------------------------------------------------
banner "Step 8: Tag v0.1.0 and push"
if [[ $ACK_SPOTCHECK -eq 1 ]]; then
    TAG_MSG="v0.1.0: NCT-bridge-vs-blinded-auditor methodology calibration on 10-condition African PACTR subset. Spot-check returned 0/30 verdict-level agreement; the disagreement IS the substantive finding (algorithm gate2 sensitivity ~6.3%). Acknowledged release per AMENDMENTS.md Amendment 2."
else
    TAG_MSG="v0.1.0: 10-condition Africa-burden hiddenness funnel; engine-only release."
fi
run "git tag -a v0.1.0 -m '$TAG_MSG'"
run "git push origin master --tags"

# ---------------------------------------------------------------------------
# Step 9 — OTS-stamp baseline + spotcheck
# ---------------------------------------------------------------------------
banner "Step 9: OTS-stamp baseline + spotcheck"
run "python scripts/stamp_file.py \
         data/processed/atlas_baseline.csv \
         data/processed/spotcheck_v0.1.0.csv"
run "git add data/processed/atlas_baseline.csv.ots \
             data/processed/spotcheck_v0.1.0.csv.ots"
run "git commit -m 'release: OTS anchor on v0.1.0 baseline + spotcheck'"
run "git push origin master"

# ---------------------------------------------------------------------------
# Step 10 — Internet Archive snapshot of v0.1.0 tag tree
# ---------------------------------------------------------------------------
banner "Step 10: Internet Archive snapshot of v0.1.0 tag tree"
run "curl -sS -o /dev/null \
         -w 'HTTP=%{http_code}\nFINAL_URL=%{url_effective}\n' \
         -L 'https://web.archive.org/save/https://github.com/mahmood726-cyber/pactr-hiddenness-atlas/tree/v0.1.0' \
         --max-time 180"
echo "  ACTION (manual): copy the FINAL_URL printed above."
echo "  Append it to .preregistration_commit.txt under a new 'Release v0.1.0' section,"
echo "  then: git add .preregistration_commit.txt && git commit -m 'docs: IA snapshot of v0.1.0 tag' && git push origin master"

# ---------------------------------------------------------------------------
# Step 11 — Pages confirmation
# ---------------------------------------------------------------------------
banner "Step 11: Pages confirmation"
echo "  Check GitHub Pages is live and rendering real data:"
echo "    https://mahmood726-cyber.github.io/pactr-hiddenness-atlas/"
echo "  Should redirect to dashboard/index.html populated from real atlas.csv."

# ---------------------------------------------------------------------------
# Step 12 — Workbook + memory bookkeeping
# ---------------------------------------------------------------------------
banner "Step 12: Workbook + memory bookkeeping"
echo "  Append to C:/E156/rewrite-workbook.txt:"
echo "    project name, dates, 156-word body, dashboard link, SUBMITTED: [ ],"
echo "    increment total count."
echo ""
echo "  Update memory file (path varies by user — see MEMORY.md for location):"
echo "    pactr-hiddenness-atlas.md — bump status to 'v0.1.0 shipped';"
echo "    record headline percentage and TrialScout sanity outcome."
echo ""
echo "  Update MEMORY.md with the v0.1.0 line."

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
banner "release_v010.sh complete"
if [[ $DRY_RUN -eq 1 ]]; then
    echo "(DRY-RUN mode — nothing was actually executed.)"
    echo "Re-run with --execute to perform each step for real."
fi
