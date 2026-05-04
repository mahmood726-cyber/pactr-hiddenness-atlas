"""Gate 2: peer-reviewed publication via Europe PMC.

Cache strategy: per-NCT JSON cache. Second call short-circuits before
the HTTP request. Ambiguous results (>=2 PMIDs for one NCT) record
ambiguous=True and pick the lowest PMID for the primary verdict; a
sensitivity sweep in v0.1.0 reruns with --reject-ambiguous.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class LookupFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class Gate2Verdict:
    published: bool
    pmid: Optional[str]
    ambiguous: bool = False
    lookup_failed: bool = False


_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _query_url(nct: str) -> str:
    # Europe PMC: find publications citing the NCT via free-text search,
    # filtered to peer-reviewed sources only.
    # SRC:MED = MEDLINE; SRC:PMC = PubMed Central full text.
    # NOTE: EXT_ID field and clinicaltrials_gov field both return 0 hits for
    # NCT IDs — even for known-published trials (e.g. PARADIGM-HF NCT01035255).
    # Free-text NCT search is the reliable approach confirmed against 29 PACTR NCTs.
    q = f'{nct} AND (SRC:MED OR SRC:PMC)'
    return f"{_BASE}?{urllib.parse.urlencode({'query': q, 'format': 'json'})}"


def _read_cache(cache_dir: Path, nct: str) -> Optional[dict]:
    p = cache_dir / f"{nct}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def _write_cache(cache_dir: Path, nct: str, body: dict) -> None:
    (cache_dir / f"{nct}.json").write_text(json.dumps(body), encoding="utf-8")


def _http_get(url: str, *, retries: int = 5, timeout: int = 30) -> dict:
    delay = 1.0
    last: Optional[Exception] = None
    for _ in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            last = exc
            time.sleep(min(delay, 30.0))
            delay *= 2
    raise LookupFailed(f"GET {url}: {last}")


def lookup_publication(nct: str, cache_dir: Path) -> Gate2Verdict:
    cached = _read_cache(cache_dir, nct)
    if cached is None:
        try:
            cached = _http_get(_query_url(nct))
            _write_cache(cache_dir, nct, cached)
        except LookupFailed:
            return Gate2Verdict(published=False, pmid=None, lookup_failed=True)
    results = (cached.get("resultList") or {}).get("result") or []
    pmids = [str(r["pmid"]) for r in results if r.get("pmid")]
    if not pmids:
        return Gate2Verdict(published=False, pmid=None)
    pmids.sort(key=lambda x: int(x))
    return Gate2Verdict(
        published=True, pmid=pmids[0], ambiguous=(len(pmids) > 1),
    )
