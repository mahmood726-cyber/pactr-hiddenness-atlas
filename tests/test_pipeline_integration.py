"""End-to-end integration test on the 50-trial fixture.

Europe PMC is monkeypatched out — the pipeline runs offline and
deterministically. Verifies the orchestrator wires every gate module
together and produces a 10-row atlas.csv with the expected columns.
"""
from __future__ import annotations

import pandas as pd
import pytest

from pactr_atlas.config import Paths
from pilots.run_all import run_pipeline


@pytest.fixture
def fake_paths(tmp_path, fixture_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    return Paths(
        ictrp_snapshot=fixture_path / "ictrp_50trial.csv",
        pairwise70_index=fixture_path / "pairwise70_micro.parquet",
        cdsr_string_index=fixture_path / "cdsr_string_micro.sqlite",
        europe_pmc_cache_dir=cache,
    )


@pytest.mark.integration
def test_run_pipeline_produces_atlas_csv(fake_paths, tmp_path, monkeypatch):
    # Stub Europe PMC: no calls go to the network.
    from pactr_atlas import publication_match

    def _fake(nct, cache_dir):
        return publication_match.Gate2Verdict(published=False, pmid=None)

    monkeypatch.setattr(publication_match, "lookup_publication", _fake)

    out = tmp_path / "out"
    run_pipeline(fake_paths, out_dir=out, n_bootstrap=50)
    atlas = pd.read_csv(out / "atlas.csv")
    assert len(atlas) == 10  # all 10 conditions present
    assert set(atlas.columns) >= {
        "condition", "n_registered", "n_gate1", "n_gate2", "n_gate3",
        "pct_gate0_to_gate3", "n_tier0_invisible",
    }
    # 50-trial fixture has 5 trials per condition, each registered
    assert (atlas["n_registered"] == 5).all()
