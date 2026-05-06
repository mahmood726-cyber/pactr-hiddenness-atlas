"""Tests for scripts/pactr_id_direct_search.py (PACTR-ID-direct EuropePMC search).

Uses unittest.mock to avoid real HTTP calls.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pactr_id_direct_search as pid  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers: fake EuropePMC response builders
# ---------------------------------------------------------------------------

def _epmc_response(results: list[dict]) -> MagicMock:
    """Return a mock whose .json() method returns a well-formed EuropePMC payload."""
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {
        "resultList": {
            "result": results
        },
        "hitCount": len(results),
    }
    return m


def _article(pmid: str, title: str = "", abstract: str = "") -> dict:
    return {"pmid": pmid, "title": title, "abstractText": abstract, "source": "MED"}


# ---------------------------------------------------------------------------
# Test 1: empty result list -> no_hit
# ---------------------------------------------------------------------------

def test_empty_results_no_hit(tmp_path):
    """Empty result list from EuropePMC -> no_hit."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    resp = _epmc_response([])
    with patch("pactr_id_direct_search.requests.get", return_value=resp):
        result = pid.query_and_classify("PACTR201510001314191", cache_dir)
    assert result["classification"] == "no_hit"
    assert result["hit_pmids"] == []


# ---------------------------------------------------------------------------
# Test 2: single result with PACTR ID in title -> hit
# ---------------------------------------------------------------------------

def test_single_result_pactr_in_title_hit(tmp_path):
    """Single article with PACTR ID in title -> hit."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    pactr_id = "PACTR201105000289276"
    resp = _epmc_response([
        _article("25490675", title=f"An RCT registered as {pactr_id}")
    ])
    with patch("pactr_id_direct_search.requests.get", return_value=resp):
        result = pid.query_and_classify(pactr_id, cache_dir)
    assert result["classification"] == "hit"
    assert "25490675" in result["hit_pmids"]


# ---------------------------------------------------------------------------
# Test 3: multiple results, only one with PACTR ID -> hit (counts that one)
# ---------------------------------------------------------------------------

def test_multiple_results_only_one_matches_hit(tmp_path):
    """Multiple results returned, only one contains PACTR ID -> hit."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    pactr_id = "PACTR201802003141213"
    resp = _epmc_response([
        _article("11111111", title="Unrelated paper"),
        _article("35767586", abstract=f"Trial registered at {pactr_id} in Africa."),
        _article("22222222", title="Another unrelated paper"),
    ])
    with patch("pactr_id_direct_search.requests.get", return_value=resp):
        result = pid.query_and_classify(pactr_id, cache_dir)
    assert result["classification"] == "hit"
    assert "35767586" in result["hit_pmids"]
    # Unrelated articles should NOT be in hit_pmids
    assert "11111111" not in result["hit_pmids"]


# ---------------------------------------------------------------------------
# Test 4: result without pmid -> no_hit (pmid required for a hit)
# ---------------------------------------------------------------------------

def test_result_without_pmid_no_hit(tmp_path):
    """Result present but pmid is empty/missing -> no_hit."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    pactr_id = "PACTR202105682809727"
    # Article has PACTR ID in abstract but no pmid
    resp = _epmc_response([
        {"pmid": "", "title": f"Study {pactr_id}", "abstractText": f"Registered {pactr_id}", "source": "PPR"},
    ])
    with patch("pactr_id_direct_search.requests.get", return_value=resp):
        result = pid.query_and_classify(pactr_id, cache_dir)
    assert result["classification"] == "no_hit"


# ---------------------------------------------------------------------------
# Test 5: cache hit returns same classification as fresh call (determinism)
# ---------------------------------------------------------------------------

def test_cache_hit_deterministic(tmp_path):
    """Second call with cached response returns same result without HTTP call."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    pactr_id = "PACTR201007000192283"
    resp = _epmc_response([
        _article("28456509", title=f"WOMAN trial {pactr_id} results")
    ])
    with patch("pactr_id_direct_search.requests.get", return_value=resp) as mock_get:
        result1 = pid.query_and_classify(pactr_id, cache_dir)
        result2 = pid.query_and_classify(pactr_id, cache_dir)
    # HTTP should only be called once (second call uses cache)
    assert mock_get.call_count == 1
    assert result1["classification"] == result2["classification"] == "hit"
    assert result1["hit_pmids"] == result2["hit_pmids"]


# ---------------------------------------------------------------------------
# Test 6: PACTR ID match is case-insensitive in title/abstract
# ---------------------------------------------------------------------------

def test_pactr_id_match_case_insensitive(tmp_path):
    """Match should work even if paper uses lowercase/mixed case PACTR ID."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    pactr_id = "PACTR201804003327269"
    # Paper uses lowercase variant of the PACTR ID
    resp = _epmc_response([
        _article("31533663", abstract=f"registered at pactr201804003327269 in Africa")
    ])
    with patch("pactr_id_direct_search.requests.get", return_value=resp):
        result = pid.query_and_classify(pactr_id, cache_dir)
    assert result["classification"] == "hit"


# ---------------------------------------------------------------------------
# Test 7: result with PACTR ID only in abstract (not title) -> hit
# ---------------------------------------------------------------------------

def test_pactr_id_in_abstract_only_hit(tmp_path):
    """PACTR ID in abstract (not in title) still counts as hit."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    pactr_id = "PACTR201810756862405"
    resp = _epmc_response([
        _article("34986170", title="Peer-led mental health cluster-RCT",
                 abstract=f"This study was pre-registered as {pactr_id}.")
    ])
    with patch("pactr_id_direct_search.requests.get", return_value=resp):
        result = pid.query_and_classify(pactr_id, cache_dir)
    assert result["classification"] == "hit"


# ---------------------------------------------------------------------------
# Test 8: classify_trials processes a list and returns one record per trial
# ---------------------------------------------------------------------------

def test_classify_trials_returns_one_record_per_trial(tmp_path):
    """classify_trials returns exactly one result dict per input trial."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    trials = [
        {"trial_id": "PACTR201007000192283"},
        {"trial_id": "PACTR201510001314191"},
    ]
    responses = {
        "PACTR201007000192283": _epmc_response([
            _article("28456509", title="WOMAN trial PACTR201007000192283")
        ]),
        "PACTR201510001314191": _epmc_response([]),
    }
    def fake_get(url, **kwargs):
        for pactr_id, resp in responses.items():
            if pactr_id in url:
                return resp
        return _epmc_response([])

    with patch("pactr_id_direct_search.requests.get", side_effect=fake_get):
        with patch("pactr_id_direct_search.time.sleep"):  # no real sleeping in tests
            results = pid.classify_trials(trials, cache_dir)
    assert len(results) == 2
    verdicts = {r["trial_id"]: r["classification"] for r in results}
    assert verdicts["PACTR201007000192283"] == "hit"
    assert verdicts["PACTR201510001314191"] == "no_hit"
