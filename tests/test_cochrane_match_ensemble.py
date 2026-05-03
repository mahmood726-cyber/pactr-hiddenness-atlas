import sqlite3
import pandas as pd

from pactr_atlas.cochrane_match import match_trial


def test_ensemble_nct_hit_only(fixture_path):
    pw = pd.read_parquet(fixture_path / "pairwise70_micro.parquet")
    db = sqlite3.connect(fixture_path / "cdsr_string_micro.sqlite")
    v = match_trial(
        nct="NCT04120000", pactr_id="PACTR2026X", pairwise70_index=pw, cdsr_conn=db,
    )
    db.close()
    assert v.in_cochrane is True
    assert v.method == "nct_bridge"
    assert v.ensemble_disagree is False


def test_ensemble_literal_hit_only(fixture_path):
    pw = pd.read_parquet(fixture_path / "pairwise70_micro.parquet")
    db = sqlite3.connect(fixture_path / "cdsr_string_micro.sqlite")
    v = match_trial(
        nct=None, pactr_id="PACTR202012000000001", pairwise70_index=pw, cdsr_conn=db,
    )
    db.close()
    assert v.in_cochrane is True
    assert v.method == "pactr_id_literal"
    assert v.ensemble_disagree is False


def test_ensemble_both_hit_no_disagreement(fixture_path):
    pw = pd.read_parquet(fixture_path / "pairwise70_micro.parquet")
    db = sqlite3.connect(fixture_path / "cdsr_string_micro.sqlite")
    v = match_trial(
        nct="NCT04120000", pactr_id="PACTR202012000000001",
        pairwise70_index=pw, cdsr_conn=db,
    )
    db.close()
    assert v.in_cochrane is True
    assert v.method == "nct_bridge"
    assert v.ensemble_disagree is False


def test_ensemble_disagree_when_only_literal_hits_with_nct_present(fixture_path):
    """NCT exists but doesn't match Pairwise70; literal does match CDSR.
    Primary verdict still nct_bridge=False, but ensemble_disagree=True."""
    pw = pd.read_parquet(fixture_path / "pairwise70_micro.parquet")
    db = sqlite3.connect(fixture_path / "cdsr_string_micro.sqlite")
    v = match_trial(
        nct="NCT09999999", pactr_id="PACTR202012000000001",
        pairwise70_index=pw, cdsr_conn=db,
    )
    db.close()
    assert v.in_cochrane is False
    assert v.method == "nct_bridge"
    assert v.ensemble_disagree is True


def test_ensemble_neither_hits(fixture_path):
    pw = pd.read_parquet(fixture_path / "pairwise70_micro.parquet")
    db = sqlite3.connect(fixture_path / "cdsr_string_micro.sqlite")
    v = match_trial(
        nct="NCT09999999", pactr_id="PACTR202099999999999",
        pairwise70_index=pw, cdsr_conn=db,
    )
    db.close()
    assert v.in_cochrane is False
    assert v.method == "none"
    assert v.ensemble_disagree is False
