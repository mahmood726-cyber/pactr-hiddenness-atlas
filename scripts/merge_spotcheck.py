"""Merge blinded auditor verdicts with algorithm verdicts → final spotcheck CSV
that validation_gates.py reads.

Inputs:
  - data/processed/spotcheck_v0.1.0_auditor.csv (blinded auditor output;
    columns: trial_id, nct_secondary, condition, auditor_gate1/2/3,
    auditor_verdict, notes)
  - data/processed/trials.parquet (algorithm output; sample is regenerated
    here via the same seed=20260503 to guarantee row alignment)

Output:
  - data/processed/spotcheck_v0.1.0.csv (12-col format validation_gates expects:
    trial_id, nct_secondary, condition,
    algorithm_gate1/2/3, auditor_gate1/2/3,
    algorithm_verdict, auditor_verdict, notes)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

DEFAULT_AUDITOR = Path("data/processed/spotcheck_v0.1.0_auditor.csv")
DEFAULT_TRIALS = Path("data/processed/trials.parquet")
DEFAULT_OUT = Path("data/processed/spotcheck_v0.1.0.csv")
DEFAULT_SEED = 20260503
DEFAULT_N = 30


def _verdict(g1: bool, g2: bool, g3: bool) -> str:
    return ("T" if g1 else "F") + ("T" if g2 else "F") + ("T" if g3 else "F")


def merge(auditor_path: Path, trials_path: Path, out_path: Path,
          *, seed: int, n: int) -> int:
    auditor = pd.read_csv(auditor_path, dtype=str)
    trials = pd.read_parquet(trials_path)
    sample = trials.sample(n=n, random_state=seed).reset_index(drop=True)
    algo = pd.DataFrame({
        "trial_id": sample["TrialID"],
        "algorithm_gate1": sample["gate1_results_posted"].astype(bool),
        "algorithm_gate2": sample["gate2_published"].astype(bool),
        "algorithm_gate3": sample["gate3_in_cochrane"].astype(bool),
    })
    algo["algorithm_verdict"] = [
        _verdict(g1, g2, g3) for g1, g2, g3 in
        zip(algo["algorithm_gate1"], algo["algorithm_gate2"], algo["algorithm_gate3"])
    ]
    merged = auditor.merge(algo, on="trial_id", how="inner")
    if len(merged) != n:
        raise ValueError(
            f"merge produced {len(merged)} rows; expected {n}. "
            f"Auditor and algorithm sample disagree on trial_id set."
        )
    out_cols = [
        "trial_id", "nct_secondary", "condition",
        "algorithm_gate1", "algorithm_gate2", "algorithm_gate3",
        "auditor_gate1", "auditor_gate2", "auditor_gate3",
        "algorithm_verdict", "auditor_verdict", "notes",
    ]
    merged[out_cols].to_csv(out_path, index=False)
    return len(merged)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--auditor", default=DEFAULT_AUDITOR, type=Path)
    p.add_argument("--trials", default=DEFAULT_TRIALS, type=Path)
    p.add_argument("--out", default=DEFAULT_OUT, type=Path)
    p.add_argument("--seed", default=DEFAULT_SEED, type=int)
    p.add_argument("--n", default=DEFAULT_N, type=int)
    args = p.parse_args()
    n = merge(args.auditor, args.trials, args.out, seed=args.seed, n=args.n)
    print(f"merged {n} rows to {args.out}")
    df = pd.read_csv(args.out)
    agree = (df["algorithm_verdict"] == df["auditor_verdict"]).sum()
    print(f"agreement: {agree}/{n} ({100*agree/n:.0f}%) — threshold for v0.1.0 release: >=27/30 (90%)")


if __name__ == "__main__":
    raise SystemExit(main())
