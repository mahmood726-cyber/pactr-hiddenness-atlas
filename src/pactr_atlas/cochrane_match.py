"""Cochrane-MA match: 3-strategy ensemble.

Primary:    NCT-bridge      (this task)
Sensitivity: PACTR-ID literal (Task 10)
Validation: Pairwise70-restricted manual audit cohort (Task 11)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class MatchVerdict:
    in_cochrane: bool
    method: str
    review_id: Optional[str] = None
    review_ids_all: Optional[tuple[str, ...]] = None


def nct_bridge_match(nct: Optional[str], pairwise70_index: pd.DataFrame) -> MatchVerdict:
    if not nct:
        return MatchVerdict(in_cochrane=False, method="none")
    hits = pairwise70_index[pairwise70_index["nct"] == nct]
    if hits.empty:
        return MatchVerdict(in_cochrane=False, method="none")
    review_ids = tuple(sorted(set(hits["review_id"].astype(str))))
    return MatchVerdict(
        in_cochrane=True, method="nct_bridge",
        review_id=review_ids[0], review_ids_all=review_ids,
    )
