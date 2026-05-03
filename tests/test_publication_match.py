import json
from pathlib import Path
from unittest.mock import patch

import pytest

from pactr_atlas.publication_match import (
    lookup_publication,
    Gate2Verdict,
    LookupFailed,
)


@pytest.fixture
def cache_dir(tmp_path):
    d = tmp_path / "epmc_cache"
    d.mkdir()
    return d


def _stub_response(payload: dict):
    class R:
        def __init__(self, p): self._p = p
        def read(self): return json.dumps(self._p).encode("utf-8")
        def __enter__(self): return self
        def __exit__(self, *a): pass
    return R(payload)


def test_lookup_publication_hit_caches_result(cache_dir):
    body = {"resultList": {"result": [
        {"pmid": "30000001", "doi": "10.1/test", "title": "x"},
    ]}}
    with patch("urllib.request.urlopen", return_value=_stub_response(body)):
        v = lookup_publication("NCT04123456", cache_dir)
    assert isinstance(v, Gate2Verdict)
    assert v.published is True
    assert v.pmid == "30000001"
    cache_file = cache_dir / "NCT04123456.json"
    assert cache_file.exists()


def test_lookup_publication_no_hit(cache_dir):
    body = {"resultList": {"result": []}}
    with patch("urllib.request.urlopen", return_value=_stub_response(body)):
        v = lookup_publication("NCT04999999", cache_dir)
    assert v.published is False
    assert v.pmid is None


def test_lookup_publication_uses_cache_on_second_call(cache_dir):
    body = {"resultList": {"result": [{"pmid": "30000002"}]}}
    with patch("urllib.request.urlopen", return_value=_stub_response(body)) as m:
        lookup_publication("NCT04123457", cache_dir)
        lookup_publication("NCT04123457", cache_dir)
    assert m.call_count == 1


def test_lookup_publication_ambiguous_picks_lowest_pmid(cache_dir):
    body = {"resultList": {"result": [
        {"pmid": "30000099"}, {"pmid": "30000010"}, {"pmid": "30000050"},
    ]}}
    with patch("urllib.request.urlopen", return_value=_stub_response(body)):
        v = lookup_publication("NCT04123458", cache_dir)
    assert v.published is True
    assert v.pmid == "30000010"
    assert v.ambiguous is True
