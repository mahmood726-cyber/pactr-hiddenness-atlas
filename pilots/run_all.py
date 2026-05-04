"""End-to-end orchestrator. Reads a frozen ICTRP snapshot, runs each
gate, writes atlas.csv to out_dir.

Linear, idempotent, no module reads back from out_dir.

Import discipline: ``publication_match`` is imported as a module (not
its functions directly) so that test-time monkeypatching of
``pactr_atlas.publication_match.lookup_publication`` flows through to
this orchestrator's call sites. All other gate modules are imported
function-by-function — they are not patched in the integration test.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
from pathlib import Path

import pandas as pd

from pactr_atlas import publication_match
from pactr_atlas.cochrane_match import match_trial
from pactr_atlas.condition_matcher import assign_all
from pactr_atlas.config import Paths
from pactr_atlas.funnel import compute_funnel
from pactr_atlas.ictrp_loader import load_pactr_snapshot
from pactr_atlas.nct_bridge import extract_nct, is_tier0_invisible
from pactr_atlas.results_posting import gate1_all

_DEFAULT_META_PATH = Path("data/snapshots/ictrp_metadata.json")


def _resolve_snapshot_date(paths: Paths, meta_path: Path | None) -> str:
    """Return the snapshot_date string for atlas.csv.

    Priority (Bug 4):
    1. Read from *meta_path* JSON if the file exists.
    2. Fall back to the stem of paths.ictrp_snapshot (e.g. ``ictrp_50trial``).
    """
    resolved = meta_path if meta_path is not None else _DEFAULT_META_PATH
    if resolved.exists():
        try:
            meta = json.loads(resolved.read_text(encoding="utf-8"))
            return str(meta["snapshot_date"])
        except (KeyError, json.JSONDecodeError):
            pass
    return paths.ictrp_snapshot.stem


def run_pipeline(
    paths: Paths,
    *,
    out_dir: Path,
    n_bootstrap: int = 1000,
    meta_path: Path | None = None,
) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pactr = load_pactr_snapshot(paths.ictrp_snapshot)
    matched, dropped = assign_all(pactr)
    if matched.empty:
        raise RuntimeError("condition_matcher produced zero rows; halt")

    matched = gate1_all(matched)
    # ICTRP CSV produces NaN floats for empty Secondary IDs; extract_nct's
    # contract is Optional[str], so coerce NaN -> None before mapping.
    secondary_ids = matched["Secondary IDs"].where(
        matched["Secondary IDs"].notna(), None
    )
    matched["nct_secondary"] = secondary_ids.map(extract_nct)
    matched["tier0_invisible"] = matched["nct_secondary"].map(is_tier0_invisible)

    # Gate 2: publication via Europe PMC, only when an NCT exists.
    # Qualified call (publication_match.lookup_publication) so monkeypatch
    # on the source module flows through here.
    g2_published, g2_pmid = [], []
    for _, r in matched.iterrows():
        if r["nct_secondary"]:
            v = publication_match.lookup_publication(
                r["nct_secondary"], paths.europe_pmc_cache_dir,
            )
        else:
            v = publication_match.Gate2Verdict(published=False, pmid=None)
        g2_published.append(v.published)
        g2_pmid.append(v.pmid)
    matched["gate2_published"] = g2_published
    matched["gate2_pmid"] = g2_pmid

    # Gate 3: Cochrane match (NCT-bridge + literal ensemble)
    pw = pd.read_parquet(paths.pairwise70_index)
    g3, g3_method, g3_review, g3_disagree = [], [], [], []
    with contextlib.closing(sqlite3.connect(paths.cdsr_string_index)) as cdsr:
        for _, r in matched.iterrows():
            v = match_trial(
                nct=r["nct_secondary"],
                pactr_id=str(r["TrialID"] or ""),
                pairwise70_index=pw,
                cdsr_conn=cdsr,
            )
            g3.append(v.in_cochrane)
            g3_method.append(v.method)
            g3_review.append(v.review_id)
            g3_disagree.append(v.ensemble_disagree)
    matched["gate3_in_cochrane"] = g3
    matched["gate3_match_method"] = g3_method
    matched["gate3_cochrane_review_id"] = g3_review
    matched["gate3_ensemble_disagree"] = g3_disagree
    matched["gate0_registered"] = True
    matched["country_lead"] = matched["Countries"].fillna("UNK")

    matched.to_parquet(out_dir / "trials.parquet", index=False)
    if not dropped.empty:
        dropped.to_csv(out_dir / "multi_condition_drops.csv", index=False)

    atlas = compute_funnel(matched, n_bootstrap=n_bootstrap)
    atlas["snapshot_date"] = _resolve_snapshot_date(paths, meta_path)
    atlas.to_csv(out_dir / "atlas.csv", index=False)
    return out_dir / "atlas.csv"


if __name__ == "__main__":
    import argparse
    import io
    import sys

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    from pactr_atlas.config import load_paths

    ap = argparse.ArgumentParser(description="PACTR Hiddenness Atlas — pipeline orchestrator")
    ap.add_argument(
        "--paths", default="paths.toml", type=Path,
        help="TOML file with snapshot + index paths (default: paths.toml)",
    )
    ap.add_argument(
        "--out-dir", default="data/processed", type=Path,
        help="Output directory for atlas.csv and trials.parquet (default: data/processed)",
    )
    ap.add_argument(
        "--n-bootstrap", default=1000, type=int,
        help="Bootstrap iterations for CI computation (default: 1000)",
    )
    ap.add_argument(
        "--meta-path", default=None, type=Path,
        help="Path to ictrp_metadata.json written by preflight (default: data/snapshots/ictrp_metadata.json)",
    )
    args = ap.parse_args()

    cfg = args.paths
    if not cfg.exists():
        print(f"FAIL: {cfg} does not exist; copy paths.toml.example and edit")
        raise SystemExit(2)

    try:
        _paths = load_paths(cfg)
        out = run_pipeline(
            _paths,
            out_dir=args.out_dir,
            n_bootstrap=args.n_bootstrap,
            meta_path=args.meta_path,
        )
        print(f"pipeline OK — atlas written to {out}")
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"PIPELINE_FAILED: {exc}")
        raise SystemExit(1)
