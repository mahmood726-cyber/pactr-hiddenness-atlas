"""Generate the 30-trial spot-check template CSV (Task 22 Step 4).

Random sample (seed=20260503) of 30 trials from the live trials.parquet,
pre-filled with algorithm verdicts. The user manually verifies each gate
against ICTRP / Europe PMC / CDSR and fills the auditor_* columns.

Output template at data/processed/spotcheck_v0.1.0_template.csv. After
the human fill, save as data/processed/spotcheck_v0.1.0.csv (the path
validation_gates.py expects).

Per spec Task 21 §3: agreement threshold ≥27/30. Verdict format is a
3-char string of T/F per gate, e.g. 'TFT' = gate1 yes, gate2 no, gate3 yes.

Usage:
    python scripts/make_spotcheck_template.py [--out PATH] [--n 30] [--seed 20260503]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

DEFAULT_TRIALS = Path("data/processed/trials.parquet")
DEFAULT_OUT = Path("data/processed/spotcheck_v0.1.0_template.csv")
DEFAULT_N = 30
DEFAULT_SEED = 20260503


def _verdict(g1: bool, g2: bool, g3: bool) -> str:
    return ("T" if g1 else "F") + ("T" if g2 else "F") + ("T" if g3 else "F")


def make_template(trials_path: Path, out_path: Path, *, n: int, seed: int) -> int:
    df = pd.read_parquet(trials_path)
    if len(df) < n:
        raise ValueError(f"trials.parquet has only {len(df)} rows; need >= {n}")
    sample = df.sample(n=n, random_state=seed).reset_index(drop=True)
    cols = {
        "trial_id": sample["TrialID"],
        "nct_secondary": sample["nct_secondary"].fillna(""),
        "condition": sample["condition"],
        "algorithm_gate1": sample["gate1_results_posted"],
        "algorithm_gate2": sample["gate2_published"],
        "algorithm_gate3": sample["gate3_in_cochrane"],
        "auditor_gate1": "",
        "auditor_gate2": "",
        "auditor_gate3": "",
        "algorithm_verdict": [
            _verdict(g1, g2, g3) for g1, g2, g3 in zip(
                sample["gate1_results_posted"],
                sample["gate2_published"],
                sample["gate3_in_cochrane"],
            )
        ],
        "auditor_verdict": "",
        "notes": "",
    }
    out_df = pd.DataFrame(cols)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)
    return len(out_df)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trials", default=DEFAULT_TRIALS, type=Path)
    p.add_argument("--out", default=DEFAULT_OUT, type=Path)
    p.add_argument("--n", default=DEFAULT_N, type=int)
    p.add_argument("--seed", default=DEFAULT_SEED, type=int)
    args = p.parse_args()
    n = make_template(args.trials, args.out, n=args.n, seed=args.seed)
    print(f"wrote {n}-row spot-check template to {args.out}")
    print()
    print("NEXT STEPS (manual):")
    print(f"  1. Open {args.out} in your editor/spreadsheet.")
    print("  2. For each row, verify each gate against the source:")
    print("     - gate1: ICTRP/PACTR Results URL — does it actually link to results?")
    print("     - gate2: Europe PMC — search for the NCT; is there a real publication?")
    print("     - gate3: CDSR — does any Cochrane MA cite this trial?")
    print("  3. Fill auditor_gate1/2/3 (True/False) and auditor_verdict (3-char string).")
    print("  4. Save as data/processed/spotcheck_v0.1.0.csv (DROP the _template suffix).")
    print("  5. Run: python scripts/validation_gates.py")
    print("  6. Threshold: >=27/30 algorithm-vs-auditor agreement.")


if __name__ == "__main__":
    raise SystemExit(main())
