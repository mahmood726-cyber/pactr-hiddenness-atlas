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


def run_pipeline(
    paths: Paths, *, out_dir: Path, n_bootstrap: int = 1000,
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
    atlas["snapshot_date"] = "fixture-50"
    atlas.to_csv(out_dir / "atlas.csv", index=False)
    return out_dir / "atlas.csv"
