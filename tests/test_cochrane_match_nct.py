import pandas as pd
import pytest

from pactr_atlas.cochrane_match import nct_bridge_match, MatchVerdict


def test_nct_bridge_match_hit(fixture_path):
    pw = pd.read_parquet(fixture_path / "pairwise70_micro.parquet")
    v = nct_bridge_match("NCT04120000", pw)
    assert isinstance(v, MatchVerdict)
    assert v.in_cochrane is True
    assert v.method == "nct_bridge"
    assert v.review_id == "CD000001"


def test_nct_bridge_match_miss(fixture_path):
    pw = pd.read_parquet(fixture_path / "pairwise70_micro.parquet")
    v = nct_bridge_match("NCT09999999", pw)
    assert v.in_cochrane is False
    assert v.method == "none"
    assert v.review_id is None


def test_nct_bridge_match_none_input(fixture_path):
    pw = pd.read_parquet(fixture_path / "pairwise70_micro.parquet")
    v = nct_bridge_match(None, pw)
    assert v.in_cochrane is False
    assert v.method == "none"


def test_nct_bridge_match_returns_first_review_when_multi(fixture_path):
    """A trial in 2 reviews should still report a single primary review_id;
    the additional reviews are surfaced via review_ids_all (sensitivity)."""
    pw = pd.DataFrame({
        "review_id": ["CD000001", "CD000007"], "nct": ["NCT04120000", "NCT04120000"],
    })
    v = nct_bridge_match("NCT04120000", pw)
    assert v.in_cochrane is True
    assert v.review_id in ("CD000001", "CD000007")
    assert set(v.review_ids_all or ()) == {"CD000001", "CD000007"}
