"""Cochrane-MA match: 3-strategy ensemble.

Primary:    NCT-bridge      (this task)
Sensitivity: PACTR-ID literal (Task 10)
Validation: Pairwise70-restricted manual audit cohort (Task 11)
"""
from __future__ import annotations

import sqlite3
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


def pactr_id_literal_match(
    pactr_id: str, cdsr_conn: sqlite3.Connection
) -> MatchVerdict:
    if not pactr_id:
        return MatchVerdict(in_cochrane=False, method="none")
    cur = cdsr_conn.execute(
        "SELECT review_id FROM review_strings WHERE body_text LIKE ? LIMIT 5",
        (f"%{pactr_id}%",),
    )
    review_ids = tuple(sorted({row[0] for row in cur.fetchall()}))
    if not review_ids:
        return MatchVerdict(in_cochrane=False, method="none")
    return MatchVerdict(
        in_cochrane=True, method="pactr_id_literal",
        review_id=review_ids[0], review_ids_all=review_ids,
    )
