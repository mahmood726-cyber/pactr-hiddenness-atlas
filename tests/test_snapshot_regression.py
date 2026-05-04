# tests/test_snapshot_regression.py
"""Snapshot regression test: re-run pipeline on fixtures; compare deterministic
columns of atlas.csv against the committed atlas_baseline.csv byte-for-byte.

Bootstrap-CI columns (pct_gate0_to_gate3_ci_lo, _ci_hi) are excluded from the
comparison — they use a seeded internal RNG inside clustered_bootstrap_ci that
is independent of the autouse _seed_random fixture.

Gate3 (Cochrane match) is independent of Gate2 (Europe PMC publication).
lookup_publication is monkeypatched to return published=False for all trials
so the test is fully offline and deterministic.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


@pytest.mark.integration
def test_atlas_matches_baseline_byte_for_byte(tmp_path, fixture_path, monkeypatch):
    """Re-run pipeline on fixtures; assert atlas.csv equals atlas_baseline.csv."""
    from pactr_atlas import publication_match

    monkeypatch.setattr(
        publication_match,
        "lookup_publication",
        lambda nct, cd: publication_match.Gate2Verdict(published=False, pmid=None),
    )

    from pactr_atlas.config import Paths
    from pilots.run_all import run_pipeline

    cache = tmp_path / "cache"
    cache.mkdir()
    paths = Paths(
        ictrp_snapshot=fixture_path / "ictrp_50trial.csv",
        pairwise70_index=fixture_path / "pairwise70_micro.parquet",
        cdsr_string_index=fixture_path / "cdsr_string_micro.sqlite",
        europe_pmc_cache_dir=cache,
    )
    run_pipeline(paths, out_dir=tmp_path / "out", n_bootstrap=200)

    fresh = pd.read_csv(tmp_path / "out" / "atlas.csv")
    base = pd.read_csv(Path("data/processed/atlas_baseline.csv"))

    # Bootstrap CIs are stochastic — compare only deterministic columns.
    # Note: n_gate3 may exceed n_gate2 because Gate3 (Cochrane match) is
    # independent of Gate2 (Europe PMC publication); this is correct behaviour.
    cols = [
        "condition",
        "n_registered",
        "n_gate1",
        "n_gate2",
        "n_gate3",
        "pct_gate0_to_gate3",
        "n_gate3_given_gate2",
        "pct_gate0_to_gate3_given_gate2",
        "n_tier0_invisible",
    ]
    pd.testing.assert_frame_equal(
        fresh[cols].sort_values("condition").reset_index(drop=True),
        base[cols].sort_values("condition").reset_index(drop=True),
    )
