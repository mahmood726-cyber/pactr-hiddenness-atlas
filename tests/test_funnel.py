import pandas as pd
import pytest

from pactr_atlas.funnel import (
    compute_funnel,
    clustered_bootstrap_ci,
    EmptyFunnelInput,
)


def _trials_df(rows):
    return pd.DataFrame(rows, columns=[
        "trial_id", "condition", "country_lead",
        "gate0_registered", "gate1_results_posted",
        "gate2_published", "gate3_in_cochrane", "tier0_invisible",
    ])


def test_compute_funnel_minimal():
    df = _trials_df([
        ("T1","tuberculosis","UGA",True,True,True,True,False),
        ("T2","tuberculosis","KEN",True,False,True,False,True),
        ("T3","hiv","ZAF",True,True,False,False,False),
    ])
    out = compute_funnel(df, n_bootstrap=50)
    assert set(out["condition"]) == {"tuberculosis", "hiv"}
    tb = out[out["condition"] == "tuberculosis"].iloc[0]
    assert tb["n_registered"] == 2
    assert tb["n_gate1"] == 1
    assert tb["n_gate2"] == 2
    assert tb["n_gate3"] == 1
    assert tb["n_tier0_invisible"] == 1
    assert tb["pct_gate0_to_gate3"] == pytest.approx(0.5)


def test_compute_funnel_empty_raises():
    df = _trials_df([])
    with pytest.raises(EmptyFunnelInput):
        compute_funnel(df)


def test_clustered_bootstrap_ci_within_bounds():
    # Test 3 (fixed): plan markdown originally had only 2 country clusters
    # (UGA + KEN) which would trigger the < 3 early-return branch and
    # return (None, None), making the `0.0 <= lo <= hi <= 1.0` assertion
    # fail. Adding a third cluster (ZAF) makes the bootstrap actually run.
    df = _trials_df([
        ("T1","tuberculosis","UGA",True,True,True,True,False),
        ("T2","tuberculosis","UGA",True,True,True,True,False),
        ("T3","tuberculosis","KEN",True,True,True,False,False),
        ("T4","tuberculosis","KEN",True,True,True,False,False),
        ("T5","tuberculosis","ZAF",True,True,True,False,False),
        ("T6","tuberculosis","ZAF",True,True,True,False,False),
    ])
    lo, hi = clustered_bootstrap_ci(df, "gate3_in_cochrane", "country_lead", n=200, seed=42)
    assert 0.0 <= lo <= hi <= 1.0


def test_clustered_bootstrap_ci_undefined_for_k_lt_3():
    df = _trials_df([
        ("T1","tuberculosis","UGA",True,True,True,True,False),
        ("T2","tuberculosis","KEN",True,True,True,True,False),
    ])
    lo, hi = clustered_bootstrap_ci(df, "gate3_in_cochrane", "country_lead", n=100, seed=42)
    assert lo is None and hi is None  # k=2 clusters → undefined
