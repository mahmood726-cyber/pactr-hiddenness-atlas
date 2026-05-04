"""Unit tests for scripts/validation_gates.py.

Three gate functions; each tested for pass, fail, and an edge case.
No live data required — all fixtures are synthetic DataFrames / tmp_path CSVs.
"""
import math

import pandas as pd
import pytest

from scripts.validation_gates import (
    ENSEMBLE_DISAGREE_FRACTION,
    SPOTCHECK_THRESHOLD,
    TRIALSCOUT_BASELINE,
    check_ensemble_disagreement,
    check_spotcheck,
    check_trialscout,
)


# ---------------------------------------------------------------------------
# check_trialscout
# ---------------------------------------------------------------------------


def test_check_trialscout_within_tolerance_passes():
    """10 cross-registered trials, 7 published → rate=0.7, within 0.636 ± 0.10."""
    trials = pd.DataFrame(
        {
            "nct_secondary": [f"NCT{i:08d}" for i in range(10)],
            "gate2_published": [True] * 7 + [False] * 3,
        }
    )
    ok, rate = check_trialscout(trials)
    assert ok is True
    assert abs(rate - 0.7) < 1e-9


def test_check_trialscout_outside_tolerance_fails():
    """10 cross-registered trials, all unpublished → rate=0.0, outside ±0.10 of 0.636."""
    trials = pd.DataFrame(
        {
            "nct_secondary": [f"NCT{i:08d}" for i in range(10)],
            "gate2_published": [False] * 10,
        }
    )
    ok, rate = check_trialscout(trials)
    assert ok is False
    assert rate == 0.0


def test_check_trialscout_no_cross_registered_returns_nan():
    """Edge case: no NCT secondaries at all → cannot evaluate; conservative fail."""
    trials = pd.DataFrame(
        {
            "nct_secondary": [None, None, ""],
            "gate2_published": [True, False, True],
        }
    )
    ok, rate = check_trialscout(trials)
    assert ok is False
    assert math.isnan(rate)


# ---------------------------------------------------------------------------
# check_spotcheck
# ---------------------------------------------------------------------------


def test_check_spotcheck_27_of_30_passes(tmp_path):
    """27 matching verdicts out of 30 meets the >=27 threshold exactly."""
    csv = tmp_path / "spot.csv"
    rows = [{"algorithm_verdict": "TFT", "auditor_verdict": "TFT"}] * 27 + [
        {"algorithm_verdict": "TFT", "auditor_verdict": "FFT"}
    ] * 3
    pd.DataFrame(rows).to_csv(csv, index=False)
    ok, agree, n = check_spotcheck(csv)
    assert ok is True
    assert agree == 27
    assert n == 30


def test_check_spotcheck_26_of_30_fails(tmp_path):
    """26/30 is below the 27-trial threshold."""
    csv = tmp_path / "spot.csv"
    rows = [{"algorithm_verdict": "TFT", "auditor_verdict": "TFT"}] * 26 + [
        {"algorithm_verdict": "TFT", "auditor_verdict": "FFT"}
    ] * 4
    pd.DataFrame(rows).to_csv(csv, index=False)
    ok, agree, n = check_spotcheck(csv)
    assert ok is False
    assert agree == 26


def test_check_spotcheck_wrong_n_fails(tmp_path):
    """29 rows must fail even if all verdicts match — n must equal exactly 30."""
    csv = tmp_path / "spot.csv"
    rows = [{"algorithm_verdict": "TFT", "auditor_verdict": "TFT"}] * 29
    pd.DataFrame(rows).to_csv(csv, index=False)
    ok, agree, n = check_spotcheck(csv)
    assert ok is False
    assert n == 29


# ---------------------------------------------------------------------------
# check_ensemble_disagreement
# ---------------------------------------------------------------------------


def test_check_ensemble_disagreement_under_threshold_passes():
    """100 in Cochrane, 4 disagree → 4% < 5% threshold."""
    trials = pd.DataFrame(
        {
            "gate3_in_cochrane": [True] * 100,
            "gate3_ensemble_disagree": [True] * 4 + [False] * 96,
        }
    )
    ok, frac = check_ensemble_disagreement(trials)
    assert ok is True
    assert abs(frac - 0.04) < 1e-9


def test_check_ensemble_disagreement_at_threshold_fails():
    """100 in Cochrane, 5 disagree → 5% is NOT < 5% (strict inequality)."""
    trials = pd.DataFrame(
        {
            "gate3_in_cochrane": [True] * 100,
            "gate3_ensemble_disagree": [True] * 5 + [False] * 95,
        }
    )
    ok, frac = check_ensemble_disagreement(trials)
    assert ok is False
    assert abs(frac - 0.05) < 1e-9


def test_check_ensemble_disagreement_zero_in_cochrane_passes():
    """Edge case: nothing reached Cochrane → vacuously passes with frac=0.0."""
    trials = pd.DataFrame(
        {
            "gate3_in_cochrane": [False, False, False],
            "gate3_ensemble_disagree": [False, False, False],
        }
    )
    ok, frac = check_ensemble_disagreement(trials)
    assert ok is True
    assert frac == 0.0
