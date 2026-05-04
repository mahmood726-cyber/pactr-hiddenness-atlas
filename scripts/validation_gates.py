"""Pre-ship validation per spec §11d:

  1. TrialScout sanity:  cross-registered subset gate0->gate2 within
                         +/- 10pp of 63.6%.
  2. 30-trial spot-check: project-lead audit; require >= 27/30.
  3. Ensemble disagreement: gate3_ensemble_disagree count < 5% of
                            gate3_in_cochrane count.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

TRIALSCOUT_BASELINE = 0.636
TRIALSCOUT_TOLERANCE_PP = 0.10
SPOTCHECK_THRESHOLD = 27
ENSEMBLE_DISAGREE_FRACTION = 0.05


def check_trialscout(trials: pd.DataFrame) -> tuple[bool, float]:
    """Gate: cross-registered publication rate within ±10pp of TrialScout 63.6%.

    Returns (ok, rate). rate is NaN when no cross-registered trials exist,
    in which case ok is False (cannot evaluate → conservative fail).
    """
    cross = trials[
        trials["nct_secondary"].notna() & (trials["nct_secondary"] != "")
    ]
    if cross.empty:
        return False, float("nan")
    rate = float(cross["gate2_published"].mean())
    ok = abs(rate - TRIALSCOUT_BASELINE) <= TRIALSCOUT_TOLERANCE_PP
    return ok, rate


def check_spotcheck(spotcheck_csv: Path) -> tuple[bool, int, int]:
    """Gate: >=27/30 project-lead spot-check records agree with algorithm.

    Returns (ok, n_agree, n_total). n_total must be exactly 30.
    """
    df = pd.read_csv(spotcheck_csv)
    n = len(df)
    agree = int((df["auditor_verdict"] == df["algorithm_verdict"]).sum())
    ok = n == 30 and agree >= SPOTCHECK_THRESHOLD
    return ok, agree, n


def check_ensemble_disagreement(trials: pd.DataFrame) -> tuple[bool, float]:
    """Gate: ensemble disagreement fraction < 5% among gate3_in_cochrane trials.

    Vacuously passes when no trials reached Cochrane (in_cochrane == 0).
    Returns (ok, frac).
    """
    in_cochrane = int(trials["gate3_in_cochrane"].sum())
    if in_cochrane == 0:
        return True, 0.0
    disagree = int(trials["gate3_ensemble_disagree"].sum())
    frac = disagree / in_cochrane
    ok = frac < ENSEMBLE_DISAGREE_FRACTION
    return ok, float(frac)


def main() -> int:
    trials_path = Path("data/processed/trials.parquet")
    spotcheck_path = Path("data/processed/spotcheck_v0.1.0.csv")

    if not trials_path.exists():
        print(f"ERROR: {trials_path} not found — run the pipeline first.", file=sys.stderr)
        return 2
    if not spotcheck_path.exists():
        print(
            f"ERROR: {spotcheck_path} not found — complete the 30-trial spot-check first.",
            file=sys.stderr,
        )
        return 2

    trials = pd.read_parquet(trials_path)

    ok1, rate = check_trialscout(trials)
    ok2, agree, n = check_spotcheck(spotcheck_path)
    ok3, dfrac = check_ensemble_disagreement(trials)

    rate_str = f"{rate:.3f}" if not math.isnan(rate) else "nan"
    print(f"TrialScout sanity:        {'OK  ' if ok1 else 'FAIL'}  rate={rate_str}  (baseline={TRIALSCOUT_BASELINE:.3f} ±{TRIALSCOUT_TOLERANCE_PP:.2f})")
    print(f"30-trial spot-check:      {'OK  ' if ok2 else 'FAIL'}  {agree}/{n}  (threshold>={SPOTCHECK_THRESHOLD}/30)")
    print(f"Ensemble disagreement:    {'OK  ' if ok3 else 'FAIL'}  frac={dfrac:.3f}  (threshold<{ENSEMBLE_DISAGREE_FRACTION:.2f})")

    all_ok = ok1 and ok2 and ok3
    if all_ok:
        print("\nAll validation gates PASSED — safe to proceed to v0.1.0 release.")
    else:
        print("\nOne or more gates FAILED — do not release until resolved.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
