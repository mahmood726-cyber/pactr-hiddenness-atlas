"""PACTR-ID-direct EuropePMC search for PACTR Hiddenness Atlas v0.2.

CLI:
    python scripts/pactr_id_direct_search.py [--sample <path>] [--output <path>]

Defaults:
    --sample  data/processed/spotcheck_v0.1.0.csv
    --output  data/v0.2/pactr_id_direct_results.json

Pre-flight: data/processed/spotcheck_v0.1.0.csv.ots must exist (OTS anchor on sample).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EPMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
THROTTLE_SECONDS = 0.34   # ≤3 req/sec
MAX_RETRIES = 3
TIMEOUT = 30

# Match any PACTR ID (10+ digits after PACTR, case-insensitive)
PACTR_RE = re.compile(r"PACTR\d{10,}", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_SAMPLE = REPO_ROOT / "data" / "processed" / "spotcheck_v0.1.0.csv"
DEFAULT_SAMPLE_OTS = REPO_ROOT / "data" / "processed" / "spotcheck_v0.1.0.csv.ots"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "v0.2" / "pactr_id_direct_results.json"
DEFAULT_CACHE_DIR = REPO_ROOT / "data" / "v0.2" / ".cache"

# ---------------------------------------------------------------------------
# HTTP + cache
# ---------------------------------------------------------------------------


def _epmc_url(pactr_id: str) -> str:
    from urllib.parse import urlencode
    params = {
        "query": pactr_id,
        "format": "json",
        "pageSize": "25",
        "resultType": "core",
    }
    return f"{EPMC_BASE}?{urlencode(params)}"


def _cache_path(cache_dir: Path, pactr_id: str) -> Path:
    # Sanitise PACTR ID for filename (it's alphanumeric so safe, but be defensive)
    safe_id = re.sub(r"[^\w]", "_", pactr_id)
    return cache_dir / f"{safe_id}.json"


def _read_cache(cache_dir: Path, pactr_id: str) -> Optional[dict]:
    p = _cache_path(cache_dir, pactr_id)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def _write_cache(cache_dir: Path, pactr_id: str, body: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    _cache_path(cache_dir, pactr_id).write_text(json.dumps(body), encoding="utf-8")


def _http_get(url: str, *, retries: int = MAX_RETRIES, timeout: int = TIMEOUT) -> dict:
    delay = 1.0
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                wait = min(delay, 30.0)
                print(f"  [retry {attempt+1}/{retries-1}] {exc} — waiting {wait:.0f}s",
                      file=sys.stderr)
                time.sleep(wait)
                delay *= 2
    raise RuntimeError(
        f"EuropePMC unreachable after {retries} attempts for URL {url}: {last_exc}"
    )


def _fetch_epmc(pactr_id: str, cache_dir: Path) -> dict:
    """Fetch EuropePMC results for a PACTR ID, using cache if available."""
    cached = _read_cache(cache_dir, pactr_id)
    if cached is not None:
        return cached
    body = _http_get(_epmc_url(pactr_id))
    _write_cache(cache_dir, pactr_id, body)
    return body


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------


def _classify_response(pactr_id: str, body: dict) -> dict:
    """
    Given an EuropePMC response body, classify as hit or no_hit.

    Match rule (§4 of v0.2 spec):
    - At least one article in resultList.result
    - At least one article has a non-empty pmid
    - That article's title OR abstractText contains the queried PACTR ID
      (case-insensitive substring match; PACTR_RE used for flexibility)
    """
    results = (body.get("resultList") or {}).get("result") or []
    n_results = len(results)
    hit_pmids: list[str] = []

    for article in results:
        pmid = str(article.get("pmid") or "").strip()
        if not pmid:
            continue
        title = str(article.get("title") or "")
        abstract = str(article.get("abstractText") or "")
        combined = (title + " " + abstract).lower()
        # Check if any PACTR-like ID in text matches the queried PACTR ID
        # We match flexibly: the queried PACTR ID (lowercased) must appear as substring
        if pactr_id.lower() in combined:
            hit_pmids.append(pmid)

    classification = "hit" if hit_pmids else "no_hit"
    return {
        "n_results": n_results,
        "hit_pmids": hit_pmids,
        "classification": classification,
    }


def query_and_classify(pactr_id: str, cache_dir: Path) -> dict:
    """Query EuropePMC for a PACTR ID and classify the result.

    Returns a dict with: classification, hit_pmids, n_results, cache_used.
    """
    cached_before = _read_cache(cache_dir, pactr_id)
    body = _fetch_epmc(pactr_id, cache_dir)
    result = _classify_response(pactr_id, body)
    result["cache_used"] = cached_before is not None
    result["trial_id"] = pactr_id
    return result


def classify_trials(
    trials: list[dict],
    cache_dir: Path,
    *,
    throttle: float = THROTTLE_SECONDS,
) -> list[dict]:
    """Classify a list of trials. Each trial dict must have 'trial_id' key."""
    results = []
    for i, trial in enumerate(trials):
        pactr_id = trial["trial_id"]
        print(f"  [{i+1}/{len(trials)}] {pactr_id} ...", end=" ", flush=True)
        result = query_and_classify(pactr_id, cache_dir)
        result["trial_id"] = pactr_id
        # Carry through any extra columns from the sample
        for k, v in trial.items():
            if k not in result:
                result[k] = v
        print(result["classification"], flush=True)
        results.append(result)
        # Throttle only on real HTTP (not cached)
        if not result.get("cache_used", False):
            time.sleep(throttle)
    return results


# ---------------------------------------------------------------------------
# Sample loading
# ---------------------------------------------------------------------------


def load_sample(sample_path: Path) -> list[dict]:
    """Load the 30-trial sample from CSV. Returns list of dicts."""
    import csv
    trials = []
    with sample_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trials.append(dict(row))
    return trials


# ---------------------------------------------------------------------------
# Pre-flight check
# ---------------------------------------------------------------------------


def preflight(sample_path: Path) -> None:
    """Hard-fail if sample OTS anchor is missing (protects pre-registration integrity)."""
    ots_path = Path(str(sample_path) + ".ots")
    if not sample_path.exists():
        raise FileNotFoundError(
            f"Sample file not found: {sample_path}\n"
            "Cannot proceed — the OTS-anchored sample must exist."
        )
    if not ots_path.exists():
        raise FileNotFoundError(
            f"OTS anchor missing for sample: {ots_path}\n"
            "Cannot proceed — pre-registration integrity check failed.\n"
            "If this is a fresh clone, ensure the .ots file is committed."
        )


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="PACTR Hiddenness Atlas v0.2: PACTR-ID-direct EuropePMC search"
    )
    parser.add_argument(
        "--sample",
        default=str(DEFAULT_SAMPLE),
        help=f"Path to sample CSV (default: {DEFAULT_SAMPLE})",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Path to output JSON (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--cache-dir",
        default=str(DEFAULT_CACHE_DIR),
        help=f"Cache directory for EuropePMC responses (default: {DEFAULT_CACHE_DIR})",
    )
    args = parser.parse_args(argv)

    sample_path = Path(args.sample)
    output_path = Path(args.output)
    cache_dir = Path(args.cache_dir)

    # Pre-flight
    print(f"[preflight] checking sample anchor: {sample_path}.ots", flush=True)
    preflight(sample_path)
    print("[preflight] OK", flush=True)

    # Load sample
    trials = load_sample(sample_path)
    print(f"[search] loaded {len(trials)} trials from {sample_path}", flush=True)

    cache_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Run search
    print("[search] querying EuropePMC (<=3 req/sec)...", flush=True)
    trial_results = classify_trials(trials, cache_dir)

    # Summary
    hits = sum(1 for r in trial_results if r["classification"] == "hit")
    no_hits = sum(1 for r in trial_results if r["classification"] == "no_hit")
    print(f"[search] done — hits: {hits}, no_hit: {no_hits}, total: {len(trial_results)}", flush=True)

    # Build output
    output = {
        "spec_version": "v0.2",
        "ran_at": datetime.now(tz=timezone.utc).isoformat(),
        "sample_path": str(sample_path),
        "n_trials": len(trial_results),
        "summary": {"hit": hits, "no_hit": no_hits},
        "trials": trial_results,
    }

    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"[output] written to {output_path}", flush=True)


if __name__ == "__main__":
    main()
