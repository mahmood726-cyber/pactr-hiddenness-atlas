from pathlib import Path
import pandas as pd
import pytest

from pilots.preflight import (
    PreflightFailed,
    check_paths_resolve,
    check_ictrp_filter_size,
    check_condition_denominators,
    run as run_preflight,
)
from pactr_atlas.config import Paths


def _make_minimal_paths(tmp_path) -> Paths:
    ictrp = tmp_path / "ictrp.csv"
    df = pd.DataFrame({
        "TrialID": [f"PACTR2026{i:09d}" for i in range(5500)],
        "Source Register": ["PACTR"] * 5500,
        "Conditions": ["Tuberculosis"] * 200 + ["HIV"] * 200 + ["Sickle cell"] * 200
                      + ["Schistosomiasis"] * 200 + ["maternal sepsis"] * 200
                      + ["neonatal sepsis"] * 200 + ["snakebite"] * 200
                      + ["soil-transmitted helminths"] * 200 + ["cervical cancer"] * 200
                      + ["cholera"] * 200 + ["other"] * 3500,
        "Secondary IDs": [""] * 5500,
        "Results URL": [""] * 5500,
    })
    df.to_csv(ictrp, index=False)
    pw = tmp_path / "pw.parquet"
    pd.DataFrame({"nct": ["NCT00000001"], "review_id": ["CD000001"]}).to_parquet(pw)
    cdsr = tmp_path / "cdsr.sqlite"
    cdsr.touch()
    return Paths(
        ictrp_snapshot=ictrp, pairwise70_index=pw,
        cdsr_string_index=cdsr, europe_pmc_cache_dir=tmp_path / "cache",
    )


def test_check_paths_resolve_passes(tmp_path):
    paths = _make_minimal_paths(tmp_path)
    paths.europe_pmc_cache_dir.mkdir(exist_ok=True)
    check_paths_resolve(paths)  # no raise


def test_check_ictrp_filter_size_below_min_raises(tmp_path):
    ictrp = tmp_path / "small.csv"
    pd.DataFrame({"TrialID": ["X"], "Source Register": ["PACTR"]}).to_csv(ictrp, index=False)
    with pytest.raises(PreflightFailed, match="filter returned"):
        check_ictrp_filter_size(ictrp, min_rows=5000)


def test_check_condition_denominators_below_min_raises(tmp_path):
    ictrp = tmp_path / "ictrp.csv"
    pd.DataFrame({
        "TrialID": ["A"] * 19,
        "Source Register": ["PACTR"] * 19,
        "Conditions": ["Tuberculosis"] * 19,
    }).to_csv(ictrp, index=False)
    with pytest.raises(PreflightFailed, match="below minimum 20"):
        check_condition_denominators(ictrp, min_per_condition=20)
